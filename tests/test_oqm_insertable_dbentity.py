from aiodal.oqm import query, filters, dbentity
from aiodal import dal
import sqlalchemy as sa
from typing import Any, Dict
import dataclasses
import pytest

pytestmark = pytest.mark.anyio


@dataclasses.dataclass
class BookForm:
    author_name: str
    name: str
    catalog: str
    extra: Dict[str, Any] = dataclasses.field(default_factory=lambda: {})


@dataclasses.dataclass
class InsertableBookDBEntity(dbentity.Insertable[BookForm]):
    id: int = 0  # <-- inherit from DBEntity, parent of InsertableDBEntity
    author_id: int = 0
    name: str = ""
    catalog: str = ""
    extra: dict[str, Any] = dataclasses.field(default_factory=lambda: {})

    @classmethod
    def insert_stmt(
        cls, transaction: dal.TransactionManager, data: BookForm
    ) -> dbentity.ReturningInsert:
        t = transaction.get_table("book")
        author_table = transaction.get_table("author")
        author_id_subq = (
            sa.select(author_table.c.id)
            .where(author_table.c.name == data.author_name)
            .scalar_subquery()
        )
        stmt = (
            sa.insert(t)
            .values(
                author_id=author_id_subq,
                name=data.name,
                catalog=data.catalog,
                extra=data.extra,
            )
            .returning(t)
        )
        return stmt


class BookInsertQ(query.InsertQ[InsertableBookDBEntity, BookForm]):
    __db_obj__ = InsertableBookDBEntity


async def test_dbentity_insert_stmt(transaction):
    author = transaction.get_table("author")

    stmt = sa.insert(author).values(**{"name": "author1"}).returning(author)
    result = await transaction.execute(stmt)
    author1 = result.one()

    data = BookForm(
        author_name=author1.name,
        name="Lord of the Tables",
        catalog="pg_catalog",
        extra={"extra": "rice"},
    )
    insert_ = BookInsertQ(data=data)
    # excute insert stmt to Book table with a subquery look up to author table for author name
    book_inserted = await insert_.insert(transaction)
    assert book_inserted.author_id == author1.id  # check if the join is correct
    assert book_inserted.name == "Lord of the Tables"

    await transaction.rollback()
