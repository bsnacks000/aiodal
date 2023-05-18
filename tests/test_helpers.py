import pytest
import sqlalchemy as sa

from aiodal import helpers

pytestmark = pytest.mark.anyio


async def test_json_serialize():
    ...


async def test_total_count(transaction):
    author = transaction.get_table("author")
    stmt = sa.insert(author).values(name="kgas").returning(author.c.id, author.c.name)
    result = await transaction.execute(stmt)
    assert result.one().name == "kgas"

    stmt = sa.select(author.c.id, author.c.name, helpers.sa_total_count(author.c.id))
    result = await transaction.execute(stmt)
    result = result.one()
    assert result.total_count == 1
