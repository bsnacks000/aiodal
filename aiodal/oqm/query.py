from typing import Generic, Type, MutableSequence
from aiodal import dal
from .dbentity import (
    QueryableT,
    InsertableT,
    UpdateableT,
    DeleteableT,
    FormDataT,
    DBEntityT,
    SaSelect,
    SaReturningUpdate,
    SaReturningDelete,
    SaReturningInsert,
    FilterDataT,
)

# from .filters import (
#     FilterStmtT,
#     FilterT,
#     IdFilter,
# )
from typing import Optional
import abc


class IListQ(abc.ABC, Generic[DBEntityT]):
    @abc.abstractmethod
    async def list(self, t: dal.TransactionManager) -> MutableSequence[DBEntityT]:
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


class BaseReadQ(abc.ABC, Generic[QueryableT, FilterDataT]):
    __db_obj__: Type[QueryableT]

    def __init__(self, where: Optional[FilterDataT] = None):
        self.where = where

    def _prepare_stmt(self, transaction: dal.TransactionManager) -> SaSelect:
        return self.__db_obj__.query_stmt(transaction, self.where)


class ListQ(IListQ[QueryableT], BaseReadQ[QueryableT, FilterDataT]):
    async def list(
        self,
        t: dal.TransactionManager,
    ) -> MutableSequence[QueryableT]:
        result = await t.execute(self._prepare_stmt(t))
        return [self.__db_obj__(**m) for m in result.mappings()]


class DetailQ(IDetailQ[QueryableT], BaseReadQ[QueryableT, FilterDataT]):
    async def detail(self, t: dal.TransactionManager) -> QueryableT:
        result = await t.execute(self._prepare_stmt(t))
        r = result.one()  # raises NoResultFound or MultipleResultsFound
        return self.__db_obj__(**r._mapping)


class InsertQ(IInsertQ[InsertableT], Generic[InsertableT, FormDataT]):
    __db_obj__: Type[InsertableT]

    def __init__(self, data: FormDataT):
        self.data = data

    def _prepare_stmt(self, t: dal.TransactionManager) -> SaReturningInsert:
        return self.__db_obj__.insert_stmt(t, self.data)

    async def insert(self, t: dal.TransactionManager) -> InsertableT:
        result = await t.execute(self._prepare_stmt(t))
        r = result.one()
        return self.__db_obj__(**r._mapping)


class DeleteQ(IDeleteQ[DeleteableT], Generic[DeleteableT, FormDataT]):
    """Base Delete class that constructs delete stmt from DBEntity.delete.stmt and executes it"""

    __db_obj__: Type[DeleteableT]

    def __init__(self, data: FormDataT) -> None:
        self.data = data

    def _prepare_stmt(self, t: dal.TransactionManager) -> SaReturningDelete:
        return self.__db_obj__.delete_stmt(t, self.data)

    async def delete(self, t: dal.TransactionManager) -> DeleteableT:
        result = await t.execute(self._prepare_stmt(t))
        r = result.one()
        return self.__db_obj__(**r._mapping)


class UpdateQ(IUpdateQ[UpdateableT], Generic[UpdateableT, FormDataT]):
    """Base Update class that constructs update stmt from DBEntity.insert_stmt and where stmts from
    Update Filters  and executes the final statement.
    """

    __db_obj__: Type[UpdateableT]

    def __init__(self, data: FormDataT):
        self.data = data

    def _prepare_stmt(self, t: dal.TransactionManager) -> SaReturningUpdate:
        return self.__db_obj__.update_stmt(t, self.data)

    async def update(self, t: dal.TransactionManager) -> UpdateableT:
        result = await t.execute(self._prepare_stmt(t))
        r = result.one()
        return self.__db_obj__(**r._mapping)


# class ListQ(IListQ[QueryableT], BaseQ[QueryableT, FilterDataT]):
#     """Read Query class is the most public facing class; this calls into BaseQ._execute and
#     returns a list of DBEntity; instantiated with QueryParamsModel.
#     Example:
#     class BookListQ(
#         ListQ[BookDBEntity, BookQueryParams],
#     ):
#         __db_obj__ = BookDBEntity

#     #in pratice:
#     params = BookQueryParams(name="Lord Of the Tables")
#     l = BookListQ(where=params)
#     l.list(transaction)"""

#     async def list(
#         self,
#         t: dal.TransactionManager,
#     ) -> MutableSequence[QueryableT]:
#         result = await self._execute(t)
#         return [self._db_obj(**m) for m in result.mappings()]


# class DetailQ(IDetailQ[QueryableT], BaseQ[QueryableT, FilterDataT]):
#     """DetailQ returns a single DBEntity object by its id
#     Example:

#     class BookDetailQ(
#         DetailQ[BookDBEntity],
#     ):
#         __db_obj__ = BookDBEntity

#     #in pratice:
#     id_params = IdParamsModel(id_=1, tablename="book")
#     dq = BookDetailQ(where=id_params)
#     dq.detail(transaction) # returns BookDBEntity with id=1 if exists

#     """

#     async def detail(self, t: dal.TransactionManager) -> QueryableT:
#         result = await self._execute(t)
#         r = result.one()  # raises NoResultFound or MultipleResultsFound
#         return self._db_obj(**r._mapping)


# class InsertQ(IInsertQ[InsertableT], BaseInsertQ[InsertableT, FormDataT]):
#     """Insert Query class is the most public facing class; this calls into BaseInsertQ._execute and returns a single DBEntity object;
#     instantiated with BaseFormModel.
#     Example:


#     class BookInsertQ(InsertQ[BookDBEntity, BookForm]):
#         __db_obj__ = BookDBEntity

#     #in pratice:
#     data = BookForm(author_name="JRR TOKEN", name="Lord of the Tables", catalog="pg_catalog", extra="rice")
#     insert_ = BookInsertQ(data=data)
#     inesert_.insert(transaction) # returns BookDBEntity that just has been inserted
#     """

#     async def insert(self, t: dal.TransactionManager) -> InsertableT:
#         result = await self._execute(t)
#         r = result.one()
#         return self._db_obj(**r._mapping)


# class UpdateQ(IUpdateQ[UpdateableT], BaseUpdateQ[UpdateableT, FormDataT]):
#     """UpdateQuery class is the most public facing class; this calls into BaseUpdateQ._execute and returns a single DBEntity object;
#     instantiated with BaseFormModel and UpdateQueryParams, which can be just a placeholder class or in which additional filter logic can be implemented.
#     Example:


#     class BookUpdateQ(
#         UpdateQ[BookDBEntity, BookPatchForm, BookUpdateQueryParams]
#     ):
#         __db_obj__ = BookDBEntity

#     #in pratice:
#     patch_data = BookPatchForm(id=1, extra={"extra": "sauce"})
#     params = BookUpdateQueryParams()

#     update_q = BookUpdateQ(data=patch_data, where=params)
#     updated_book = await update_q.update(transaction) #book with id 1 has its extra field updated
#     """

#     async def update(self, t: dal.TransactionManager) -> UpdateableT:
#         result = await self._execute(t)
#         r = result.one()
#         return self._db_obj(**r._mapping)


# class DeleteQ(IDeleteQ[DeleteableT], BaseDeleteQ[DeleteableT, FormDataT]):
#     """Public facing class to delete deletable DBEntities. Returns nothing for now"""

#     async def delete(self, t: dal.TransactionManager) -> DeleteableT:
#         result = await self._execute(t)
#         r = result.one()
#         return self._db_obj(**r._mapping)
