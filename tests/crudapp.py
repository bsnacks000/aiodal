# example crud app to test out aiodal.web module functionalities
from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    Depends,
    Security,
    Header,
    Body,
    Response,
)
from sqlalchemy.engine import Row as Row
from aiodal import dal, helpers
from aiodal.web import auth, context, controllers, models, paginator, version
import pydantic
import os
import contextlib
import logging

import uuid
from sqlalchemy.ext.asyncio import create_async_engine
import sqlalchemy as sa
from typing import Any, Coroutine, List, AsyncIterator, Annotated


from aiodal.web.controllers import (
    SaReturningInsert,
    SaReturningUpdate,
    SaSelect,
    SaReturningDelete,
)


# dummy env example set up
ASYNCPG_POSTGRES_URI = os.environ.get("ASYNCPG_POSTGRES_URL", "")
AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN", "")
AUTH0_API_AUDIENCE = os.environ.get("AUTH0_API_AUDIENCE", "")

# set up an auth0 user


class ExampleUser(auth.Auth0User):
    ...


auth0 = auth.Auth0(
    domain=AUTH0_DOMAIN, api_audience=AUTH0_API_AUDIENCE, user_model=ExampleUser
)


# set up permissions for this user


db = dal.DataAccessLayer()


# new way to do startup
@contextlib.asynccontextmanager
async def startup(_: FastAPI):  # configure and load postgres
    engine = create_async_engine(ASYNCPG_POSTGRES_URI)
    metadata = sa.MetaData()
    auth0.initialize_jwks()
    await db.reflect(engine, metadata)
    yield


app = FastAPI(lifespan=startup)
models.ApiBaseModel.init_app(app)


class Author(models.ResourceModel):
    name: str


# declare some models
class Book(models.ResourceModel):
    id: int
    author_id: int
    name: str
    catalog: str
    etag_version: uuid.UUID


class BookListView(models.ListViewModel[Book]):
    results: List[Book]


# dependencies
async def get_transaction() -> AsyncIterator[dal.TransactionManager]:
    async with db.engine.connect() as conn:
        transaction = dal.TransactionManager(conn, db)
        try:
            yield transaction
            await transaction.commit()
        except HTTPException as err:
            await transaction.rollback()
            raise
        except Exception as err:
            logging.exception(err)
            await transaction.rollback()
            raise HTTPException(status_code=500, detail="Server Error.")


class BookQueryParams(models.ListViewQueryParamsModel):
    ...


class BookUpdateForm(models.FormModel):
    name: str | None = None
    author_id: int | None = None


class BookCreateForm(models.FormModel):
    author_id: int
    name: str
    catalog: str


# need a dummy form here to make it work with update context; this is not a true delete.
class BookDeleteForm(models.FormModel):
    deleted: bool = True


# an example of doing this generically...
class ListViewQueryable(
    controllers.IListQueryable[models.ListViewQueryParamsModelT, auth.Auth0UserT]
):
    def __init__(self, t: str):
        self.t = t

    def query_stmt(
        self,
        transaction: dal.TransactionManager,
        where: context.ListContext[models.ListViewQueryParamsModelT, auth.Auth0UserT],
    ) -> SaSelect:
        t = transaction.get_table(self.t)
        stmt = sa.select(t, helpers.sa_total_count(t.c.id)).order_by(t.c.id)

        viewable_authors = where.user.get_permissions()

        if viewable_authors is not None:
            stmt = stmt.where(t.c.author_id.in_(viewable_authors))
        return stmt


class CreateQueryable(controllers.ICreatable):
    def __init__(self, t: str):
        self.t = t

    def insert_stmt(
        self,
        transaction: dal.TransactionManager,
        data: context.CreateContext[models.FormModelT, auth.Auth0UserT],
    ) -> SaReturningInsert:
        t = transaction.get_table(self.t)
        stmt = sa.insert(t).values(**data.form.model_dump()).returning(t)
        return stmt


class DetailQueryable(controllers.IDetailQueryable):
    def __init__(self, t: str):
        self.t = t

    def query_stmt(
        self,
        transaction: dal.TransactionManager,
        where: context.DetailContext[auth.Auth0UserT],
    ) -> SaSelect:
        assert where.params is not None
        obj_id = where.params.get("id")
        t = transaction.get_table(self.t)
        stmt = sa.select(t).where(t.c.id == obj_id)
        return stmt


class OptLockQueryable(controllers.IVersionDetailQueryable):
    def __init__(self, t: str):
        self.t = t

    def query_stmt(
        self,
        transaction: dal.TransactionManager,
        where: context.UpdateContext[models.FormModelT, auth.Auth0UserT],
    ) -> SaSelect:
        assert where.params is not None
        obj_id = where.params.get("id")
        t = transaction.get_table(self.t)
        stmt = sa.select(t.c.id, t.c.etag_version, t.c.deleted).where(t.c.id == obj_id)
        return stmt


class UpdateQueryable(controllers.IUpdateable):
    def __init__(self, t: str):
        self.t = t

    def update_stmt(
        self,
        transaction: dal.TransactionManager,
        data: context.UpdateContext[models.FormModelT, auth.Auth0UserT],
    ) -> SaReturningUpdate:
        assert data.params is not None
        obj_id = data.params.get("id")

        new_etag = data.etag.new_etag
        curr_etag = data.etag.current_etag

        t = transaction.get_table(self.t)

        stmt = (
            sa.update(t)
            .values(
                {
                    "etag_version": new_etag,
                    **data.form.model_dump(exclude_unset=True),
                }
            )
            .where(t.c.id == obj_id)
            .where(t.c.etag_version == curr_etag)
            .returning(t)
        )

        return stmt


