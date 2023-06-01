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

In minimum, a `DBEntityT` should implement `Queryable` mixin that returns the represented data from the db. This doesn't neccessarily need to map to a complete table but it can... In these cases we can easily get similar django-like ORM behavior by implementing the other Mixins.


### DBEntities and simple Querying

Using a dataclass here is nice for speed and that it saves some time, but you can use any object here.

```python
@dataclasses.dataclass
class Book(dbentity.Queryable):
    id: int = 0 
    author_id: int = 0
    name: str = ""
    catalog: str = ""
    extra: dict[str, Any] = dataclasses.field(default_factory=lambda: {})

    @classmethod
    def query_stmt(cls, transaction: dal.TransactionManager) -> SaSelect:
        t = transaction.get_table("book")
        stmt = sa.select(t).order_by(t.c.id)  # type: ignore
        return stmt
```


### List View + Filtering
To construct a list view of `book` table, we can use `ListQ(IListQ[QueryableT], BaseQ[QueryableT, FilterT])` which takes a `TableDBEntity` and 
a `Filter`.

We can build `BookQueryParams` that can be used to query on `book.name` and `author.name` as follows

```python
from aiodal.oqm import filters

class BookQueryParams(filters.Filter):
    def __init__(
        self,
        name: Optional[str] = "",
        author_name: Optional[str] = "",
        author_name__contains: Optional[str] = "",
        offset: int = 0, # Query(0, ge=0) #optionally use fastapi.Query
        limit: int = 1000, # Query(1000, ge=0, le=1000),
    ):
        self.offset = offset
        self.limit = limit
        self.name = name
        self.author_name = author_name
        self.author_name__contains = author_name__contains

    __filterset__ = filters.FilterSet(
        [   
            filters.WhereEquals("book", "name", "name"),
            filters.WhereEquals("author", "name", "author_name"),
            filters.WhereContains("author", "name", "author_name__contains"),
        ]
    )
```
`filters.FilterSet` takes in a list of `WhereFilter` objects: default WhereFilter objs are: `WhereEquals`, `WhereGE`, `WhereLE`, `WhereGT`, `WhereLT`, and `WhereContains`. `WhereFilter` object takes `dbtable_name`, `dbtable_column_name` and `python_param` that correspond to `dbtable_column_name`.

Next we implement a `ListQ` that works with `BookDBEntity` and `BookQueryParams`; note that `ListQ` is instaniated with `QueryParamsModel`.
```python
from aiodal import query
class BookListQ(
    query.ListQ[Book, BookQueryParams],
):
    __db_obj__ = Book

#in pratice:
params = BookQueryParams(name="Lord Of the Tables")
l = BookListQ(where=params)
book_list = await l.list(transaction) #returns list[TableDBEntityT] --> list[BookDBEntity]
```

#### Detail View
For constructing detail view, we can use `DetailQ(IDetailQ[QueryableT], BaseQ[QueryableT, IdFilter])`. Note that, unlike `ListQ`, `DetailQ` has already
`IdFilter` which is a subclass of `FilterStatement`, same as `Filter`, so we do not need to provide any other query params model.
```python
class BookDetailQ(
    query.DetailQ[Book]
):

    __db_obj__ = Book

#in pratice:
id_=1
id_params = query.IdFilter(id_, tablename="book")
dq = BookDetailQ(where=id_params)
book_detail = await dq.detail(transaction) # --> Book!
```

### Inserting

To make `Book` to be a writable table, we inherit it from `dbentity.Insertable`, with which we implement `insert_stmt` method with relevant business logic to insert data into table in db. `insert_stmt` takes a `transaction` object with connection to db and a form model (we will be using pydantic model).

```python
import pydantic
class BookForm(pydantic.BaseFormModel):
    author_name: str
    name: str
    catalog: str
    extra: Dict[str, Any] = {}

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
            .returning(t)
        )
        return stmt
```

Similarly to `ListQ`, `Insertable` entity works together with `InsertQ` which has `insert` method that execute insert statment generated from `Insertable.insert_stmt`

```python
class BookInsertQ(query.InsertQ[Book, BookForm]):
    __db_obj__ = Book

#in pratice:
data = BookForm(author_name="JRR TOKEN", name="Lord of the Tables", catalog="pg_catalog", extra="rice")
insert_ = BookInsertQ(data=data)
# excute insert stmt to Book table with a subquery look up to author table for author name 
inesert_.insert(transaction) # returns BookDBEntity
```

### Updating

To make `Book` an updateable table, we inherit it from `dbentity.Updateable`, with which we implement `update_stmt` method with relevant business logic to update a single record. The `update_stmt` method takes a `transaction` object with connection to db. 


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
Similarly, we can implement delete as follows:
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
    dbentity.Queryable,
    dbentity.Insertable[BookForm],
    dbentity.Updateable[BookPatchForm],
    dbentity.Deleteable[BookDeleteForm],
):  
    ...

    @classmethod
    def query_stmt(cls, transaction: dal.TransactionManager) -> dbentity.SaSelect:
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

As of this writing we have not implemented `Delete` but a similar pattern since we do not regularly delete data from our applications but a similar pattern can be used to extend the `oqm` package.

