"""
This module provides interfaces and implementations of Controller classes to help with CRUD. 

We seperate the sqlalchemy statements from the business logic the statement operates on. 

This API should be flexible enough to CRUD against tables in a declarative style as well as 
handle more complex queries or CUD scenarios.

"""
from fastapi import HTTPException
from aiodal import dal
from . import models, auth, paginator, context

from typing import Generic, TypeVar, Any, TypeAlias
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError, IntegrityError

# abstract interfaces for queryable objects.
import abc

# see: https://github.com/cunybpl/aiodal/issues/17
from sqlalchemy.sql.dml import ReturningDelete, ReturningInsert, ReturningUpdate


SaRow = sa.Row[Any]
FormDataT = TypeVar("FormDataT")  # generic T used to handle form data
FilterDataT = TypeVar("FilterDataT")
_T = Any

SaReturningDelete: TypeAlias = ReturningDelete[_T]
SaReturningInsert: TypeAlias = ReturningInsert[_T]
SaReturningUpdate: TypeAlias = ReturningUpdate[_T]
SaSelect: TypeAlias = sa.Select[_T]


class IQueryable(abc.ABC, Generic[FilterDataT]):
    """enable a dbentity to be readable/query-able; works with QueryParamsModel which
    adds additonal where stmt to the output from query_stmt.

    This is taken directly from oqm but with the caveat that it is not constructible. If/when
    we revise oqm we will remove that constraint from this interface.
    """

    @abc.abstractmethod
    def query_stmt(
        self, transaction: dal.TransactionManager, where: FilterDataT
    ) -> SaSelect:
        ...


class IDeleteable(abc.ABC, Generic[FormDataT]):
    """Enable a dbentity to be deleteable"""

    @classmethod
    @abc.abstractmethod
    def delete_stmt(
        cls, transaction: dal.TransactionManager, data: FormDataT
    ) -> SaReturningDelete:
        ...  # pragma: no cover


class ICreatable(abc.ABC, Generic[FormDataT]):
    """enable a dbentity to be writable; takes a pydantic BaseForm model, which contains data to be inserted into db."""

    @classmethod
    @abc.abstractmethod
    def insert_stmt(
        cls, transaction: dal.TransactionManager, data: FormDataT
    ) -> SaReturningInsert:
        ...  # pragma: no cover


class IUpdateable(abc.ABC, Generic[FormDataT]):
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


class DetailController(Generic[models.ResourceModelT, auth.Auth0UserT]):
    def __init__(
        self,
        *,
        q: IQueryable[context.RequestContext[auth.Auth0UserT]],
        permissions: auth.IPermission | None = None,
    ):
        self.q = q
        self.permissions = permissions

    async def query(
        self,
        transaction: dal.TransactionManager,
        ctx: context.RequestContext[auth.Auth0UserT],
    ) -> sa.Row[Any]:
        if self.permissions:
            await self.permissions.check(transaction, ctx.user)

        stmt = self.q.query_stmt(transaction, where=ctx)
        res = await transaction.execute(stmt)
        result = res.one_or_none()

        if not result:
            raise HTTPException(status_code=404, detail="Not Found.")

        if ctx.soft_delete_handler:
            ctx.soft_delete_handler.status(result)

        if ctx.etag:
            ctx.etag.set_current_etag(ctx, result)

        return result


class UpdateController(Generic[auth.Auth0UserT]):
    def __init__(
        self,
        *,
        q: IUpdateable[context.RequestContext[auth.Auth0UserT]],
        permissions: auth.IPermission | None = None,
    ):
        self.q = q
        self.permissions = permissions

    async def update(
        self,
        transaction: dal.TransactionManager,
        ctx: context.RequestContext[auth.Auth0UserT],
    ) -> sa.Row[Any]:
        if self.permissions:
            await self.permissions.check(transaction, ctx.user)

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


class CreateController(Generic[auth.Auth0UserT]):
    def __init__(
        self,
        *,
        q: ICreatable[context.RequestContext[auth.Auth0UserT]],
        permissions: auth.IPermission | None = None,
    ):
        self.q = q
        self.permissions = permissions

    async def create(
        self,
        transaction: dal.TransactionManager,
        ctx: context.RequestContext[auth.Auth0UserT],
    ) -> sa.Row[Any]:
        if self.permissions:
            await self.permissions.check(transaction, ctx.user)

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
    def __init__(
        self,
        *,
        q: IDeleteable[context.RequestContext[auth.Auth0UserT]],
        permissions: auth.IPermission | None = None,
    ):
        self.q = q
        self.permissions = permissions

    async def delete(
        self,
        transaction: dal.TransactionManager,
        ctx: context.RequestContext[auth.Auth0UserT],
    ):
        if self.permissions:
            await self.permissions.check(transaction, ctx.user)

        stmt = self.q.delete_stmt(transaction, data=ctx)

        res = await transaction.execute(stmt)
        result = res.one_or_none()

        if not result:
            raise HTTPException(status_code=404, detail="Not Found.")


class ListViewController(Generic[auth.Auth0UserT]):
    def __init__(
        self,
        *,
        q: IQueryable[context.RequestContext[auth.Auth0UserT]],
        permissions: auth.IPermission | None = None,
    ):
        self.q = q
        self.permissions = permissions

    async def query(
        self,
        transaction: dal.TransactionManager,
        ctx: context.RequestContext[auth.Auth0UserT],
    ) -> paginator.ListViewData:
        if self.permissions:
            await self.permissions.check(transaction, ctx.user)

        # send the params wrapper into the generic where
        # should assure the QueryableT will have everything it needs
        stmt = self.q.query_stmt(transaction, where=ctx)
        result = await transaction.execute(stmt)

        return paginator.model_mapper(
            result,
            request_url=ctx.request_url,
            offset=ctx.query_param("offset"),
            limit=ctx.query_param("limit"),
        )
