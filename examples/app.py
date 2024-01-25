from fastapi import FastAPI
from aiodal import dal
from aiodal.web import auth, context, controllers, models, paginator, version

import pydantic
import os
import contextlib

from sqlalchemy.ext.asyncio import create_async_engine
import sqlalchemy as sa
import uvicorn

ASYNCPG_POSTGRES_URI = os.environ.get("ASYNCPG_POSTGRES_URL", "")
AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN", "")
AUTH0_API_AUDIENCE = os.environ.get("AUTH0_API_AUDIENCE", "")


class ExampleUser(auth.Auth0User):
    ...


auth0 = auth.Auth0(
    domain=AUTH0_DOMAIN, api_audience=AUTH0_API_AUDIENCE, user_model=ExampleUser
)

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


@app.get("/book")
async def get_book_list():
    ...


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


if __name__ == "__main__":
    uvicorn
