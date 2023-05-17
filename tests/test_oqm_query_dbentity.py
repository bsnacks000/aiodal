from aiodal.oqm import query, filters, dbentity
from aiodal import dal
import sqlalchemy as sa
from typing import Any, Optional
import dataclasses
import pytest

pytestmark = pytest.mark.anyio


@dataclasses.dataclass
class ReadableBookDBEntity(dbentity.Queryable):
    # id: int = 0 <-- inherit from DBEntity, parent of TableDBEntity
    id: int = 0
    author_id: int = 0
    author_name: str = ""
    name: str = ""
    catalog: str = ""
    extra: dict[str, Any] = dataclasses.field(default_factory=lambda: {})

    @classmethod
    def query_stmt(cls, transaction: dal.TransactionManager) -> sa.Select[Any]:
        t = transaction.get_table("book")
        u = transaction.get_table("author")
        stmt = (
            sa.select(t, u.c.name.label("author_name"))
            .select_from(t.join(u, u.c.id == t.c.author_id))
            .order_by(t.c.id)
        )  # type: ignore
        return stmt


class BookQueryParams(filters.Filter):
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
    query.ListQ[ReadableBookDBEntity, BookQueryParams],
):
    __db_obj__ = ReadableBookDBEntity


class BookDetailQ(query.DetailQ[ReadableBookDBEntity]):
    __db_obj__ = ReadableBookDBEntity


async def test_dbentity_query_stmt(transaction):
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

    # actual testing
    params = BookQueryParams(name="book1")
    l = BookListQ(where=params)
    res = await l.list(transaction)
    assert len(res) == 1

    book1_exp = res.pop()
    assert book1_exp.id == book1.id
    assert book1_exp.name == book1.name
    assert book1_exp.author_id == book1.author_id

    params = BookQueryParams(author_name_contains="author")
    l = BookListQ(where=params)
    res = await l.list(transaction)
    assert len(res) == 1

    id_params = query.IdFilter(id_=book1.id, tablename="book")
    dq = BookDetailQ(where=id_params)
    res = await dq.detail(transaction)

    assert res.id == book1.id
    assert res.name == book1.name
    assert res.author_id == book1.author_id

    await transaction.rollback()
