from typing import Callable, Any, AsyncIterator, Dict
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from .dal import DataAccessLayer, TransactionManager
from . import helpers

import pytest
import logging

logger = logging.getLogger(__file__)

JsonSerializerT = Callable[[Any], str]


@pytest.fixture(scope="session")
def engine_json_serializer() -> JsonSerializerT:
    """Override this to return a custom json serializer function for the
    engine to use for working with json/jsonb data.

    Returns:
        JsonSerializerT: Wrapper function around json.dumps
    """
    return helpers.json_serializer


@pytest.fixture(scope="session")
def engine_uri() -> str:
    """Override this and return a string for sqlalchemy

    Returns:
        str: The engine uri (including db driver etc.)
    """
    return ""


@pytest.fixture(scope="session")
def engine_echo() -> bool:
    """Override to set whether you want the engine to log calls during tests.

    Returns:
        bool: echo or not
    """
    return False


@pytest.fixture(scope="session")
def engine_extra_kwargs() -> Dict[str, Any]:
    """Any extra kwargs for the engine you want for your tests. Defaults to empty.

    Returns:
        Dict[str, Any]: Extra engine kwargs.
    """
    return {"json_serializer": helpers.json_serializer, "echo": False}


@pytest.fixture(scope="session")
def async_engine(
    engine_uri: str,
    engine_extra_kwargs: Dict[str, Any],
) -> AsyncEngine:
    return create_async_engine(url=engine_uri, **engine_extra_kwargs)


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
