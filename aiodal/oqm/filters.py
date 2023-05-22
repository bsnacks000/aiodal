"""Declarative API for creating dynamic where clauses. Convenient for filtering GET requests from 
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
        ...  # pragma: no cover


FilterStmtT = TypeVar("FilterStmtT", bound=FilterStatement)


class Filter(FilterStatement):
    """The basic Filter class. Runs through Filters in its filter set and applies WhereFilters
    to a sqlalchemy stmt.

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
    """This is a useful concrete class that we use to simplfy filtering an object by id.
    Useful for detail view routes. It does not require more then one filter.
    """

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


class TableLookupError(KeyError):
    """Raised if lookup in both reflected table and aliased table fails."""


class WhereFilter(abc.ABC, Generic[FilterT]):
    def __init__(self, tablename: str, col: str, param: str):
        """Defines a single where clause on a single column. These should be pushed into a
        an instance of FilterSet.

        Args:
            tablename (str): _description_
            col (str): _description_
            param (str): _description_
        """
        self.tablename = tablename
        self.col = col
        self.param = param

    @abc.abstractmethod
    def _where(
        self, t: sa.Table | sa.TableValuedAlias, stmt: sa.Select[Any], attr: Any
    ) -> sa.Select[Any]:
        """Override this internal method to define the business logic against the column. See
        example implementations.

        Args:
            t (sa.Table | sa.TableValuedAlias): Either a Table or TableValuedAlias passed from apply.
            stmt (sa.Select[Any]): The sqla stmt to build
            attr (Any): The attribute passed from params

        Returns:
            sa.Select[Any]: _description_
        """
        ...  # pragma: no cover

    def apply(
        self,
        transaction: dal.TransactionManager,
        stmt: sa.Select[Any],
        params: FilterT,
    ) -> sa.Select[Any]:
        """Applies the filter against the given params which should be of type Filter.

        Args:
            transaction (dal.TransactionManager): _description_
            stmt (sa.Select[Any]): _description_
            params (FilterT): _description_

        Raises:
            e: _description_

        Returns:
            sa.Select[Any]: _description_
        """
        attr = getattr(params, self.param)
        t: sa.Table | sa.TableValuedAlias
        if attr:
            try:
                try:
                    t = transaction.get_table(self.tablename)
                except KeyError:
                    t = transaction.get_aliased(self.tablename)
            except KeyError as err:
                e = TableLookupError(
                    f"Could not find `{self.tablename}` in reflected or aliased tables."
                )
                raise e from err
            stmt = self._where(t, stmt, attr)
        return stmt


class FilterSet(Generic[FilterT]):
    def __init__(self, wheres: Iterable[WhereFilter[FilterT]]):
        """Builds up a sqla query statement with a given set of `wheres`.
        These are applied in the order that they are declared and the `stmt` will
        continue to mutate.

        Args:
            wheres (Iterable[WhereFilter[FilterT]]): An iterable of WhereFilters
        """
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


# Below are the most common where clauses for convenience


class WhereGE(WhereFilter[FilterT]):
    def _where(
        self,
        t: sa.Table | sa.TableValuedAlias,
        stmt: sa.Select[Any],
        attr: Any,
    ) -> sa.Select[Any]:
        return stmt.where(t.c[self.col] >= attr)


class WhereLE(WhereFilter[FilterT]):
    def _where(
        self,
        t: sa.Table | sa.TableValuedAlias,
        stmt: sa.Select[Any],
        attr: Any,
    ) -> sa.Select[Any]:
        return stmt.where(t.c[self.col] <= attr)


class WhereGT(WhereFilter[FilterT]):
    def _where(
        self,
        t: sa.Table | sa.TableValuedAlias,
        stmt: sa.Select[Any],
        attr: Any,
    ) -> sa.Select[Any]:
        return stmt.where(t.c[self.col] > attr)


class WhereLT(WhereFilter[FilterT]):
    def _where(
        self,
        t: sa.Table | sa.TableValuedAlias,
        stmt: sa.Select[Any],
        attr: Any,
    ) -> sa.Select[Any]:
        return stmt.where(t.c[self.col] < attr)


class WhereEquals(WhereFilter[FilterT]):
    def _where(
        self,
        t: sa.Table | sa.TableValuedAlias,
        stmt: sa.Select[Any],
        attr: Any,
    ) -> sa.Select[Any]:
        return stmt.where(t.c[self.col] == attr)


class WhereContains(WhereFilter[FilterT]):
    def _where(
        self,
        t: sa.Table | sa.TableValuedAlias,
        stmt: sa.Select[Any],
        attr: Any,
    ) -> sa.Select[Any]:
        return stmt.where(t.c[self.col].contains(attr))
