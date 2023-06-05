from aiodal.oqm import query, filters, dbentity, views
from aiodal import dal
import sqlalchemy as sa
from typing import Any, Optional, Dict
import dataclasses
import pytest

from aiodal.oqm.views import Paginateable
from aiodal.helpers import sa_total_count

pytestmark = pytest.mark.anyio

from sqlalchemy.exc import NoResultFound, IntegrityError


async def test_default_paginator():
    # NOTE pydantic or whatever validator should assure offset/limit
    # ints are correct and match the logic in the request url

    offset = 0
    limit = 100
    current_len = 100
    total_count = 200
    url = f"https://mysite.com/v1/book/"
    x = views._default_paginator(url, offset, limit, current_len, total_count, None)
    assert x == "https://mysite.com/v1/book/?offset=100&limit=100"

    offset = 0
    limit = 100
    current_len = 100
    total_count = 200
    url = f"https://mysite.com/v1/book/?some_param=42"
    x = views._default_paginator(url, offset, limit, current_len, total_count, "/v1")
    assert x == "/v1/book/?some_param=42&offset=100&limit=100"

    offset = 0
    limit = 100
    current_len = 100
    total_count = 200
    url = f"https://mysite.com/v1/book/?offset={offset}&limit={limit}"
    x = views._default_paginator(url, offset, limit, current_len, total_count, "/v1")
    assert x == "/v1/book/?offset=100&limit=100"

    offset = 100
    limit = 100
    current_len = 100
    total_count = 200
    url = f"https://mysite.com/v1/book/?offset={offset}&limit={limit}"
    x = views._default_paginator(url, offset, limit, current_len, total_count, "/v1")
    assert x is None

    offset = 100
    limit = 100
    current_len = 0
    total_count = 0
    url = f"https://mysite.com/v1/book/?offset={offset}&limit={limit}"
    x = views._default_paginator(url, offset, limit, current_len, total_count, "/v1")
    assert x is None

    offset = 50
    limit = 100
    current_len = 50
    total_count = 200
    url = f"https://mysite.com/v1/book/?offset={offset}&limit={limit}"
    x = views._default_paginator(url, offset, limit, current_len, total_count, "/v1")
    assert x == "/v1/book/?offset=150&limit=100"


class MockBookQueryParams(filters.Filter):
    ...


class MockBookForm:
    ...


@dataclasses.dataclass
class MockBook(
    Paginateable,
    dbentity.Updateable[MockBookForm],
    dbentity.Deleteable[MockBookForm],
    dbentity.Insertable[MockBookForm],
):
    id: int = 0
    author_id: int = 0
    name: str = ""
    catalog: str = ""
    extra: dict[str, Any] = dataclasses.field(default_factory=lambda: {})
    total_count: int = 200

    @classmethod
    def query_stmt(cls, transaction: dal.TransactionManager) -> dbentity.SaSelect:
        ...

    @classmethod
    def update_stmt(
        cls, transaction: dal.TransactionManager, data: MockBookForm
    ) -> dbentity.SaReturningUpdate:
        ...

    @classmethod
    def delete_stmt(
        cls, transaction: dal.TransactionManager, data: MockBookForm
    ) -> dbentity.SaReturningDelete:
        ...

    @classmethod
    def insert_stmt(
        cls, transaction: dal.TransactionManager, data: MockBookForm
    ) -> dbentity.SaReturningInsert:
        ...


class BookListQ(query.ListQ[MockBook, MockBookQueryParams]):
    __db_obj__ = MockBook


class BookDetailQ(query.DetailQ[MockBook]):
    __db_obj__ = MockBook


class BookUpdateQ(query.UpdateQ[MockBook, MockBookForm]):
    __db_obj__ = MockBook


class BookInsertQ(query.InsertQ[MockBook, MockBookForm]):
    __db_obj__ = MockBook


class BookDeleteQ(query.DeleteQ[MockBook, MockBookForm]):
    __db_obj__ = MockBook


