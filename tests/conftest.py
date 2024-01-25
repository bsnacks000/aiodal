import pytest
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncEngine
from typing import AsyncIterator
from aiodal.dal import DataAccessLayer, TransactionManager
import logging

logger = logging.getLogger(__file__)

POSTGRES_TEST_URI = "postgresql+asyncpg://bsnacks000:iamgroot666@pgdb:5432/testdb"
POSTGRES_ASYNCPG_TEST_URI = "postgresql://bsnacks000:iamgroot666@pgdb:5432/testdb"


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
