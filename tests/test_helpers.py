import pytest
import sqlalchemy as sa
import datetime

from aiodal import helpers

pytestmark = pytest.mark.anyio


async def test_json_serialize(testing_enum):
    data = {
        "red": testing_enum.RED,
        "blue": testing_enum.BLUE,
        "green": testing_enum.GREEN,
    }
    serialized = helpers.json_serializer(data)
    expected = '{"red": 1, "blue": 2, "green": 3}'
    assert serialized == expected

    data = {"date": datetime.datetime(2020, 1, 1).date()}
    serialized = helpers.json_serializer(data)
    expected = '{"date": "2020-01-01"}'
    assert serialized == expected


async def test_total_count(transaction):
    author = transaction.get_table("author")
    stmt = sa.insert(author).values(name="kgas").returning(author.c.id, author.c.name)
    result = await transaction.execute(stmt)
    assert result.one().name == "kgas"

    stmt = sa.select(author.c.id, author.c.name, helpers.sa_total_count(author.c.id))
    result = await transaction.execute(stmt)
    result = result.one()
    assert result.total_count == 1
