import pytest
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncEngine
from typing import AsyncIterator
from aiodal.dal import DataAccessLayer, TransactionManager
import logging
import sqlalchemy as sa
from . import crudapp
import json
import pathlib

logger = logging.getLogger(__file__)

POSTGRES_TEST_URI = "postgresql+asyncpg://postgres:postgres@pgdb:5432/testdb"
POSTGRES_ASYNCPG_TEST_URI = "postgresql://postgres:postgres@pgdb:5432/testdb"


FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures"


# NOTE must add this to local scope
@pytest.fixture(scope="session")
def anyio_backend():
    """Override this to use a different backend for testing"""
    return "asyncio"


@pytest.fixture(scope="session")
def engine_uri() -> str:
    return POSTGRES_TEST_URI


@pytest.fixture(scope="session")
def asyncpg_engine_uri() -> str:
    return POSTGRES_ASYNCPG_TEST_URI


class TestingEnum(Enum):
    RED = 1
    BLUE = 2
    GREEN = 3


@pytest.fixture(scope="session")
def testing_enum() -> TestingEnum:
    return TestingEnum


@pytest.fixture(scope="module")
async def multischema_db(async_engine: AsyncEngine) -> AsyncIterator[DataAccessLayer]:
    """Create the database and mirate using an os call to alembic.
    Setup the database internals and seed critical data.
    Yield the DataAccessLayer object for the rest of the tests.

    """

    try:
        db = DataAccessLayer()
        await db.reflect(async_engine, schema="testschema1")
        yield db
    except Exception as err:
        logger.exception(err)
    finally:
        await async_engine.dispose()


@pytest.fixture(scope="module")
async def multischema_transaction(
    multischema_db: DataAccessLayer,
) -> AsyncIterator[TransactionManager]:
    """auto rollback. Used by get_transaction to create isolation in tests."""
    async with multischema_db.engine.connect() as conn:
        transaction = TransactionManager(conn, multischema_db)
        try:
            yield transaction
        finally:
            await transaction.rollback()


@pytest.fixture(scope="module")
async def listschema_db(async_engine: AsyncEngine) -> AsyncIterator[DataAccessLayer]:
    """Create the database and mirate using an os call to alembic.
    Setup the database internals and seed critical data.
    Yield the DataAccessLayer object for the rest of the tests.

    """

    try:
        db = DataAccessLayer()
        await db.reflect(async_engine, schema=["testschema1", "testschema2"])
        yield db
    except Exception as err:
        logger.exception(err)
    finally:
        await async_engine.dispose()


@pytest.fixture(scope="module")
async def listschema_transaction(
    listschema_db: DataAccessLayer,
) -> AsyncIterator[TransactionManager]:
    """auto rollback. Used by get_transaction to create isolation in tests."""
    async with listschema_db.engine.connect() as conn:
        transaction = TransactionManager(conn, listschema_db)
        try:
            yield transaction
        finally:
            await transaction.rollback()


# fixtures for crudapp
@pytest.fixture(scope="module")
def module_get_user():
    """override dep injector"""

    async def _get_user():
        return crudapp.ExampleUser(
            sub="tinbot", email="tinbot@bot.com", org_name="world", org_id="1"
        )

    return _get_user


@pytest.fixture(scope="module")
async def module_transaction(db):
    """auto rollback. Module level isolation"""
    async with db.engine.connect() as conn:
        transaction = TransactionManager(conn, db)
        try:
            yield transaction
        finally:
            await transaction.rollback()


@pytest.fixture(scope="module")
def module_get_transaction(module_transaction):
    """override dep injector"""

    async def _get_test_transaction():
        return module_transaction

    return _get_test_transaction


@pytest.fixture(scope="module")
def module_test_app(module_get_transaction, module_get_user):
    crudapp.app.dependency_overrides[crudapp.get_transaction] = module_get_transaction
    crudapp.app.dependency_overrides[crudapp.auth0.get_user] = module_get_user
    yield crudapp.app
    crudapp.app.dependency_overrides = {}


@pytest.fixture(scope="module")
async def module_authors(module_transaction):
    author_data = [{"name": "Hep"}, {"name": "Tup"}, {"name": "Pup"}]
    tab = module_transaction.get_table("author")
    stmt = (
        sa.insert(tab)
        .values([{**rec, "id": i} for i, rec in enumerate(author_data, start=1)])
        .returning(tab)
    )
    await module_transaction.execute(stmt)


@pytest.fixture(scope="module")
async def module_books(module_transaction):
    book_data = [
        {"author_id": 1, "name": "Gone with the Fin", "catalog": "Boring"},
        {"author_id": 2, "name": "Needless Things", "catalog": "Really Boring"},
        {"author_id": 3, "name": "War of the Zorlds", "catalog": "Exciting"},
    ]
    tab = module_transaction.get_table("book")
    stmt = (
        sa.insert(tab)
        .values([{**rec, "id": i} for i, rec in enumerate(book_data, start=1)])
        .returning(tab)
    )
    await module_transaction.execute(stmt)
