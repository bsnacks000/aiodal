from aiodal.oqm import query, filters, dbentity
from aiodal import dal
import sqlalchemy as sa
from typing import Any, Optional, Dict
import dataclasses
import pytest

pytestmark = pytest.mark.anyio


# NOTE @tinbot since removing pydantic the patch form must be explicit in this case
# in the tests having name: None was auto-ignored which is very pydantic behavior
# when I made the FormT more generic the test failed with assert None == book1.name
# in practice we would configure any forms to handle this sort of behavior if needed
@dataclasses.dataclass
class BookPatchForm:
    id: int


@dataclasses.dataclass
class DeleteableBookDBEntity(dbentity.Deleteable[BookPatchForm]):
    id: int = 0
    author_id: int = 0
    name: str = ""
    catalog: str = ""
    extra: dict[str, Any] = dataclasses.field(default_factory=lambda: {})

    @classmethod
    def delete_stmt(
        cls, transaction: dal.TransactionManager, data: BookPatchForm
    ) -> sa.Delete:
        t = transaction.get_table("book")
        return sa.delete(t).where(t.c.id == data.id)

    @classmethod
    def table(cls, transaction: dal.TransactionManager) -> sa.Table:
        return transaction.get_table("book")


class BookDeleteQ(query.DeleteQ[DeleteableBookDBEntity, BookPatchForm]):
    __db_obj__ = DeleteableBookDBEntity


async def test_dbentity_delete_stmt(transaction):
    # setup
    author = transaction.get_table("author")
    book = transaction.get_table("book")

    stmt = sa.insert(author).values(**{"name": "author1"}).returning(author)
    result = await transaction.execute(stmt)
    author1 = result.one()

    stmt = (
        sa.insert(book)
        .values(**{"name": "book1", "author_id": author1.id})
        .returning(book)
    )
    result = await transaction.execute(stmt)
    book1 = result.one()

    book_contents = await transaction.execute(sa.select(book))
    book_contents = book_contents.all()
    assert len(book_contents) == 1

    patch_data = BookPatchForm(id=book1.id)
    l = BookDeleteQ(patch_data)
    await l.delete(transaction)

    book_contents = await transaction.execute(sa.select(book))
    book_contents = book_contents.all()
    assert len(book_contents) == 0

    await transaction.rollback()
