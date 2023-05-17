import pytest
from sqlalchemy.exc import SQLAlchemyError

from aiodal import connect

pytestmark = pytest.mark.anyio


async def test_connect_module(mocker):
    mocked = mocker.patch.object(connect, "connect")

    # Basic test
    await connect.or_fail(url="abc123")
    assert await mocked.called_once()
    assert await mocked.called_with(url="abc123")

    mocked.reset_mock()

    # Ensure engine options are propagated correctly
    await connect.or_fail(url="abc123", engine_option_1="test")
    assert await mocked.called_once()
    assert await mocked.called_with(url="abc123", engine_option_1="test")

    mocked.reset_mock()

    # Check that SQLAlchemyErrors are propagated correctly
    mocked.side_effect = SQLAlchemyError
    with pytest.raises(SQLAlchemyError):
        await connect.or_fail(url="abc123", with_exit=False)
    assert await mocked.called_once()

    # Check that SQLAlchemyErrors generate a sys.exit if with_exit is not False
    mocked.side_effect = SQLAlchemyError
    with pytest.raises(SystemExit):
        await connect.or_fail(url="abc123")
