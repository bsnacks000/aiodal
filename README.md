# aiodal 
--- 
A small toolset for working with sqlalchemy core using the reflection API and asyncio extension. 

Supports sqlalchemy 2.x.  

## about
---- 

What about the ORM? We've been using `sqlalchemy` for many years in a variety of contexts. We made the transition away from the ORM for several reasons. 

* We use timescaledb which did not play nice with ORM and alembic. There were some hacky solutions but basically autogenerate did not work very well and we had to write our alembic migrations by hand anyway (which isn't really that complicated honestly).
* We often need to write alot of complicated queries and/or interact with the postgresql extension (tsdb, crosstab) which we found much easier to manage using the core API.  
* When asyncio support was first introduced we could only use it with core and have developed alot of projects without the ORM. We prefer async python in our stack.  
* We use pydantic for object modeling and many of these models do not always map directly to a database table, but rather a complicated. We found it inconvenient and redundent to keep lots of models around for these different contexts

After doing a number of projects without the ORM we've found we don't really miss it all that much. Using `core` with the reflection API keeps the parts of our business logic related to querying away from object serialization and other application code which is nice. There are generally only one set of "models" for the project and these are often used with pydantic.

This little API is the backbone of most of our database and rest API projects.

The `DataAccessLayer` class is the centerpiece and acts as a controller and proxy. It is borrowed from an old book on sqlalchemy back from before the ORM was even a thing by Rick Copeland. It's designed to be instantiated in two parts so you can lazily initialize the db connection if need be. You call `await reflect` by passing in an engine and the dal will keep an instance of MetaData populated for the duration of your app. We also include automatically include views and allow for convenient lookup of unique constraints.  

A `TransactionManager` is created via an async `contextmanager` by passing in a connection and a reference to the dal instance. This wraps some of the basic patterns found in the documentation for sqlalchmey 1.4+. We yield this transaction which maintains a reference to both the dal itself and the active connection. It assures that the transaction will automatically commit after it goes out of scope or rollback on error. This is a pretty standard pattern we've written a million times. The same exact pattern works for a fastapi application using the dependency injection system.

I've included a json encoder that we use that will handle enums and datetimes.  

Even though we use postgres and I am testing this code using asyncpg and alembic this _should_ be compatible with any async sqlalchemy driver for any of the supported databases.

## pytest-plugin

Probably most useful is the pytest plugin. We've chosen to decouple it from `alembic` which means your dev environment will have to manage set up and tear down for any tests. You can look at our `docker-compose.yaml` file to see how this can be done using `psql` for isolating local tests. 

There are a number of python fixutres provided to setup an engine, but the minimal conftest should just need the following.
```python 
# conftest.py 

#1. Set anyio backend fixture scoped to session 
@pytest.fixture(scope="session")
def anyio_backend():
    """Override this to use a different backend for testing"""
    return "asyncio"

# 2. provide the testdb you are connecting to.
@pytest.fixture(scope="session")
def engine_uri() -> str:
    return "postgresql+asyncpg://user:pass@host:port/dbname

```

To see the other overrides you can look at `aiodal.pytest_plugin`. 

This give you access to an active `transaction` fixture that you can pass around. This is a common pattern found in alot of projects and is nothing new. Its default is to rollback after each test case.  


## oqm

We have a small framework for mapping _custom queries_ and related CRUD ops to python objects. It is implemented as a set of mixins and base classes that can be configured in declarative style similar to django or sqlalchemy.orm.

The core mixins are found in `oqm.query` and `oqm.dbentity`. 

In minimum, a `DBEntityT` should implement `Queryable` mixin that returns the represented data from the db. This doesn't neccessarily need to map to a complete table but it can... In these cases we can easily get similar django-like ORM behavior by implementing the other Mixins.

The `oqm` package provides a concrete API with these mixins that can be used to create list views and CRUD on single objects out of the box. 

### Queryable

We can use Queryable to create a list view out of an arbitrary `sqlalchemy.core` style query with dynamic runtime where clause. 

```python

class BookQueryParams:
    def __init__(self, name: str): 
        self.name = name



@dataclasses.dataclass
class BookList(dbentity.Queryable[BookQueryParams]):
    id: int = 0 
    author_id: int = 0
    name: str = ""
    catalog: str = ""
    extra: dict[str, Any] = dataclasses.field(default_factory=lambda: {})

    @classmethod
    def query_stmt(cls, transaction: dal.TransactionManager, where: BookQueryParams) -> SaSelect:
        t = transaction.get_table("book")
        stmt = sa.select(t).where( t.c.name == where.name).order_by(t.c.id)
        return stmt


class BookListQ(query.ListQ[BookList, BookQueryParams]):
    __db_obj__ = BookList

#in pratice:
params = BookQueryParams(name="Lord Of the Tables")
l = BookListQ(where=params)
book_list = await l.list(transaction) #returns list[TableDBEntityT] --> list[BookDBEntity]
```


### CRUD single objects

We can CRUD single objects useful in context for REST APIs. 

Here another `Queryable` is used to return a detail view using `DetailQ`. This concrete class will call `result.one()` to get the result and raise 
an error if the object is not found. 

To insert update and delete we inherit from the appropriate abstract class and implement the needed statement. 

Note that these operations are simple in this example but because the db entities do not neccessarily need to be tied to a database table we have flexibilty. 
For example we can insert and update an object using a CTE. 

In the future we might extend CUD ops to include bulk statements.  

```python

class ObjectId: 
    def __init__(self, id: int): 
        self.id = id 


@dataclasses.dataclass
class BookList(dbentity.Queryable[ObjectId]):
    id: int = 0 
    author_id: int = 0
    name: str = ""
    catalog: str = ""
    extra: dict[str, Any] = dataclasses.field(default_factory=lambda: {})

    @classmethod
    def query_stmt(cls, transaction: dal.TransactionManager, where: ObjectId) -> SaSelect:
        t = transaction.get_table("book")
        stmt = sa.select(t).where( t.c.id == where.id).order_by(t.c.id)
        return stmt


class BookDetailQ(query.DetailQ[Book]):
    __db_obj__ = BookDetail

#in pratice:
obj = ObjectId(1)
dq = BookDetailQ(where=obj)
book_detail = await dq.detail(transaction) # --> Book!
```

### Inserting

```python

@dataclasses.dataclass
class BookForm:
    author_name: str
    name: str
    catalog: str
    

@dataclasses.dataclass
class BookDBEntity(dbentity.Insertable[BookForm]):
    ...

    @classmethod
    def insert_stmt(
        cls, transaction: dal.TransactionManager, data: BookForm
    ) -> dbentity.SaReturningInsert:
        t = transaction.get_table("book")
        author_table = transaction.get_table("author")
        author_id_subq = (
            sa.select(author_table.c.id)
            .where(author_table.c.name == data.author_name)
            .scalar_subquery()
        )
        stmt = (
            sa.insert(t)
            .values(
                author_id=author_id_subq,
                name=data.name,
                catalog=data.catalog,
                extra=data.extra,
            )
            .returning(t) # NOTE should use returning in this API
        )
        return stmt

class BookInsertQ(query.InsertQ[Book, BookForm]):
    __db_obj__ = Book

#in pratice:
data = BookForm(author_name="JRR TOKEN", name="Lord of the Tables", catalog="pg_catalog", extra="rice")
insert_ = BookInsertQ(data=data)
# excute insert stmt to Book table with a subquery look up to author table for author name 
inesert_.insert(transaction) # returns BookDBEntity
```

### Updating

```python
@dataclasses.dataclass
class BookPatchForm:
    id: int
    catalog: str
    extra: Dict[str, Any] = {}


@dataclasses.dataclass
class BookDBEntity(dbentity.Updateable):
    ...

    @classmethod
    def update_stmt(
        cls, transaction: dal.TransactionManager, data: BookPatchForm
    ) -> dbentity.SaReturningUpdate:
        t = transaction.get_table("book")
        stmt = (
            sa.update(t)
            .where(t.c.id == data.id)
            .values(**data.dict(exclude={"id"}, exclude_none=True))
            .returning(t)
        )
        return stmt
```

Next we implement `UpdateQ` that will execute `update_stmt` and update the row in the db.
```python
class BookUpdateQ(
    query.UpdateQ[BookDBEntity, BookPatchForm]
):
    __db_obj__ = BookDBEntity

#in pratice:
patch_data = BookPatchForm(id=book1.id, extra={"extra": "sauce"})

update_q = BookUpdateQ(data=patch_data)
updated_book = await update_q.update(transaction)   
```

### Delete

```python

@dataclasses.dataclass
class BookDeleteForm:
    id: int

@dataclasses.dataclass
class BookDBEntity(dbentity.Deleteable[BookDeleteForm]):
    ...

    @classmethod
    def delete_stmt(
        cls, transaction: dal.TransactionManager, data: BookDeleteForm
    ) -> dbentity.ReturningDelete:
        t = transaction.get_table("book")
        return sa.delete(t).where(t.c.id == data.id).returning(t)


class BookDeleteQ(query.DeleteQ[DeleteableBookDBEntity, BookDeleteForm]):
    __db_obj__ = DeleteableBookDBEntity


#practice:
delete_data = BookDeleteForm(id=book1.id)
l = BookDeleteQ(delete_data)
deleted_book = await l.delete(transaction)
```

### Create, Read and Update, Delete

Now, we can build a readable, writable, updateable, and deleteable `DBEntity` as follows:

```python
@dataclasses.dataclass
class Book(
    dbentity.Queryable[BookParams],
    dbentity.Insertable[BookForm],
    dbentity.Updateable[BookPatchForm],
    dbentity.Deleteable[BookDeleteForm],
):  
    ...

    @classmethod
    def query_stmt(cls, transaction: dal.TransactionManager, where: BookParams) -> dbentity.SaSelect:
        ...
    
    @classmethod
    def insert_stmt(
        cls, transaction: dal.TransactionManager, data: BookForm
    ) -> dbentity.SaReturningInsert:
        ...

    @classmethod
    def update_stmt(
        cls, transaction: dal.TransactionManager, data: BookPatchForm
    ) -> dbentity.SaReturningUpdate:
        ...

    @classmethod
    def delete_stmt(
        cls, transaction: dal.TransactionManager, data: BookDeleteForm
    ) -> dbentity.ReturningDelete:
```
