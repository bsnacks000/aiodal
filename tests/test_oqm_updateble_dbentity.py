from aiodal.oqm import query, filters, dbentity
from aiodal import dal
import sqlalchemy as sa
from typing import Any, Dict, Optional
import dataclasses
import pytest

pytestmark = pytest.mark.anyio


class BookPatchForm(dbentity.BaseFormModel):
    id: int
    name: Optional[str] = None
    extra: Dict[str, Any] = {}


@dataclasses.dataclass
class UpdateableBookDBEntity(dbentity.UpdateableDBEntity[BookPatchForm]):
    # id: int = 0 <-- inherit from DBEntity, parent of InsertableDBEntity
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
            .values(**data.dict(exclude={"id"}, exclude_none=True))
        )
        return stmt

    @classmethod
    def table(cls, transaction: dal.TransactionManager) -> sa.Table:
        return transaction.get_table("book")


# additional query or business logic for updating
class BookUpdateQueryParams(filters.UpdateQueryParamsModel):
    def __init__(self, author_name: Optional[str] = None):
        self.author_name = author_name

    __filterset__ = filters.FilterSet(
        [
            filters.WhereEquals("author", "name", "author_name"),
        ]
    )


class BookUpdateQ(
    query.UpdateQ[UpdateableBookDBEntity, BookPatchForm, BookUpdateQueryParams]
):
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
    params = BookUpdateQueryParams()

    update_q = BookUpdateQ(data=patch_data, where=params)
    updated_book = await update_q.update(transaction)
    assert updated_book.name == book1.name
    assert updated_book.extra["extra"] == "sauce"

    # with update params
    patch_data = BookPatchForm(id=book1.id, extra={"extra": "rice"})
    params = BookUpdateQueryParams(author_name="author1")

    update_q = BookUpdateQ(data=patch_data, where=params)
    updated_book = await update_q.update(transaction)
    assert updated_book.name == book1.name
    assert updated_book.extra["extra"] == "rice"

    await transaction.rollback()
