"""
This module provides interfaces and implementations of Controller classes to help with CRUD. 

We seperate the sqlalchemy statements from the business logic the statement operates on. 

This API should be flexible enough to CRUD against tables in a declarative style as well as 
handle more complex queries or CUD scenarios.

"""
from fastapi import HTTPException
from aiodal import dal
from . import models, auth, paginator, context

from typing import Generic, Any, TypeAlias
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError, IntegrityError

# abstract interfaces for queryable objects.
import abc

# see: https://github.com/cunybpl/aiodal/issues/17
from sqlalchemy.sql.dml import ReturningDelete, ReturningInsert, ReturningUpdate

_T = Any
SaRow = sa.Row[_T]
SaReturningDelete: TypeAlias = ReturningDelete[_T]
SaReturningInsert: TypeAlias = ReturningInsert[_T]
SaReturningUpdate: TypeAlias = ReturningUpdate[_T]
SaSelect: TypeAlias = sa.Select[_T]


class IListQueryable(abc.ABC):
    @abc.abstractmethod
    def query_stmt(
        self,
        transaction: dal.TransactionManager,
        where: context.ListContext[models.ListViewQueryParamsModelT, auth.Auth0UserT],
    ) -> SaSelect:
        ...


class IDetailQueryable(abc.ABC):
    @abc.abstractmethod
    def query_stmt(
        self,
        transaction: dal.TransactionManager,
        where: context.DetailContext[auth.Auth0UserT],
    ) -> SaSelect:
        ...


class IVersionDetailQueryable(abc.ABC):
    @abc.abstractmethod
    def query_stmt(
        self,
        transaction: dal.TransactionManager,
        where: context.UpdateContext[models.FormModelT, auth.Auth0UserT],
    ) -> SaSelect:
        ...


class IDeleteable(abc.ABC):
    @abc.abstractmethod
    def delete_stmt(
        self,
        transaction: dal.TransactionManager,
        data: context.DetailContext[auth.Auth0UserT],
    ) -> SaReturningDelete:
        ...  # pragma: no cover


class ICreatable(abc.ABC):
    @abc.abstractmethod
    def insert_stmt(
        self,
        transaction: dal.TransactionManager,
        data: context.CreateContext[models.FormModelT, auth.Auth0UserT],
    ) -> SaReturningInsert:
        ...  # pragma: no cover


class IUpdateable(abc.ABC):
    @abc.abstractmethod
    def update_stmt(
        self,
        transaction: dal.TransactionManager,
        data: context.UpdateContext[models.FormModelT, auth.Auth0UserT],
    ) -> SaReturningUpdate:
        ...  # pragma: no cover


class DetailController:
    def __init__(self, *, q: IDetailQueryable, soft_deleted_field: str | None = None):
        self.q = q
        self.soft_deleted_field = soft_deleted_field

    async def query(
        self,
        transaction: dal.TransactionManager,
        ctx: context.DetailContext[auth.Auth0UserT],
    ) -> sa.Row[Any]:
        stmt = self.q.query_stmt(transaction, where=ctx)
        res = await transaction.execute(stmt)
        result = res.one_or_none()

        if not result:
            raise HTTPException(status_code=404, detail="Not Found.")

        if self.soft_deleted_field:
            if getattr(result, self.soft_deleted_field):
                raise HTTPException(status_code=410, detail="Gone.")

        return result


class VersionDetailController:
    def __init__(
        self, *, q: IVersionDetailQueryable, soft_deleted_field: str | None = None
    ):
        self.q = q
        self.soft_deleted_field = soft_deleted_field

    async def query(
        self,
        transaction: dal.TransactionManager,
        ctx: context.UpdateContext[models.FormModelT, auth.Auth0UserT],
    ) -> sa.Row[Any]:
        stmt = self.q.query_stmt(transaction, where=ctx)
        res = await transaction.execute(stmt)
        result = res.one_or_none()

        if not result:
            raise HTTPException(status_code=404, detail="Not Found.")

        if self.soft_deleted_field:
            if getattr(result, self.soft_deleted_field):
                raise HTTPException(status_code=410, detail="Gone.")

        ctx.etag.set_current(ctx.request.headers, result)

        return result


class UpdateController:
    def __init__(self, *, q: IUpdateable):
        self.q = q

    async def update(
        self,
        transaction: dal.TransactionManager,
        ctx: context.UpdateContext[models.FormModelT, auth.Auth0UserT],
    ) -> SaRow:
        stmt = self.q.update_stmt(transaction, data=ctx)

        try:
            res = await transaction.execute(stmt)

        except IntegrityError:
            raise HTTPException(status_code=409, detail="Conflict.")

        except DBAPIError as err:
            message = str(err.orig).split(":")[-1]
            raise HTTPException(status_code=409, detail=f"Conflict. {message}")

        result = res.one_or_none()

        if not result:
            raise HTTPException(status_code=409, detail="Stale Data.")

        return result


class CreateController:
    def __init__(self, *, q: ICreatable):
        self.q = q

    async def create(
        self,
        transaction: dal.TransactionManager,
        ctx: context.CreateContext[models.FormModelT, auth.Auth0UserT],
    ) -> SaRow:
        stmt = self.q.insert_stmt(transaction, data=ctx)

        try:
            res = await transaction.execute(stmt)

        except IntegrityError:
            raise HTTPException(status_code=409, detail="Conflict.")

        except DBAPIError as err:
            message = str(err.orig).split(":")[-1]
            raise HTTPException(status_code=409, detail=f"Conflict. {message}")

        result = res.one()

        return result


class DeleteController(Generic[auth.Auth0UserT]):
    def __init__(self, *, q: IDeleteable):
        self.q = q

    async def delete(
        self,
        transaction: dal.TransactionManager,
        ctx: context.DetailContext[auth.Auth0UserT],
    ) -> None:
        stmt = self.q.delete_stmt(transaction, data=ctx)

        res = await transaction.execute(stmt)
        result = res.one_or_none()

        if not result:
            raise HTTPException(status_code=404, detail="Not Found.")


class ListViewController:
    def __init__(self, *, q: IListQueryable):
        self.q = q

    async def query(
        self,
        transaction: dal.TransactionManager,
        ctx: context.ListContext[models.ListViewQueryParamsModelT, auth.Auth0UserT],
    ) -> paginator.ListViewData:
        # send the params wrapper into the generic where
        # should assure the QueryableT will have everything it needs
        stmt = self.q.query_stmt(transaction, where=ctx)
        result = await transaction.execute(stmt)

        return paginator.model_mapper(
            result,
            request_url=ctx.request_url,
            offset=ctx.query_params.offset,
            limit=ctx.query_params.limit,
        )
