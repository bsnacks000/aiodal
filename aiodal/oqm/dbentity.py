""" These are stubs and mixins that form the backbone of `oqm`. We use 2 generic constructs: A DBEntityT is any representation that 
comes from the database. A FormDataT is any input that can be inserted or updated in the database.
"""
from typing import TypeVar, Generic, Any, Protocol, TypeAlias
import abc
from aiodal import dal
import sqlalchemy as sa

# see: https://github.com/cunybpl/aiodal/issues/17
from sqlalchemy.sql.dml import ReturningDelete, ReturningInsert, ReturningUpdate

DBEntityT = TypeVar(
    "DBEntityT"
)  # generic T repr a database entity (table / result of query)
FormDataT = TypeVar("FormDataT")  # generic T used to handle form data

_T = Any

SaReturningDelete: TypeAlias = ReturningDelete[_T]
SaReturningInsert: TypeAlias = ReturningInsert[_T]
SaReturningUpdate: TypeAlias = ReturningUpdate[_T]
SaSelect: TypeAlias = sa.Select[_T]


class Constructable(Protocol):
    def __init__(self, *args: Any, **kwargs: Any):
        ...


class Queryable(Constructable):
    """enable a dbentity to be readable/query-able; works with QueryParamsModel which
    adds additonal where stmt to the output from query_stmt
    """

    @classmethod
    @abc.abstractmethod
    def query_stmt(
        cls,
        transaction: dal.TransactionManager,
    ) -> SaSelect:
        ...  # pragma: no cover


class Deleteable(Constructable, Generic[FormDataT]):
    """Enable a dbentity to be deleteable"""

    @classmethod
    @abc.abstractmethod
    def delete_stmt(
        cls, transaction: dal.TransactionManager, data: FormDataT
    ) -> SaReturningDelete:
        ...  # pragma: no cover


class Insertable(Constructable, Generic[FormDataT]):
    """enable a dbentity to be writable; takes a pydantic BaseForm model, which contains data to be inserted into db."""

    @classmethod
    @abc.abstractmethod
    def insert_stmt(
        cls, transaction: dal.TransactionManager, data: FormDataT
    ) -> SaReturningInsert:
        ...  # pragma: no cover


class Updateable(Constructable, Generic[FormDataT]):
    """enable a dbentity to be updateable; takes a pydantic BaseForm model, which contains data to be inserted into db, and
    a UpdateQueryParamsModel, in which addtional filtering logic can be implemented."""

    @classmethod
    @abc.abstractmethod
    def update_stmt(
        cls,
        transaction: dal.TransactionManager,
        data: FormDataT,
    ) -> SaReturningUpdate:
        ...  # pragma: no cover


QueryableT = TypeVar("QueryableT", bound=Queryable)
DeleteableT = TypeVar("DeleteableT", bound=Deleteable[_T])
InsertableT = TypeVar("InsertableT", bound=Insertable[_T])
UpdateableT = TypeVar("UpdateableT", bound=Updateable[_T])
