import dataclasses
from typing import Optional, TypeVar, Generic, Any
import abc
from aiodal import dal
import sqlalchemy as sa
import pydantic


@dataclasses.dataclass
class DBEntity(abc.ABC):
    """This is an intermediate representation.
    We map sqlalchemy rows which are quite generic to these well defined types in `models`.

    If generating a list view for this API you must assure that sqlalchemy is providing a `total_count`
    column which is a scalar of total rows in the query before offset limit.

    This value is used by the paginator. The list view will raise if total_count
    is not provided.
    """

    id: int = 0
    total_count: Optional[int] = None


class BaseFormModel(pydantic.BaseModel):
    class Config:
        use_enum_values = True
        extra = "forbid"


BaseFormModelT = TypeVar("BaseFormModelT", bound=BaseFormModel)


@dataclasses.dataclass
class TableDBEntity(DBEntity):
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


@dataclasses.dataclass
class InsertableDBEntity(DBEntity, Generic[BaseFormModelT]):
    """enable a dbentity to be writable; takes a pydantic BaseForm model, which contains data to be inserted into db."""

    @classmethod
    @abc.abstractmethod
    def insert_stmt(
        cls, transaction: dal.TransactionManager, data: BaseFormModelT
    ) -> sa.Insert:
        ...


class UpdateableDBEntity(DBEntity, Generic[BaseFormModelT]):
    """enable a dbentity to be updateable; takes a pydantic BaseForm model, which contains data to be inserted into db, and
    a UpdateQueryParamsModel, in which addtional filtering logic can be implemented."""

    @classmethod
    @abc.abstractmethod
    def update_stmt(
        cls,
        transaction: dal.TransactionManager,
        data: BaseFormModelT,
    ) -> sa.Update:
        ...

    @classmethod
    @abc.abstractmethod
    def table(
        cls,
        transaction: dal.TransactionManager,
    ) -> sa.Table:
        """abstract method that must returns  sa.table that DBEntity is representing,
        which is utilized in BaseUpdateQ._prepare_stmt with sa.update(table).values(..).where(..).returning_table(UpdateableDBEntity.table())
        """
        ...


DBEntityT = TypeVar("DBEntityT", bound=DBEntity)
TableDBEntityT = TypeVar("TableDBEntityT", bound=TableDBEntity)
# XXX Any got rid of the squiggly line; using BaseFormModel give me error in UserInsert
InsertableDBEntityT = TypeVar("InsertableDBEntityT", bound=InsertableDBEntity[Any])
UpdateableDBEntityT = TypeVar("UpdateableDBEntityT", bound=UpdateableDBEntity[Any])


class IListQ(abc.ABC, Generic[DBEntityT]):
    @abc.abstractmethod
    async def list(
        self,
        t: dal.TransactionManager,
    ) -> list[DBEntityT]:
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
