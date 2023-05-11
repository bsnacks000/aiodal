from aiodal.oqm import query, filters, dbentity
from aiodal import dal
import sqlalchemy as sa
from typing import Any, Optional, Dict
import dataclasses
import pytest

pytestmark = pytest.mark.anyio


class BookForm(dbentity.BaseFormModel):
    author_name: str
    name: str
    catalog: str
    extra: Dict[str, Any] = {}


class BookPatchForm(dbentity.BaseFormModel):
    id: int
    name: Optional[str] = None
    extra: Dict[str, Any] = {}


@dataclasses.dataclass
class BookDBEntity(
    dbentity.TableDBEntity,
    dbentity.InsertableDBEntity[BookForm],
    dbentity.UpdateableDBEntity[BookPatchForm],
):
    # id: int = 0 <-- inherit from DBEntity, parent of TableDBEntity
    author_id: int = 0
    name: str = ""
    catalog: str = ""
    extra: dict[str, Any] = dataclasses.field(default_factory=lambda: {})

    @classmethod
    def query_stmt(cls, transaction: dal.TransactionManager) -> sa.Select[Any]:
        t = transaction.get_table("book")
        stmt = sa.select(t).order_by(t.c.id)  # type: ignore
        return stmt

    @classmethod
    def insert_stmt(
        cls, transaction: dal.TransactionManager, data: BookForm
    ) -> sa.Insert:
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


class BookQueryParams(filters.QueryParamsModel):
    def __init__(
        self,
        name: Optional[str] = "",
        author_name: Optional[str] = "",
        author_name_contains: Optional[str] = "",
        offset: int = 0,
        limit: int = 1000,
    ):
        self.offset = offset
        self.limit = limit
        self.name = name
        self.author_name = author_name
        self.author_name_contains = author_name_contains

    __filterset__ = filters.FilterSet(
        [
            filters.WhereEquals("book", "name", "name"),
            filters.WhereEquals("author", "name", "author_name"),
            filters.WhereContains("author", "name", "author_name_contains"),
        ]
    )


class BookListQ(
    query.ListQ[BookDBEntity, BookQueryParams],
):
    __db_obj__ = BookDBEntity


class BookUpdateQ(query.UpdateQ[BookDBEntity, BookPatchForm, BookUpdateQueryParams]):
    __db_obj__ = BookDBEntity


class BookInsertQ(query.InsertQ[BookDBEntity, BookForm]):
    __db_obj__ = BookDBEntity


async def test_dbentity_create_read_update(transaction):
    author = transaction.get_table("author")

    stmt = sa.insert(author).values(**{"name": "author1"}).returning(author)
    result = await transaction.execute(stmt)
    author1 = result.one()

    # test Insert
    data = BookForm(
        author_name=author1.name,
        name="Lord of the Tables",
        catalog="pg_catalog",
        extra={"extra": "rice"},
    )
    insert_ = BookInsertQ(data=data)
    book_inserted = await insert_.insert(transaction)
    assert book_inserted.author_id == author1.id
    assert book_inserted.name == "Lord of the Tables"

    # test query
    params = BookQueryParams(name="Lord of the Tables")
    l = BookListQ(where=params)
    res = await l.list(transaction)
    assert len(res) == 1

    book1_exp = res.pop()
    assert book1_exp.id == book_inserted.id
    assert book1_exp.name == book_inserted.name
    assert book1_exp.author_id == book_inserted.author_id

    # update
    patch_data = BookPatchForm(id=book_inserted.id, extra={"extra": "rice"})
    params = BookUpdateQueryParams(author_name="author1")

    update_q = BookUpdateQ(data=patch_data, where=params)
    updated_book = await update_q.update(transaction)
    assert updated_book.name == book_inserted.name
    assert updated_book.extra["extra"] == "rice"

    await transaction.rollback()
