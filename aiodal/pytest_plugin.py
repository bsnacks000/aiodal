from typing import Callable, Any, AsyncIterator
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from .dal import DataAccessLayer, TransactionManager
from . import helpers

import pytest

import logging

logger = logging.getLogger(__name__)


import dataclasses

JsonSerializerT = Callable[[Any], str]


@pytest.fixture(scope="session")
def json_serializer() -> JsonSerializerT:
    """Override this to change what function you want to use for json_serializer"""
    return helpers.json_serializer


@dataclasses.dataclass
class TestConfig:
    engine: AsyncEngine


@pytest.fixture(scope="session")
def postgres_testdb_uri() -> str:
    return ""


@pytest.fixture(scope="session")
def engine_echo() -> bool:
    return False


@pytest.fixture(scope="session")
def async_engine(
    postgres_testdb_uri: str, engine_echo: bool, json_serializer: JsonSerializerT
) -> AsyncEngine:
    return create_async_engine(
        url=postgres_testdb_uri,
        echo=engine_echo,
        json_serializer=json_serializer,
    )


@pytest.fixture(scope="session")
async def db(async_engine: AsyncEngine) -> AsyncIterator[DataAccessLayer]:
    """Create the database and mirate using an os call to alembic.
    Setup the database internals and seed critical data.
    Yield the DataAccessLayer object for the rest of the tests.

    """

    try:
        db = DataAccessLayer()

        await db.reflect(async_engine)
        yield db
    except Exception as err:
        logger.exception(err)
    finally:
        await async_engine.dispose()


@pytest.fixture
async def transaction(db: DataAccessLayer) -> AsyncIterator[TransactionManager]:
    """auto rollback. Used by get_transaction to create isolation in tests."""
    async with db.engine.connect() as conn:
        transaction = TransactionManager(conn, db)
        try:
            yield transaction
        finally:
            await transaction.rollback()
