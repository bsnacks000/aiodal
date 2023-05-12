### Querying

TableDBEntity represents an sql table.
In minimum, a TableDBEntity must implement a `query_stmt` that returns the represented table in db.

```python
from aiodal.oqm import dbentity
@dataclasses.dataclass
class BookDBEntity(dbentity.TableDBEntity):
    #id: int = 0 <-- inherit from DBEntity, parent of TableDBEntity
    author_id: int = 0
    name: str = ""
    catalog: str = ""
    extra: dict[str, Any] = dataclasses.field(default_factory=lambda: {})

    @classmethod
    def query_stmt(cls, transaction: dal.TransactionManager) -> sa.Select[Any]:
        t = transaction.get_table("book")
        stmt = sa.select(t).order_by(t.c.id)  # type: ignore
        return stmt
```
### List View
To construct a list view of `book` table, we can use `ListQ(IListQ[TableDBEntityT], BaseQ[TableDBEntityT, QueryParamsModelT])` which takes a `TableDBEntity` and 
a `QueryParamsModel`.
We can build `BookQueryParams` that can be used to query on `book.name` and `author.name` as follows

```python
from aiodal.oqm import filters
class BookQueryParams(filters.QueryParamsModel):
    def __init__(
        self,
        name: Optional[str] = "",
        author_name: Optional[str] = "",
        author_name_contains: Optional[str] = "",
        offset: int = 0, # Query(0, ge=0) #optionally use fastapi.Query
        limit: int = 1000, # Query(1000, ge=0, le=1000),
    ):
        self.offset = offset
        self.limit = limit
        self.name = name
        self.author_name = author_name
        self.author_name_contains = author_name_contains

    __filterset__ = filters.FilterSet(
        [   
            filters.WhereEquals("book", "name", "name"),
            filters.WhereEquals("author", "name", "author_name"),
            filters.WhereContains("author", "name", "author_name_contains"),
        ]
    )
```
`filters.FilterSet` takes in a list of `WhereFilter` objects: default WhereFilter objs are: `WhereEquals`, `WhereGE`, `WhereLE`, `WhereGT`, `WhereLT`, and `WhereContains`. `WhereFilter` object takes `dbtable_name`, `dbtable_column_name` and `python_param` that correspond to `dbtable_column_name`.

Next we implement a `ListQ` that works with `BookDBEntity` and `BookQueryParams`; note that `ListQ` is instaniated with `QueryParamsModel`.
```python
from aiodal import query
class BookListQ(
    query.ListQ[BookDBEntity, BookQueryParams],
):
    __db_obj__ = BookDBEntity

#in pratice:
params = BookQueryParams(name="Lord Of the Tables")
l = BookListQ(where=params)
book_list = await l.list(transaction) #returns list[TableDBEntityT] --> list[BookDBEntity]
```

#### Detail View
For constructing detail view, we can use `DetailQ(IDetailQ[TableDBEntityT], BaseQ[TableDBEntityT, IdParamsModel])`. Note that, unlike `ListQ`, `DetailQ` has already
`IdParamsModel` which is a subclass of `FilterStatement`, same as `QueryParamsModel`, so we do not need to provide any other query params model.
```python
class BookDetailQ(
    query.DetailQ[BookDBEntity]
):

    __db_obj__ = BookDBEntity

#in pratice:
id_=1
id_params = query.IdParamsModel(id_, tablename="book")
dq = BookDetailQ(where=id_params)
book_detail = await dq.detail(transaction) # --> BookDBEntity
```

### Inserting

To make `BookDBEntity` to be a writable table, we inherit it from `dbentity.InsertableDBEntity`, with which we implement `insert_stmt` method with relevant business logic to insert data into table in db. `insert_stmt` takes a `transaction` object with connection to db and a pydantic form, subclass of `dbentity.BaseFormModel`.

