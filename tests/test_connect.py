import pytest
import sqlalchemy as sa

from aiodal import connect

pytestmark = pytest.mark.anyio


async def test_connect_module(mocker):
    print(mocker)

    # kwargs = {"url": "http://www.google.com/"}
    # db = await connect.or_fail(**kwargs)
