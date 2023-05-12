import pytest
import sqlalchemy as sa
import datetime

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