```python
class BookForm(dbentity.BaseFormModel):
    author_name: str
    name: str
    catalog: str
    extra: Dict[str, Any] = {}

@dataclasses.dataclass
class BookDBEntity(dbentity.InsertableDBEntity[BookForm]):
    ...

    @classmethod
    def insert_stmt(
        cls, transaction: dal.TransactionManager, data: BookForm
    ) -> sa.Insert:
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

Similarly to `ListQ` and `TableDBEntity`, `InsertableDBEntity` entity works together with `InsertQ` which has `insert` method that execute insert statment generated from `InsertableDBEntity.insert_stmt`

```python
class BookInsertQ(query.InsertQ[BookDBEntity, BookForm]):
    __db_obj__ = BookDBEntity 

#in pratice:
data = BookForm(author_name="JRR TOKEN", name="Lord of the Tables", catalog="pg_catalog", extra="rice")
insert_ = BookInsertQ(data=data)
# excute insert stmt to Book table with a subquery look up to author table for author name 
inesert_.insert(transaction) # returns BookDBEntity
```

### Updating

To make `BookDBEntity` a updateable table, we inherit it from `dbentity.UpdateableDBEntity`, with which we implement `update_stmt` method with relevant business logic to update data into table in db. `update_stmt` takes a `transaction` object with connection to db and a pydantic form, subclass of `dbentity.BaseFormModel` and `UpdateQueryParamsModel` in which additional business logic for filtering can be added to. To make `UpdateableDBEntity` work with `UpdateQueryParamsModel`, we add `table` classmethod that return `sa.Table` which will be used in `UpdateQueryParamsModel`; see `BaseUpdateQ._prepare_stmt`.
```python
class BookPatchForm(dbentity.BaseFormModel):
    id: int
    catalog: str
    extra: Dict[str, Any] = {}

@dataclasses.dataclass
class BookDBEntity(dbentity.UpdateableDBEntity):
    ...

    @classmethod
    def update_stmt(
        cls, transaction: dal.TransactionManager, data: BookPatchForm
    ) -> sa.Update:
        t = transaction.get_table("book")
        stmt = (
            sa.update(t)
            .where(t.c.id == data.id)
            .values(**data.dict(exclude={"id"}, exclude_none=True))
        )
        return stmt

    @classmethod
    def table(cls, transaction: dal.TransactionManager) -> sa.Table:
        return transaction.get_table("book")

#Update query params for additonal filter logic
class BookUpdateQueryParams(filters.UpdateQueryParamsModel):
    def __init__(self, author_name: Optional[str] = None):
        self.author_name = author_name

    __filterset__ = filters.FilterSet(
        [
            filters.WhereEquals("author", "name", "author_name"),
        ]
```
If no additonal querying or filtering is needed, `BookUpdateQueryParams` can be just a placeholder class with an empty `__filterset__ = filters.FilterSet([])`.

Next we implement `UpdateQ` that will execute `update_stmt` and update the row in the db.
```python
class BookUpdateQ(
    query.UpdateQ[BookDBEntity, BookPatchForm, BookUpdateQueryParams]
):
    __db_obj__ = BookDBEntity

#in pratice:
patch_data = BookPatchForm(id=book1.id, extra={"extra": "sauce"})
params = BookUpdateQueryParams() #no need to pass params even if there are filters

update_q = BookUpdateQ(data=patch_data, where=params)
updated_book = await update_q.update(transaction)   
```

One use case of UpdateQueryParamsModel will be soft deleting an item in db. That is, setting `item.active` to `True` (for recovering) and `False` (for soft deleting). By filtering on `active` column, we can make sure that an item that has been soft-deleted is not soft-deleted again.

### Create, Read and Update

Now, we can build a readable, writable and updateable `DBEntity` as follows:

```python
@dataclasses.dataclass
class BookDBEntity(
    dbentity.TableDBEntity,
    dbentity.InsertableDBEntity[BookForm],
    dbentity.UpdateableDBEntity[BookPatchForm],
):  
    ...

    @classmethod
    def query_stmt(cls, transaction: dal.TransactionManager) -> sa.Select[Any]:
        ...
    @classmethod
    def insert_stmt(
        cls, transaction: dal.TransactionManager, data: BookForm
    ) -> sa.Insert:
        ...

    @classmethod
    def update_stmt(
        cls, transaction: dal.TransactionManager, data: BookPatchForm
    ) -> sa.Update:
        ...
    
    @classmethod
    def table(cls, transaction: dal.TransactionManager) -> sa.Table:
        return transaction.get_table("book")
```
