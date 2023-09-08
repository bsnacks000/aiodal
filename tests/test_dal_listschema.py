import pytest
import sqlalchemy as sa
import datetime
from aiodal import dal, connect

pytestmark = pytest.mark.anyio


# a list of schema -- two named schema and one none schema
async def test_dal_basics_listschema(listschema_transaction):
    author = listschema_transaction.get_table("author")
    book = listschema_transaction.get_table("book")

    assert listschema_transaction.get_unique_constraint("book") == ["catalog"]

    stmt = (
        sa.insert(author).values(name="bsnacks").returning(author.c.id, author.c.name)
    )
    result = await listschema_transaction.execute(stmt)

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

    result = await listschema_transaction.execute(stmt)
    mybook = result.one()
    assert mybook.name == "some book"

    # testschema1
    table1 = listschema_transaction.get_table("testschema1.table1")
    assert listschema_transaction.get_unique_constraint("testschema1.table1") == [
        "column1"
    ]

    stmt = (
        sa.insert(table1)
        .values(column1="tinbot")
        .returning(table1.c.id, table1.c.column1)
    )
    result = await listschema_transaction.execute(stmt)

    me = result.one()

    assert me.column1 == "tinbot"

    # testschema2
    table2 = listschema_transaction.get_table("testschema2.table1")
    assert listschema_transaction.get_unique_constraint("testschema2.table1") == [
        "column3"
    ]

    stmt = (
        sa.insert(table2)
        .values(column3="kudibot")
        .returning(table2.c.id, table2.c.column3)
    )
    result = await listschema_transaction.execute(stmt)

    me = result.one()

    assert me.column3 == "kudibot"

    await listschema_transaction.rollback()
