from aiodal.oqm import query, filters, dbentity
from aiodal import dal
import sqlalchemy as sa
from typing import Any, Optional, Dict
import dataclasses
import pytest

pytestmark = pytest.mark.anyio


@dataclasses.dataclass
class BookForm:
    author_id: int
    name: str
    catalog: str
    extra: Dict[str, Any] = dataclasses.field(default_factory=lambda: {})


@dataclasses.dataclass
class BookDBEntity(
    dbentity.Queryable,
    dbentity.Insertable[BookForm],
):
    id: int = 0
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
        stmt = (
            sa.insert(t)
            .values(
                author_id=data.author_id,
                name=data.name,
                catalog=data.catalog,
                extra=data.extra,
            )
            .returning(t)
        )
        return stmt


class BookQueryParams(filters.Filter):
    def __init__(
        self,
        name: Optional[str] = "",
        author_name: Optional[str] = "",
        id__ge: Optional[int] = None,
        id__le: Optional[int] = None,
        id__gt: Optional[int] = None,
        id__lt: Optional[int] = None,
        offset: int = 0,
        limit: int = 1000,
    ):
        self.offset = offset
        self.limit = limit
        self.name = name
        self.author_name_contains = author_name  # NOTE correct attr set here...
        self.id__ge = id__ge
        self.id__le = id__le
        self.id__gt = id__gt
        self.id__lt = id__lt

    __filterset__ = filters.FilterSet(
        [
            filters.WhereEquals("book", "name", "name"),
            filters.WhereContains("author", "name", "author_name_contains"),
            filters.WhereGE("book", "id", "id__ge"),
            filters.WhereGT("book", "id", "id__gt"),
            filters.WhereLE("book", "id", "id__le"),
            filters.WhereLT("book", "id", "id__lt"),
        ]
    )


class SuperBrokenBookQueryParams(BookQueryParams):
    __filterset__ = filters.FilterSet(
        [filters.WhereEquals("fail_1", "fail_2", "fail_3")]
    )


class TableLookupErrorQueryParams(BookQueryParams):
    __filterset__ = filters.FilterSet(
        [filters.WhereEquals("fail", "name", "author_name_contains")]
    )


class BookListQ(
    query.ListQ[BookDBEntity, BookQueryParams],
):
    __db_obj__ = BookDBEntity


class BookInsertQ(query.InsertQ[BookDBEntity, BookForm]):
    __db_obj__ = BookDBEntity


async def test_filters_wheres(transaction):
    author = transaction.get_table("author")

    stmt = sa.insert(author).values(**{"name": "author1"}).returning(author)
    result = await transaction.execute(stmt)
    author1 = result.one()

    next_id_stmt = sa.text("Select nextval(pg_get_serial_sequence('book', 'id'));")
    res = await transaction.execute(next_id_stmt)
    next_id = res.one()[0]
    for i in range(next_id, next_id + 10):
        data = BookForm(author_id=author1.id, name=f"book{i}", catalog=f"pg_catalog{i}")
        insert_ = BookInsertQ(data=data)
        await insert_.insert(transaction)

    # test ge and lt; testing combo wheres
    params = BookQueryParams(
        id__ge=next_id + 2, id__lt=next_id + 8
    )  # giving it the upper bound so that we can check the number of book
    l = BookListQ(where=params)
    res = await l.list(transaction)
    assert len(res) == 6  # 2,3,4,5,6,7

    # test gt and lt
    params = BookQueryParams(id__gt=next_id + 2, id__lt=next_id + 10)
    l = BookListQ(where=params)
    res = await l.list(transaction)
    assert len(res) == 7  # 3,4,5,6,7,8,9

    # test le; need lower bound gt to get correct number
    params = BookQueryParams(id__gt=next_id + 3, id__le=next_id + 10)
    l = BookListQ(where=params)
    res = await l.list(transaction)
    assert len(res) == 7  # 4,5,6, 7,8,9,10

    await transaction.rollback()


async def test_filters_keyerror(transaction):
    # with pytest.raises(filters.TableLookupError):
    # should key error since the tablename is not found in alias or reflect
    with pytest.raises(filters.TableLookupError):
        params = TableLookupErrorQueryParams(author_name="hi")
        l = BookListQ(where=params)
        await l.list(transaction)
    await transaction.rollback()


async def test_filters_attributeerr(transaction):
    with pytest.raises(AttributeError):
        # fail_3 throws since there since getattr fails in line 131
        params = SuperBrokenBookQueryParams()
        l = BookListQ(where=params)
        await l.list(transaction)

    await transaction.rollback()
