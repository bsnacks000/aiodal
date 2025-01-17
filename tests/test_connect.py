import pytest
from sqlalchemy.exc import SQLAlchemyError
from unittest.mock import AsyncMock
from aiodal import connect

pytestmark = pytest.mark.anyio


async def test_connect_module(mocker):
    mocked = mocker.patch.object(connect, "connect", new_callable=AsyncMock)

    # Basic test
    await connect.or_fail(url="abc123")

    # make sure it rasise error without manual assertion
    with pytest.raises(AssertionError):
        mocked.assert_awaited_once_with("abc124", None, True)

    mocked.assert_awaited_once_with("abc123", None, True)

    mocked.reset_mock()

    # # Ensure engine options are propagated correctly
    await connect.or_fail(url="abc123", engine_option_1="test")
    mocked.assert_awaited_once_with("abc123", None, True, engine_option_1="test")

    mocked.reset_mock()

    # Check that SQLAlchemyErrors are propagated correctly
    mocked.side_effect = SQLAlchemyError
    with pytest.raises(SQLAlchemyError):
        await connect.or_fail(url="abc123", with_exit=False)
        mocked.assert_awaited_once_with()

    # Check that SQLAlchemyErrors generate a sys.exit if with_exit is not False
    mocked.side_effect = SQLAlchemyError
    with pytest.raises(SystemExit):
        await connect.or_fail(url="abc123")
