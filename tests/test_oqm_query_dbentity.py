from aiodal.oqm import query, dbentity
from aiodal import dal
import sqlalchemy as sa
from typing import Any, Optional
import dataclasses
import pytest

pytestmark = pytest.mark.anyio


class BookQueryParams:
    def __init__(
        self,
        name: Optional[str] = "",
        offset: int = 0,
        limit: int = 1000,
    ):
        self.offset = offset
        self.limit = limit
        self.name = name


class IdFilter:
    def __init__(self, id: int):
        self.id = id


@dataclasses.dataclass
class BookDBEntityData:
    id: int = 0
    author_id: int = 0
    author_name: str = ""
    name: str = ""
    catalog: str = ""
    extra: dict[str, Any] = dataclasses.field(default_factory=lambda: {})


@dataclasses.dataclass
class ReadableBookDBEntity(BookDBEntityData, dbentity.Queryable[BookQueryParams]):
    @classmethod
    def query_stmt(
        cls, transaction: dal.TransactionManager, where: BookQueryParams
    ) -> sa.Select[Any]:
        t = transaction.get_table("book")
        u = transaction.get_table("author")
        stmt = (
            sa.select(t, u.c.name.label("author_name"))
            .select_from(t.join(u, u.c.id == t.c.author_id))
            .order_by(t.c.id)
        )  # type: ignore
        return stmt


@dataclasses.dataclass
class DetailBookDBEntity(BookDBEntityData, dbentity.Queryable[IdFilter]):
    @classmethod
    def query_stmt(
        cls, transaction: dal.TransactionManager, where: IdFilter
    ) -> sa.Select[Any]:
        t = transaction.get_table("book")
        return sa.select(t).where(t.c.id == where.id)


class BookListQ(
    query.ListQ[ReadableBookDBEntity, BookQueryParams],
):
    __db_obj__ = ReadableBookDBEntity


class BookDetailQ(query.DetailQ[ReadableBookDBEntity, BookQueryParams]):
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

    id_params = IdFilter(id=book1.id)
    dq = BookDetailQ(where=id_params)
    res = await dq.detail(transaction)

    assert res.id == book1.id
    assert res.name == book1.name
    assert res.author_id == book1.author_id

    await transaction.rollback()
