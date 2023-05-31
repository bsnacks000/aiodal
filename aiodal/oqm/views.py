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
            status_code (int): _description_
            detail (str): _description_
            headers (Optional[dict], optional): _description_. Defaults to None.
        """
        self.status_code = status_code
        self.detail = detail
        self.headers = headers

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"{class_name}(status_code={self.status_code!r}, detail={self.detail!r})"


@dataclasses.dataclass
class Paginateable(Queryable):
    total_count: int = 0


PaginateableT = TypeVar("PaginateableT", bound=Paginateable)


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
        """Algorithm to create a url that will point to the next page in the pagination.

        It assumes the client wants a page of equal size from the previous request.

        NOTE that results that hit this Query handler must provide a total_count field in the results
        in order to correctly count a next url. This should be done for all list views that
        hit this API. If you fail to do this we raise a ValueError here.

        Args:
            request_url (str): The request url in its entirety.
            offset (int): The current offset
            limit (int): The current limit
            results (Sequence[PaginateableT]): A paginateable result. Must have have total_count field as a columnn in the result.
            url_start_index (Optional[str], optional): A string indicating where to begin the slice to next_url.
                Example would be "/v1" to slice inclusively at index of "/v1". Defaults to None which uses the entire hostname.

        Raises:
            ValueError: Checks for `total_count` field in result set fails.

        Returns:
            Optional[str]: The constructed next_url.
        """
        len_recs = len(results)

        if len_recs == 0:  # short circuit sempty response
            return None

        tc = results[0].total_count

        if tc is None:  # No total_count provided in entity #type: ignore
            raise ValueError("total_count must be provided to ListViewQuery")

        # must subtract previous offset
        remainder = tc - len_recs - offset  # type: ignore
        if remainder > 0:
            if next_url_start:
                idx = request_url.index(next_url_start)
            else:
                idx = 0
            if "offset" not in request_url:
                return request_url[idx:] + f"&offset={offset+limit}"  # type: ignore
            else:
                return request_url[idx:].replace(f"offset={offset}", f"offset={offset+limit}")  # type: ignore
        else:
            return None

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
        """Standard Listview. Will paginate to the next url if `total_count` is calculated. Otherwise
        returns None.

        If no data is found return an empty list. ListView routes should always succeed.

        Args:
            transaction (dal.TransactionManager): _description_
            request (FastAPIRequest): _description_
            listq (ListQ[DBEntityT, FilterT]): _description_

        Returns:
            ListViewQuery[DBEntityT, FilterT]: _description_
        """
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
        deetq: DetailQ[QueryableT],
    ) -> "DetailViewQuery[QueryableT]":
        """Standard detail view. Find an object or raise 404

        Args:
            transaction (dal.TransactionManager): _description_
            deetq (DetailQ[DBEntityT]): _description_

        Raises:
            HTTPException: _description_

        Returns:
            DetailViewQuery[DBEntityT]: _description_
        """
        try:
            obj = await deetq.detail(transaction)
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
        """Standard detail view. Find an object or raise 404

        Args:
            transaction (dal.TransactionManager): _description_
            deetq (DetailQ[DBEntityT]): _description_

        Raises:
            HTTPException: _description_

        Returns:
            DetailViewQuery[DBEntityT]: _description_
        """
        try:
            obj = await insertq.insert(transaction)
            return cls(obj=obj)
        except IntegrityError as err:
            err_orig = str(err.orig)
            if "UniqueViolationError" in str(
                err_orig
            ):  # we return the Key from the database error if uc violation
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
        delq: DeleteQ[DeleteableT, FormDataT],
    ) -> "DeleteViewQuery[DeleteableT, FormDataT]":
        try:
            obj = await delq.delete(transaction)
            return cls(obj=obj)
        except NoResultFound:
            raise AiodalHTTPException(404, detail="Not Found.")
