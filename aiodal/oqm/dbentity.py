""" These are stubs and mixins that form the backbone of `oqm`. We use 2 generic constructs: A DBEntityT is any representation that 
comes from the database. A FormDataT is any input that can be inserted or updated in the database.
"""
from typing import TypeVar, Generic, Any
import abc
from aiodal import dal
import sqlalchemy as sa

DBEntityT = TypeVar(
    "DBEntityT"
)  # generic T repr a database entity (table / result of query)
FormDataT = TypeVar("FormDataT")  # generic T used to handle form data


class Queryable(abc.ABC):
    """enable a dbentity to be readable/query-able; works with QueryParamsModel which
    adds additonal where stmt to the output from query_stmt
    """

    @classmethod
    @abc.abstractmethod
    def query_stmt(
        cls,
        transaction: dal.TransactionManager,
    ) -> sa.Select[Any]:
        ...


class Insertable(abc.ABC, Generic[FormDataT]):
    """enable a dbentity to be writable; takes a pydantic BaseForm model, which contains data to be inserted into db."""

    @classmethod
    @abc.abstractmethod
    def insert_stmt(
        cls, transaction: dal.TransactionManager, data: FormDataT
    ) -> sa.Insert:
        ...


class Updateable(Generic[FormDataT]):
    """enable a dbentity to be updateable; takes a pydantic BaseForm model, which contains data to be inserted into db, and
    a UpdateQueryParamsModel, in which addtional filtering logic can be implemented."""

    @classmethod
    @abc.abstractmethod
    def update_stmt(
        cls,
        transaction: dal.TransactionManager,
        data: FormDataT,
    ) -> sa.Update:
        ...


_T = Any
QueryableT = TypeVar("QueryableT", bound=Queryable)
InsertableT = TypeVar("InsertableT", bound=Insertable[_T])
UpdateableT = TypeVar("UpdateableT", bound=Updateable[_T])
