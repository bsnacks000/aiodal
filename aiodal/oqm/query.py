from typing import Generic, Type, Any, MutableSequence
from aiodal import dal
import sqlalchemy as sa
from .dbentity import (
    QueryableT,
    InsertableT,
    UpdateableT,
    DeleteableT,
    FormDataT,
    DBEntityT,
)
from .filters import (
    FilterStmtT,
    FilterT,
    IdFilter,
)

import abc


class IListQ(abc.ABC, Generic[DBEntityT]):
    @abc.abstractmethod
    async def list(
        self,
        t: dal.TransactionManager,
    ) -> MutableSequence[DBEntityT]:
        ...


class IDetailQ(abc.ABC, Generic[DBEntityT]):
    @abc.abstractmethod
    async def detail(self, t: dal.TransactionManager) -> DBEntityT:
        ...


class IInsertQ(abc.ABC, Generic[DBEntityT]):
    @abc.abstractmethod
    async def insert(self, t: dal.TransactionManager) -> DBEntityT:
        ...


class IUpdateQ(abc.ABC, Generic[DBEntityT]):
    @abc.abstractmethod
    async def update(self, t: dal.TransactionManager) -> DBEntityT:
        ...


class IDeleteQ(abc.ABC, Generic[DBEntityT]):
    @abc.abstractmethod
    async def delete(self, t: dal.TransactionManager) -> DBEntityT:
        ...


class BaseQ(abc.ABC, Generic[QueryableT, FilterStmtT]):
    """Base Query class that constructs where stmt from DBEntity.query_stmt and where stmts from
    Filters and executes the final statement.
    """

    __db_obj__: Type[QueryableT]

    def __init__(self, where: FilterStmtT):
        self.where = where

    @property
    def _db_obj(self) -> Type[QueryableT]:
        return self.__class__.__db_obj__

    def _prepare_stmt(self, transaction: dal.TransactionManager) -> sa.Select[Any]:
        stmt = self._db_obj.query_stmt(transaction)
        stmt = self.where.filter_stmt(transaction, stmt)
        return stmt

    async def _execute(self, t: dal.TransactionManager) -> sa.CursorResult[Any]:
        stmt = self._prepare_stmt(t)
        return await t.execute(stmt)


class BaseInsertQ(abc.ABC, Generic[InsertableT, FormDataT]):
    """Base Insert class that constructs insert stmt from DBEntity.insert_stmt and excecutes."""

    __db_obj__: Type[InsertableT]

    def __init__(self, data: FormDataT):
        self.data = data

    @property
    def _db_obj(self) -> Type[InsertableT]:
        return self.__class__.__db_obj__

    async def _execute(self, t: dal.TransactionManager) -> sa.CursorResult[Any]:
        stmt = self._db_obj.insert_stmt(t, self.data)
        return await t.execute(stmt)


class BaseDeleteQ(abc.ABC, Generic[DeleteableT]):
    """Base Delete class that constructs delete stmt from DBEntity.delete.stmt and executes it"""

    __db_obj__: Type[DeleteableT]

    @property
    def _db_obj(self) -> Type[DeleteableT]:
        return self.__class__.__db_obj__

    async def _execute(self, t: dal.TransactionManager) -> None:
        stmt = self._db_obj.delete_stmt(t)
        await t.execute(stmt)


class BaseUpdateQ(abc.ABC, Generic[UpdateableT, FormDataT]):
    """Base Update class that constructs update stmt from DBEntity.insert_stmt and where stmts from
    Update Filters  and executes the final statement.
    """

    __db_obj__: Type[UpdateableT]

    def __init__(self, data: FormDataT):
        self.data = data

    @property
    def _db_obj(self) -> Type[UpdateableT]:
        return self.__class__.__db_obj__

    def _prepare_stmt(self, transaction: dal.TransactionManager) -> sa.Update:
        return self._db_obj.update_stmt(transaction, self.data)

    async def _execute(self, t: dal.TransactionManager) -> sa.CursorResult[Any]:
        return await t.execute(self._prepare_stmt(t))


class ListQ(IListQ[QueryableT], BaseQ[QueryableT, FilterT]):
    """Read Query class is the most public facing class; this calls into BaseQ._execute and
    returns a list of DBEntity; instantiated with QueryParamsModel.
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
    ) -> MutableSequence[QueryableT]:
        result = await self._execute(t)
        return [self._db_obj(**m) for m in result.mappings()]


class DetailQ(IDetailQ[QueryableT], BaseQ[QueryableT, IdFilter]):
    """DetailQ returns a single DBEntity object by its id
    Example:

    class BookDetailQ(
        DetailQ[BookDBEntity],
    ):
        __db_obj__ = BookDBEntity

    #in pratice:
    id_params = IdParamsModel(id_=1, tablename="book")
    dq = BookDetailQ(where=id_params)
    dq.detail(transaction) # returns BookDBEntity with id=1 if exists

    """

    async def detail(self, t: dal.TransactionManager) -> QueryableT:
        result = await self._execute(t)
        r = result.one()  # raises NoResultFound or MultipleResultsFound
        return self._db_obj(**r._mapping)


class InsertQ(
    IInsertQ[InsertableT],
    BaseInsertQ[InsertableT, FormDataT],
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

    async def insert(self, t: dal.TransactionManager) -> InsertableT:
        result = await self._execute(t)
        r = result.one()
        return self._db_obj(**r._mapping)


class UpdateQ(
    IUpdateQ[UpdateableT],
    BaseUpdateQ[UpdateableT, FormDataT],
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

    async def update(self, t: dal.TransactionManager) -> UpdateableT:
        result = await self._execute(t)
        r = result.one()
        return self._db_obj(**r._mapping)
