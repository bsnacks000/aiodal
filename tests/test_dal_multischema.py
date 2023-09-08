import pytest
import sqlalchemy as sa
import datetime
from aiodal import dal, connect

pytestmark = pytest.mark.anyio


# multischema --> one named schema and one none schema
async def test_dal_basics_with_multischema(multischema_transaction):
    author = multischema_transaction.get_table("author")
    book = multischema_transaction.get_table("book")

    assert multischema_transaction.get_unique_constraint("book") == ["catalog"]

    stmt = (
        sa.insert(author).values(name="bsnacks").returning(author.c.id, author.c.name)
    )
    result = await multischema_transaction.execute(stmt)

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

    result = await multischema_transaction.execute(stmt)
    mybook = result.one()
    assert mybook.name == "some book"

    table1 = multischema_transaction.get_table("testschema1.table1")
    assert multischema_transaction.get_unique_constraint("testschema1.table1") == [
        "column1"
    ]

    stmt = (
        sa.insert(table1)
        .values(column1="tinbot")
        .returning(table1.c.id, table1.c.column1)
    )
    result = await multischema_transaction.execute(stmt)

    me = result.one()

    assert me.column1 == "tinbot"

    # testschema1.table2
    table2 = multischema_transaction.get_table("testschema1.table2")
    stmt = (
        sa.insert(table2)
        .values(
            table1_id=me.id,
            column2="some book",
        )
        .returning(table2.c.id, table2.c.column2)
    )

    result = await multischema_transaction.execute(stmt)
    table2_res = result.one()
    assert table2_res.column2 == "some book"

    with pytest.raises(KeyError):
        multischema_transaction.get_table("testschema2.table1")

    with pytest.raises(KeyError):
        multischema_transaction.get_table("table1")

    await multischema_transaction.rollback()
