import pytest
from aiodal import helpers
from aiodal.dal import TransactionManager, DataAccessLayer
from sqlalchemy.ext.asyncio.engine import AsyncEngine

pytestmark = pytest.mark.anyio


async def test_pytest_fixtures(
    engine_json_serializer,
    engine_echo,
    engine_extra_kwargs,
    async_engine,
    db,
    transaction,
):
    assert engine_json_serializer == helpers.json_serializer
    assert engine_echo == False
    assert engine_extra_kwargs == {
        "json_serializer": helpers.json_serializer,
        "echo": False,
    }
    assert isinstance(async_engine, AsyncEngine)
    assert isinstance(db, DataAccessLayer)
    assert isinstance(transaction, TransactionManager)
