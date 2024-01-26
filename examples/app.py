from fastapi import FastAPI, HTTPException, Request, Depends, Security
from aiodal import dal, helpers
from aiodal.web import auth, context, controllers, models, paginator, version
import pydantic
import os
import contextlib
import logging

import uuid
from sqlalchemy.ext.asyncio import create_async_engine
import sqlalchemy as sa
from typing import List, AsyncIterator


from aiodal.web.controllers import SaReturningInsert, SaSelect

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


class ListViewQueryable(controllers.IListQueryable):
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


@app.get(
    "/book", response_model=BookListView, dependencies=[Depends(auth0.implicit_scheme)]
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


@app.post("/book")
async def create():
    ...


@app.get("/book/{id}")
async def get_book_detail():
    ...


@app.patch("/book/{id}")
async def patch_book():
    ...


@app.delete("/book/")
async def get_book():
    ...
