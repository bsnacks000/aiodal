from .. import dal
from .filters import QueryParamsModel
from .query import ListQ
from .dbentity import TableDBEntityT
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection
import abc
from typing import TypeVar, Any


class AliasingTransactionManager(dal.TransactionManager):
    def __init__(self, conn: AsyncConnection, db: dal.DataAccessLayer):
        super().__init__(conn, db)
        self._aliased_tables: dict[str, sa.TableValuedAlias] = {}

    def set_aliased(self, name: str, t: sa.TableValuedAlias) -> None:
        self._aliased_tables[name] = t

    def get_table(self, name: str) -> sa.Table | sa.TableValuedAlias:  # type: ignore
        aliased = self._aliased_tables.get(name)
        if aliased is not None:
            return aliased
        return super().get_table(name)


class AliasedQueryParamsModel(QueryParamsModel):
    @abc.abstractmethod
    def set_aliased_table(
        self,
        transaction: AliasingTransactionManager,
    ) -> None:
        ...


AliasedQueryParamsModelT = TypeVar(
    "AliasedQueryParamsModelT", bound=AliasedQueryParamsModel
)


class AliasedListQ(ListQ[TableDBEntityT, AliasedQueryParamsModelT]):
    def __init__(self, where: AliasedQueryParamsModelT):
        self.where = where

    def _prepare_stmt(self, transaction: AliasingTransactionManager) -> sa.Select[Any]:  # type: ignore
        self.where.set_aliased_table(transaction)
        stmt = self._db_obj.query_stmt(transaction)
        stmt = self.where.filter_stmt(transaction, stmt)
        return stmt