class SoftDeleteQueryable(controllers.IUpdateable):
    def __init__(self, t: str):
        self.t = t

    def update_stmt(
        self,
        transaction: dal.TransactionManager,
        data: context.UpdateContext[models.FormModelT, auth.Auth0UserT],
    ) -> SaReturningUpdate:
        assert data.params is not None
        obj_id = data.params.get("id")

        new_etag = data.etag.new_etag
        curr_etag = data.etag.current_etag

        t = transaction.get_table(self.t)

        stmt = (
            sa.update(t)
            .values(
                {
                    "etag_version": new_etag,
                    "deleted": True,
                }
            )
            .where(t.c.id == obj_id)
            .where(t.c.deleted == False)
            .where(t.c.etag_version == curr_etag)
            .returning(t)
        )

        return stmt


class DeleteQueryable(controllers.IDeleteable):
    def __init__(self, t: str):
        self.t = t

    def delete_stmt(
        self,
        transaction: dal.TransactionManager,
        data: context.DetailContext[auth.Auth0UserT],
    ) -> SaReturningDelete:
        assert data.params is not None
        obj_id = data.params.get("id")
        t = transaction.get_table(self.t)
        stmt = sa.delete(t).where(t.c.id == obj_id).returning(t)
        return stmt


@app.get(
    "/book",
    dependencies=[Depends(auth0.implicit_scheme)],
)
async def get_book_list(
    request: Request,
    params: BookQueryParams = Depends(),
    user: ExampleUser = Security(auth0.get_user),
    transaction: dal.TransactionManager = Depends(get_transaction),
) -> BookListView:
    ctx = context.ListContext(user=user, request=request, query_params=params)
    data = await controllers.ListViewController(q=ListViewQueryable("book")).query(
        transaction, ctx
    )
    return BookListView.model_validate(data)


@app.post("/book", dependencies=[Depends(auth0.implicit_scheme)], status_code=201)
async def create_book(
    request: Request,
    form: BookCreateForm,
    user: ExampleUser = Security(auth0.get_user),
    transaction: dal.TransactionManager = Depends(get_transaction),
) -> Book:
    ctx = context.CreateContext(user=user, request=request, form=form)
    data = await controllers.CreateController(q=CreateQueryable("book")).create(
        transaction, ctx
    )
    return Book.model_validate(data)


import uuid


def if_match_header(if_match: uuid.UUID = Header()):
    return if_match


@app.patch("/book/{id}", dependencies=[Depends(if_match_header)])
@version.set_etag_on_response_coroutine
async def patch_book(
    request: Request,
    response: Response,
    id: int,
    form: BookUpdateForm,
    user: ExampleUser = Security(auth0.get_user),
    transaction: dal.TransactionManager = Depends(get_transaction),
) -> Book:
    # optimistic locking pattern ...
    ctx = context.UpdateContext(
        user=user,
        request=request,
        form=form,
        etag=version.EtagHandler(),
        params={"id": id},
    )

    # this is only used to set the etag on the context
    # a pessimistic version might get a lock
    _ = await controllers.VersionDetailController(
        q=OptLockQueryable("book"), soft_deleted_field="deleted"
    ).query(transaction, ctx)

    data = await controllers.UpdateController(q=UpdateQueryable("book")).update(
        transaction, ctx
    )

    return Book.model_validate(data)


@app.get(
    "/book/{id}", dependencies=[Depends(auth0.implicit_scheme)], response_model=Book
)
async def get_book_detail(
    id: int,
    request: Request,
    user: ExampleUser = Security(auth0.get_user),
    transaction: dal.TransactionManager = Depends(get_transaction),
) -> Book:
    ctx = context.DetailContext(user=user, request=request, params={"id": id})
    data = await controllers.DetailController(
        q=DetailQueryable("book"), soft_deleted_field="deleted"
    ).query(transaction, ctx)

    return Book.model_validate(data)


@app.delete(
    "/book/{id}",
    status_code=204,
    response_class=Response,
    dependencies=[Depends(if_match_header)],
)
async def delete_book(
    id: int,
    request: Request,
    user: ExampleUser = Security(auth0.get_user),
    transaction: dal.TransactionManager = Depends(get_transaction),
) -> None:
    ctx = context.DetailContext(user=user, request=request, params={"id": id})
    await controllers.DeleteController(q=DeleteQueryable("book")).delete(
        transaction, ctx
    )
    return None


@app.delete(
    "/book/{id}/soft_delete/",
    status_code=204,
    response_class=Response,
    dependencies=[Depends(if_match_header)],
)
async def soft_delete_book(
    id: int,
    request: Request,
    user: ExampleUser = Security(auth0.get_user),
    transaction: dal.TransactionManager = Depends(get_transaction),
) -> None:
    ctx = context.UpdateContext(
        user=user,
        request=request,
        form=BookDeleteForm(),  # dummy form
        etag=version.EtagHandler(),
        params={"id": id},
    )

    # this is only used to set the etag on the context
    # a pessimistic version might get a lock
    _ = await controllers.VersionDetailController(
        q=OptLockQueryable("book"), soft_deleted_field="deleted"
    ).query(transaction, ctx)

    data = await controllers.UpdateController(q=SoftDeleteQueryable("book")).update(
        transaction, ctx
    )

    return None
