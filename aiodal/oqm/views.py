"""This module provides some convenience for gluing the oqm APIs to the async web framework of your choice.
"""

from typing import Optional, Generic, Sequence, TypeVar, Dict, Any
from aiodal.oqm.dbentity import (
    QueryableT,
    InsertableT,
    UpdateableT,
    Queryable,
    DeleteableT,
)
from .query import ListQ, DetailQ, UpdateQ, InsertQ, DeleteQ
from .dbentity import FormDataT
from .filters import Filter, FilterT

from sqlalchemy.exc import NoResultFound, IntegrityError
import dataclasses
import abc

from aiodal import dal


class AiodalHTTPException(Exception):
    def __init__(
        self,
        status_code: int,
        detail: str,
        headers: Optional[Dict[str, Any]] = None,
    ):
        """This is essentially duck typed from starlette.exceptions.HttpException.

        Args:
            status_code (int): A valid Http Status code
            detail (str): Error detail
            headers (Optional[dict], optional): Headers to send. Defaults to None.
        """
        self.status_code = status_code
        self.detail = detail
        self.headers = headers

    def __repr__(self) -> str:  # pragma: no cover
        class_name = self.__class__.__name__
        return f"{class_name}(status_code={self.status_code!r}, detail={self.detail!r})"


class Paginateable(Queryable, abc.ABC):
    total_count: int


PaginateableT = TypeVar("PaginateableT", bound=Paginateable)


def _default_paginator(
    request_url: str,
    offset: int,
    limit: int,
    current_len: int,
    total_count: int,
    next_url_start: Optional[str] = None,
) -> Optional[str]:
    if total_count < 1:
        return None

    remainder = total_count - current_len - offset
    if remainder > 0:
        if next_url_start:
            idx = request_url.index(next_url_start)
        else:
            idx = 0
        if "offset" not in request_url:
            if "?" in request_url:
                off_lim = f"&offset={offset+limit}&limit={limit}"
            else:
                off_lim = f"?offset={offset+limit}&limit={limit}"
            return request_url[idx:] + off_lim
        else:
            return request_url[idx:].replace(
                f"offset={offset}", f"offset={offset+limit}"
            )
    else:
        return None


@dataclasses.dataclass
class ListViewQuery(Generic[PaginateableT, FilterT]):
    next_url: Optional[str]
    results: Sequence[PaginateableT]

    @classmethod
    def _paginator(
        cls,
        request_url: str,
        offset: int,
        limit: int,
        results: Sequence[PaginateableT],
        next_url_start: Optional[str] = None,
    ) -> Optional[str]:
        current_len = len(results)
        if current_len == 0:  # short circuit empty response
            return None

        total_count = results[0].total_count  # grab the first

        return _default_paginator(
            request_url, offset, limit, current_len, total_count, next_url_start
        )

    @classmethod
    async def from_query(
        cls,
        transaction: dal.TransactionManager,
        request_url: str,
        offset: int,
        limit: int,
        listq: ListQ[PaginateableT, FilterT],
        url_start_index: Optional[str] = None,
    ) -> "ListViewQuery[PaginateableT, FilterT]":
        results = await listq.list(transaction)
        next_url = cls._paginator(request_url, offset, limit, results, url_start_index)
        return cls(next_url=next_url, results=results)


@dataclasses.dataclass
class DetailViewQuery(Generic[QueryableT]):
    obj: QueryableT

    @classmethod
    async def from_query(
        cls,
        transaction: dal.TransactionManager,
        detailq: DetailQ[QueryableT],
    ) -> "DetailViewQuery[QueryableT]":
        try:
            obj = await detailq.detail(transaction)
            return cls(obj=obj)
        except NoResultFound:
            raise AiodalHTTPException(404, detail="Not Found.")


@dataclasses.dataclass
class InsertViewQuery(Generic[InsertableT, FormDataT]):
    obj: InsertableT

    @classmethod
    async def from_query(
        cls,
        transaction: dal.TransactionManager,
        insertq: InsertQ[InsertableT, FormDataT],
    ) -> "InsertViewQuery[InsertableT, FormDataT]":
        try:
            obj = await insertq.insert(transaction)
            return cls(obj=obj)
        except IntegrityError as err:
            err_orig = str(err.orig)
            # we return the Key from the database error if uc violation
            if "UniqueViolationError" in str(err_orig):
                detail = (
                    "Unique Violation Error: "
                    + err_orig[err_orig.find("DETAIL:") :]
                    .replace("DETAIL:", "")
                    .strip()
                )
            else:
                detail = "Failed to create resource."
            raise AiodalHTTPException(status_code=409, detail=detail)


@dataclasses.dataclass
class CreateOrUpdateQuery(InsertViewQuery[InsertableT, FormDataT]):
    @classmethod
    async def from_query(
        cls,
        transaction: dal.TransactionManager,
        insertq: InsertQ[InsertableT, FormDataT],
    ) -> "InsertViewQuery[InsertableT, FormDataT]":
        try:
            obj = await insertq.insert(transaction)
            return cls(obj=obj)
        except NoResultFound:
            raise AiodalHTTPException(404, detail="Not Found.")


@dataclasses.dataclass
class UpdateViewQuery(Generic[UpdateableT, FormDataT]):
    obj: UpdateableT

    @classmethod
    async def from_query(
        cls,
        transaction: dal.TransactionManager,
        updateq: UpdateQ[UpdateableT, FormDataT],
    ) -> "UpdateViewQuery[UpdateableT, FormDataT]":
        try:
            obj = await updateq.update(transaction)  # call update here
            return cls(obj=obj)
        except NoResultFound:
            raise AiodalHTTPException(404, detail="Not Found.")


@dataclasses.dataclass
class DeleteViewQuery(Generic[DeleteableT, FormDataT]):
    obj: DeleteableT

    @classmethod
    async def from_query(
        cls,
        transaction: dal.TransactionManager,
        deleteq: DeleteQ[DeleteableT, FormDataT],
    ) -> "DeleteViewQuery[DeleteableT, FormDataT]":
        try:
            obj = await deleteq.delete(transaction)
            return cls(obj=obj)
        except NoResultFound:
            raise AiodalHTTPException(404, detail="Not Found.")
