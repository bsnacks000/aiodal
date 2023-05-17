from aiodal.oqm import query, filters, dbentity
from aiodal import dal
import sqlalchemy as sa
from typing import Any, Dict, Optional
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
    #    name: Optional[str] = None
    extra: Dict[str, Any] = dataclasses.field(default_factory=lambda: {})


@dataclasses.dataclass
class UpdateableBookDBEntity(dbentity.Updateable[BookPatchForm]):
    id: int = 0
    author_id: int = 0
    name: str = ""
    catalog: str = ""
    extra: dict[str, Any] = dataclasses.field(default_factory=lambda: {})

    @classmethod
    def update_stmt(
        cls, transaction: dal.TransactionManager, data: BookPatchForm
    ) -> sa.Update:
        t = transaction.get_table("book")

        stmt = (
            sa.update(t)
            .where(t.c.id == data.id)
            .values(**{k: v for k, v in vars(data).items() if k != "id" or k is not None})  # type: ignore
            .returning(t)
        )
        return stmt

    @classmethod
    def table(cls, transaction: dal.TransactionManager) -> sa.Table:
        return transaction.get_table("book")


class BookUpdateQ(query.UpdateQ[UpdateableBookDBEntity, BookPatchForm]):
    __db_obj__ = UpdateableBookDBEntity


async def test_dbentity_update(transaction):
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

    # check the setup
    assert book1.extra == {}
    assert book1.name == "book1"

    patch_data = BookPatchForm(id=book1.id, extra={"extra": "sauce"})

    update_q = BookUpdateQ(data=patch_data)
    updated_book = await update_q.update(transaction)
    # print(updated_book)
    assert updated_book.name == book1.name
    assert updated_book.extra["extra"] == "sauce"

    # with update params
    patch_data = BookPatchForm(id=book1.id, extra={"extra": "rice"})

    update_q = BookUpdateQ(data=patch_data)
    updated_book = await update_q.update(transaction)
    assert updated_book.name == book1.name
    assert updated_book.extra["extra"] == "rice"

    await transaction.rollback()
