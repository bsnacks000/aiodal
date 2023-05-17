"""Declarative API for creating dynamic where clause. Convenient for filtering GET requests from 
incoming query parameters to avoid having to write switch blocks. Inspired by `django_filter`.
"""

import abc
from typing import Generic, Any, Iterable, TypeVar, Optional
from aiodal import dal
import sqlalchemy as sa


class FilterStatement(abc.ABC):
    @abc.abstractmethod
    def filter_stmt(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
    ) -> sa.Select[Any]:
        ...


FilterStmtT = TypeVar("FilterStmtT", bound=FilterStatement)


class Filter(FilterStatement):
    """The basic Filter class. Runs through Filters in its filter set.

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


FilterT = TypeVar("FilterT", bound=Filter)


class IdFilter(FilterStatement):
    """This is a useful concrete class that we use to filter an object by id."""

    def __init__(self, id_: Any, tablename: str, id_col_name: str = "id"):
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


class WhereFilter(abc.ABC, Generic[FilterT]):
    def __init__(self, tablename: str, col: str, param: str):
        self.tablename = tablename
        self.col = col
        self.param = param

    @abc.abstractmethod
    def apply(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
        params: FilterT,
    ) -> sa.Select[Any]:
        ...


class WhereGE(WhereFilter[FilterT]):
    def apply(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
        params: FilterT,
    ) -> sa.Select[Any]:
        if hasattr(params, self.param):
            attr = getattr(params, self.param)
            if attr:
                t = transaction.get_table(self.tablename)
                stmt = stmt.where(t.c[self.col] >= attr)
        return stmt


class WhereLE(WhereFilter[FilterT]):
    def apply(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
        params: FilterT,
    ) -> sa.Select[Any]:
        if hasattr(params, self.param):
            attr = getattr(params, self.param)
            if attr:
                t = transaction.get_table(self.tablename)
                stmt = stmt.where(t.c[self.col] <= attr)
        return stmt


class WhereGT(WhereFilter[FilterT]):
    def apply(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
        params: FilterT,
    ) -> sa.Select[Any]:
        if hasattr(params, self.param):
            attr = getattr(params, self.param)
            if attr:
                t = transaction.get_table(self.tablename)
                stmt = stmt.where(t.c[self.col] > attr)
        return stmt


class WhereLT(WhereFilter[FilterT]):
    def apply(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
        params: FilterT,
    ) -> sa.Select[Any]:
        if hasattr(params, self.param):
            attr = getattr(params, self.param)
            if attr:
                t = transaction.get_table(self.tablename)
                stmt = stmt.where(t.c[self.col] < attr)
        return stmt


class WhereEquals(WhereFilter[FilterT]):
    def apply(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
        params: FilterT,
    ) -> sa.Select[Any]:
        if hasattr(params, self.param):
            attr = getattr(params, self.param)
            if attr:
                t = transaction.get_table(self.tablename)
                stmt = stmt.where(t.c[self.col] == attr)
        return stmt


class WhereContains(WhereFilter[FilterT]):
    def apply(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
        params: FilterT,
    ) -> sa.Select[Any]:
        if hasattr(params, self.param):
            attr = getattr(params, self.param)
            if attr:
                t = transaction.get_table(self.tablename)
                stmt = stmt.where(t.c[self.col].contains(attr))
        return stmt


class FilterSet(Generic[FilterT]):
    def __init__(self, wheres: Iterable[WhereFilter[FilterT]]):
        self.wheres = wheres

    def apply(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
        params: FilterT,
    ) -> sa.Select[Any]:
        for w in self.wheres:
            stmt = w.apply(transaction, stmt, params)
        return stmt
