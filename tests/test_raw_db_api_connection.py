from __future__ import annotations
from aiodal import dal
import pytest
import pathlib
import sqlalchemy as sa


pytestmark = pytest.mark.anyio
import asyncpg

# bulk upload some authors and books using jsonl
# we will load this in as rows of jsonb and then munge them into the correct tables
# authors will have their ids assigned... the book insert op will need to do a lookup on authors.

fixture_dir = pathlib.Path(__file__).parent / "fixtures"


async def test_raw_dbapi_connection(listschema_transaction):

    transaction: dal.TransactionManager = listschema_transaction

    apg_conn = await transaction.get_dbapi_connection()

    assert isinstance(apg_conn, asyncpg.Connection)

    # load using asyncpg connection copy
    async with apg_conn.transaction():
        stmt = """ 
        create temp table widgytemp (
            thing varchar, 
            n numeric 
        ) on commit drop;
"""
        result = await apg_conn.execute(stmt)

        result = await apg_conn.copy_to_table(
            "widgytemp",
            source=fixture_dir / "widgy.csv",
            format="csv",
            delimiter=",",
            header=True,
        )

        stmt = """
        insert into w.widgy(thing, n) select * from widgytemp;
"""

        await apg_conn.execute(stmt)

    # committed... query using transaction
    w = transaction.get_table("w.widgy")

    result = await transaction.execute(sa.select(w))

    assert len(result.fetchall()) > 0
