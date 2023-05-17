import pytest
import sqlalchemy as sa
import datetime
from aiodal import dal, connect

pytestmark = pytest.mark.anyio


async def test_dal_basics(transaction):
    author = transaction.get_table("author")
    book = transaction.get_table("book")

    assert transaction.get_unique_constraint("book") == ["catalog"]

    stmt = (
        sa.insert(author).values(name="bsnacks").returning(author.c.id, author.c.name)
    )
    result = await transaction.execute(stmt)

    me = result.one()

    assert me.name == "bsnacks"
    stmt = (
        sa.insert(book)
        .values(
            author_id=me.id,
            name="some book",
            catalog="123abc",
            extra={"some": "value", "date": datetime.datetime.now().date()},
        )
        .returning(book.c.id, book.c.name)
    )

    result = await transaction.execute(stmt)
    mybook = result.one()
    assert mybook.name == "some book"

    await transaction.rollback()


async def test_dal_setters_getters(engine_uri, transaction):
    db = await connect.or_fail(url=engine_uri, with_exit=False)
    tablename = "Table name"
    value = "Testing value"

    db.set_aliased(name=tablename, t=value)
    assert db._aliased_tables[tablename] == value
    assert db.get_aliased(name=tablename) == value

    transaction.set_aliased(name=tablename, t=value)
    assert transaction._aliased_tables[tablename] == value
    assert transaction.get_aliased(name=tablename) == value

    with pytest.raises(KeyError):
        transaction.get_aliased(name="nonexistent table")

    author_table = db.get_table("author")
    assert author_table is not None

    with pytest.raises(KeyError):
        db.get_table("nonexistent table")

    book_constraint = db.get_unique_constraint("book")
    assert book_constraint == ["catalog"]
