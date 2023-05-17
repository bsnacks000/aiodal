"""Declarative API for creating dynamic where clause. Convenient for filtering GET requests from 
incoming query parameters to avoid having to write switch blocks. Inspired by `django_filter`.
"""

import abc
from typing import Generic, Any, Iterable, TypeVar, Optional
from aiodal import dal
import sqlalchemy as sa


class SelectFilterStatement(abc.ABC):
    @abc.abstractmethod
    def filter_stmt(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
    ) -> sa.Select[Any]:
        ...


FilterStmtT = TypeVar("FilterStmtT", bound=SelectFilterStatement)


class QueryParamsModel(SelectFilterStatement):
    """Base class for all incoming query params.
    To pass in other variables for filtering on the route that you
    do not want to expose via public, simply use underscore. This is useful for
    supplying urls or filter criteria for child views.

    We use limit/offset pagination to paginate so those values can be supplied here.
    There are attached to the tail end of the query statment after any where clauses.
    """

    def __init__(self, limit: int | None = None, offset: int | None = None):
        self.limit = limit
        self.offset = offset

    __filterset__: Optional["FilterSet[Any]"] = None

    def filter_stmt(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
    ) -> sa.Select[Any]:
        if self.__filterset__:
            stmt = self.__filterset__.apply(transaction, stmt, self)
        if self.offset:
            stmt = stmt.offset(self.offset)
        if self.limit:
            stmt = stmt.limit(self.limit)
        return stmt


QueryParamsModelT = TypeVar("QueryParamsModelT", bound=QueryParamsModel)


class WhereFilter(abc.ABC, Generic[QueryParamsModelT]):
    def __init__(self, tablename: str, col: str, param: str):
        self.tablename = tablename
        self.col = col
        self.param = param

    @abc.abstractmethod
    def apply(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
        params: QueryParamsModelT,
    ) -> sa.Select[Any]:
        ...


class WhereGE(WhereFilter[QueryParamsModelT]):
    def apply(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
        params: QueryParamsModelT,
    ) -> sa.Select[Any]:
        if hasattr(params, self.param):
            attr = getattr(params, self.param)
            if attr:
                t = transaction.get_table(self.tablename)
                stmt = stmt.where(t.c[self.col] >= attr)
        return stmt


class WhereLE(WhereFilter[QueryParamsModelT]):
    def apply(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
        params: QueryParamsModelT,
    ) -> sa.Select[Any]:
        if hasattr(params, self.param):
            attr = getattr(params, self.param)
            if attr:
                t = transaction.get_table(self.tablename)
                stmt = stmt.where(t.c[self.col] <= attr)
        return stmt


class WhereGT(WhereFilter[QueryParamsModelT]):
    def apply(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
        params: QueryParamsModelT,
    ) -> sa.Select[Any]:
        if hasattr(params, self.param):
            attr = getattr(params, self.param)
            if attr:
                t = transaction.get_table(self.tablename)
                stmt = stmt.where(t.c[self.col] > attr)
        return stmt


class WhereLT(WhereFilter[QueryParamsModelT]):
    def apply(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
        params: QueryParamsModelT,
    ) -> sa.Select[Any]:
        if hasattr(params, self.param):
            attr = getattr(params, self.param)
            if attr:
                t = transaction.get_table(self.tablename)
                stmt = stmt.where(t.c[self.col] < attr)
        return stmt


class WhereEquals(WhereFilter[QueryParamsModelT]):
    def apply(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
        params: QueryParamsModelT,
    ) -> sa.Select[Any]:
        if hasattr(params, self.param):
            attr = getattr(params, self.param)
            if attr:
                t = transaction.get_table(self.tablename)
                stmt = stmt.where(t.c[self.col] == attr)
        return stmt


class WhereContains(WhereFilter[QueryParamsModelT]):
    def apply(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
        params: QueryParamsModelT,
    ) -> sa.Select[Any]:
        if hasattr(params, self.param):
            attr = getattr(params, self.param)
            if attr:
                t = transaction.get_table(self.tablename)
                stmt = stmt.where(t.c[self.col].contains(attr))
        return stmt


class FilterSet(Generic[QueryParamsModelT]):
    def __init__(self, wheres: Iterable[WhereFilter[QueryParamsModelT]]):
        self.wheres = wheres

    def apply(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
        params: QueryParamsModelT,
    ) -> sa.Select[Any]:
        for w in self.wheres:
            stmt = w.apply(transaction, stmt, params)
        return stmt


# Useful concrete class...
class IdParamsModel(SelectFilterStatement):
    def __init__(self, id_: int, tablename: str, id_col_name: str = "id"):
        self.id = id_
        self.tablename = tablename
        self.id_col_name = id_col_name

    def filter_stmt(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
    ) -> sa.Select[Any]:
        t = transaction.get_table(self.tablename)
        stmt = stmt.where(t.c[self.id_col_name] == self.id)
        return stmt