async def test_list_view_query(transaction, mocker):
    async def mocked_list(cls_, transaction):
        return [MockBook(id=i) for i in range(100)]

    mocker.patch.object(BookListQ, "list", mocked_list)

    offset = 0
    limit = 100
    url = f"https://mysite.com/v1/book/"

    q = BookListQ(MockBookQueryParams())
    response = await views.ListViewQuery.from_query(
        transaction, url, offset, limit, q, "/v1"
    )
    assert response.next_url == "/v1/book/?offset=100&limit=100"
    assert len(response.results) == 100


async def test_list_view_empty(transaction, mocker):
    async def mocked_list(cls_, transaction):
        return []

    mocker.patch.object(BookListQ, "list", mocked_list)

    offset = 0
    limit = 100
    url = f"https://mysite.com/v1/book/"

    q = BookListQ(MockBookQueryParams())
    response = await views.ListViewQuery.from_query(
        transaction, url, offset, limit, q, "/v1"
    )
    assert response.next_url is None
    assert len(response.results) == 0


async def test_detail_view_query_result(transaction, mocker):
    async def mocked_detail(cls_, transaction):
        return MockBook()

    mocker.patch.object(BookDetailQ, "detail", mocked_detail)

    q = BookDetailQ()
    response = await views.DetailViewQuery.from_query(transaction, q)
    assert isinstance(response.obj, MockBook)


async def test_detail_view_query_exception(transaction, mocker):
    async def mocked_detail(cls_, transaction):
        raise NoResultFound

    mocker.patch.object(BookDetailQ, "detail", mocked_detail)

    with pytest.raises(views.AiodalHTTPException):
        q = BookDetailQ()
        response = await views.DetailViewQuery.from_query(transaction, q)
        assert isinstance(response.obj, MockBook)


async def test_update_view_query_result(transaction, mocker):
    async def mocked_update(cls_, transaction):
        return MockBook()

    mocker.patch.object(BookUpdateQ, "update", mocked_update)

    q = BookUpdateQ(MockBookForm())
    response = await views.UpdateViewQuery.from_query(transaction, q)
    assert isinstance(response.obj, MockBook)


async def test_update_view_query_exception(transaction, mocker):
    async def mocked_update(cls_, transaction):
        raise NoResultFound

    mocker.patch.object(BookUpdateQ, "update", mocked_update)

    with pytest.raises(views.AiodalHTTPException):
        q = BookUpdateQ(MockBookForm())
        await views.UpdateViewQuery.from_query(transaction, q)


async def test_delete_view_query_result(transaction, mocker):
    async def mocked_delete(cls_, transaction):
        return MockBook()

    mocker.patch.object(BookDeleteQ, "delete", mocked_delete)

    q = BookDeleteQ(MockBookForm())
    response = await views.DeleteViewQuery.from_query(transaction, q)
    assert isinstance(response.obj, MockBook)


async def test_delete_view_query_exception(transaction, mocker):
    async def mocked_delete(cls_, transaction):
        raise NoResultFound

    mocker.patch.object(BookDeleteQ, "delete", mocked_delete)

    with pytest.raises(views.AiodalHTTPException):
        q = BookDeleteQ(MockBookForm())
        await views.DeleteViewQuery.from_query(transaction, q)


async def test_insert_view_query_result(transaction, mocker):
    async def mocked_insert(cls_, transaction):
        return MockBook()

    mocker.patch.object(BookInsertQ, "insert", mocked_insert)

    q = BookInsertQ(MockBookForm())
    response = await views.InsertViewQuery.from_query(transaction, q)
    assert isinstance(response.obj, MockBook)


async def test_insert_view_query_exception(transaction, mocker):
    async def mocked_insert(cls_, transaction):
        raise IntegrityError(None, None, Exception)

    mocker.patch.object(BookInsertQ, "insert", mocked_insert)

    with pytest.raises(views.AiodalHTTPException):
        q = BookInsertQ(MockBookForm())
        await views.InsertViewQuery.from_query(transaction, q)
