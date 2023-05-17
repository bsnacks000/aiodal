import pytest

import sqlalchemy as sa
from aiodal import mixins, dal
from typing import Any, Optional

from dataclasses import dataclass


async def author_list(
    transaction: dal.TransactionManager, where: Optional[mixins.Where] = None
) -> sa.CursorResult:
    t = transaction.get_table("author")

    stmt = sa.select(t)

    if where is not None:
        names = where.get("names")
        if names:
            stmt = stmt.where(t.c.name.in_(names))
    return await transaction.execute(stmt)


async def author_insert_one(
    transaction: dal.TransactionManager, data: mixins.RecordT
) -> sa.Row[Any]:
    t = transaction.get_table("author")
    stmt = sa.insert(t).values(**data).returning(t)
    result = await transaction.execute(stmt)
    return result.one()


async def author_delete_many(transaction: dal.TransactionManager) -> None:
    t = transaction.get_table("author")
    stmt = sa.insert(t).values


@dataclass
class Author(mixins.ListQ, mixins.InsertDetailQ):
    id: int
    name: str

    __list_query__ = author_list
    __insert_detail_query__ = author_insert_one


@pytest.mark.anyio
async def test_mixins(transaction):
    _ = await Author.insert_one(transaction, {"name": "aaron"})
    _ = await Author.insert_one(transaction, {"name": "bob"})
    _ = await Author.insert_one(transaction, {"name": "cath"})
    _ = await Author.insert_one(transaction, {"name": "doug"})

    result = await transaction.execute(sa.select(transaction.get_table("author")))
    assert len(result.all()) == 4

    authors = await Author.list(transaction, {"names": ["bob", "cath"]})
    assert len(authors) == 2

    await transaction.rollback()  # adding this so that inserting here does not affect other test
