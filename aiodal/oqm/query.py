from typing import Generic, Type, Any
from aiodal import dal
import sqlalchemy as sa
from .dbentity import (
    TableDBEntityT,
    InsertableDBEntityT,
    UpdateableDBEntityT,
    BaseFormModelT,
    IListQ,
    IDetailQ,
    IUpdateQ,
    IInsertQ,
)
from .filters import (
    FilterStmtT,
    UpdateFilterStmtT,
    QueryParamsModelT,
    IdParamsModel,
    UpdateQueryParamsModelT,
)

sa_total_count = lambda column: sa.func.count(column).over().label("total_count")  # type: ignore


class BaseQ(Generic[TableDBEntityT, FilterStmtT]):
    """Base Query class that constructs where stmt from DBEntity.query_stmt and where stmts from Filters and executes the final statement."""

    __db_obj__: Type[TableDBEntityT]

    def __init__(self, where: FilterStmtT):
        self.where = where

    @property
    def _db_obj(self) -> Type[TableDBEntityT]:
        return self.__class__.__db_obj__

    def _prepare_stmt(self, transaction: dal.TransactionManager) -> sa.Select[Any]:
        stmt = self._db_obj.query_stmt(transaction)
        stmt = self.where.filter_stmt(transaction, stmt)
        return stmt

    async def _execute(self, t: dal.TransactionManager) -> sa.CursorResult[Any]:
        stmt = self._prepare_stmt(t)
        return await t.execute(stmt)


class BaseInsertQ(Generic[InsertableDBEntityT, BaseFormModelT]):
    """Base Insert class that constructs insert stmt from DBEntity.insert_stmt and excecutes."""

    __db_obj__: Type[InsertableDBEntityT]

    def __init__(self, data: BaseFormModelT):
        self.data = data

    @property
    def _db_obj(self) -> Type[InsertableDBEntityT]:
        return self.__class__.__db_obj__

    async def _execute(self, t: dal.TransactionManager) -> sa.CursorResult[Any]:
        stmt = self._db_obj.insert_stmt(t, self.data)
        return await t.execute(stmt)


class BaseUpdateQ(Generic[UpdateableDBEntityT, BaseFormModelT, UpdateFilterStmtT]):
    """Base Update class that constructs update stmt from DBEntity.insert_stmt and where stmts from Update Filters  and executes the final statement."""

    __db_obj__: Type[UpdateableDBEntityT]

    def __init__(self, data: BaseFormModelT, where: UpdateFilterStmtT):
        self.where = where
        self.data = data

    @property
    def _db_obj(self) -> Type[UpdateableDBEntityT]:
        return self.__class__.__db_obj__

    def _prepare_stmt(self, transaction: dal.TransactionManager) -> sa.Update:
        stmt = self._db_obj.update_stmt(transaction, self.data)
        stmt = self.where.filter_stmt(transaction, stmt)
        stmt = stmt.returning(self._db_obj.table(transaction))
        return stmt

    async def _execute(self, t: dal.TransactionManager) -> sa.CursorResult[Any]:
        stmt = self._prepare_stmt(t)
        return await t.execute(stmt)


class ListQ(IListQ[TableDBEntityT], BaseQ[TableDBEntityT, QueryParamsModelT]):
    """Read Query class is the most public facing class; this calls into BaseQ._execute and returns a list of DBEntity; instantiated with QueryParamsModel.
    Example:
    class BookListQ(
        ListQ[BookDBEntity, BookQueryParams],
    ):
        __db_obj__ = BookDBEntity

    #in pratice:
    params = BookQueryParams(name="Lord Of the Tables")
    l = BookListQ(where=params)
    l.list(transaction)"""

    async def list(
        self,
        t: dal.TransactionManager,
    ) -> list[TableDBEntityT]:
        result = await self._execute(t)
        return [self._db_obj(**m) for m in result.mappings()]


class DetailQ(IDetailQ[TableDBEntityT], BaseQ[TableDBEntityT, IdParamsModel]):
    """Read Query class is the most public facing class; this calls into BaseQ._execute and returns a single DBEntity object; instantiated with IdParamsModel
    Example:

    class BookDetailQ(
        DetailQ[BookDBEntity],
    ):
        __db_obj__ = BookDBEntity

    #in pratice:
    id_params = IdParamsModel(id_=1, tablename="book")
    params = BookDetailQ(where=id_params)
    dq = BookDetailQ(where=params)
    dq.detail(transaction) # returns BookDBEntity with id=1 if exists

    """

    async def detail(self, t: dal.TransactionManager) -> TableDBEntityT:
        result = await self._execute(t)
        r = result.one()  # raises NoResultFound or MultipleResultsFound
        return self._db_obj(**r._mapping)


class InsertQ(
    IInsertQ[InsertableDBEntityT],
    BaseInsertQ[InsertableDBEntityT, BaseFormModelT],
):
    """Insert Query class is the most public facing class; this calls into BaseInsertQ._execute and returns a single DBEntity object;
    instantiated with BaseFormModel.
    Example:


    class BookInsertQ(InsertQ[BookDBEntity, BookForm]):
        __db_obj__ = BookDBEntity

    #in pratice:
    data = BookForm(author_name="JRR TOKEN", name="Lord of the Tables", catalog="pg_catalog", extra="rice")
    insert_ = BookInsertQ(data=data)
    inesert_.insert(transaction) # returns BookDBEntity that just has been inserted
    """

    async def insert(self, t: dal.TransactionManager) -> InsertableDBEntityT:
        result = await self._execute(t)
        r = result.one()
        return self._db_obj(**r._mapping)


class UpdateQ(
    IUpdateQ[UpdateableDBEntityT],  # Inherit from IUpdateQ instead since this is update
    BaseUpdateQ[UpdateableDBEntityT, BaseFormModelT, UpdateQueryParamsModelT],
):
    """UpdateQuery class is the most public facing class; this calls into BaseUpdateQ._execute and returns a single DBEntity object;
    instantiated with BaseFormModel and UpdateQueryParams, which can be just a placeholder class or in which additional filter logic can be implemented.
    Example:


    class BookUpdateQ(
        UpdateQ[BookDBEntity, BookPatchForm, BookUpdateQueryParams]
    ):
        __db_obj__ = BookDBEntity

    #in pratice:
    patch_data = BookPatchForm(id=1, extra={"extra": "sauce"})
    params = BookUpdateQueryParams()

    update_q = BookUpdateQ(data=patch_data, where=params)
    updated_book = await update_q.update(transaction) #book with id 1 has its extra field updated
    """

    async def update(self, t: dal.TransactionManager) -> UpdateableDBEntityT:
        result = await self._execute(t)
        r = result.one()
        return self._db_obj(**r._mapping)
