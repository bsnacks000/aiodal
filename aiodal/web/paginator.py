""" An implmentation of offset/limit pagination. 

"""

from dataclasses import dataclass
from typing import List

from typing import Any, Dict, TypedDict
import sqlalchemy as sa

_DictT = Dict[str, Any]


def _default_paginator(
    request_url: str,
    offset: int,
    limit: int,
    current_len: int,
    total_count: int,
    next_url_start: str | None = None,
) -> str | None:
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
                off_lim = (
                    f"&offset={offset+limit}"
                    if "limit" in request_url
                    else f"&offset={offset+limit}&limit={limit}"
                )
            else:
                off_lim = (
                    f"?offset={offset+limit}"
                    if "limit" in request_url
                    else f"?offset={offset+limit}&limit={limit}"
                )
            return request_url[idx:] + off_lim
        else:
            return request_url[idx:].replace(
                f"offset={offset}", f"offset={offset+limit}"
            )
    else:
        return None


@dataclass
class NextPageInfo:
    total_count: int
    next_url: str | None


def _get_total_count(results: List[_DictT]) -> int | Any:
    return results[0]["total_count"]  # key error means boo boo


def get(
    results: List[_DictT],
    request_url: str,
    offset: int,
    limit: int,
    url_start_index: str = "/v1",
) -> NextPageInfo:
    """Hacked from the innerds of aiodal.oqm. We get the same pagination calculation but its more
    loosely coupled with what we need for basat in terms of types.

    Our list views should create RowMappings using `list(result.mappings())` to pass here.

    Args:
        results (List[RowMapping]): _description_
        request_url (str): _description_
        offset (int): _description_
        limit (int): _description_
        url_start_index (str, optional): _description_. Defaults to "/v1".

    Returns:
        Page: _description_
    """
    current_len = len(results)
    if current_len == 0:
        return NextPageInfo(total_count=0, next_url=None)

    # NOTE if this throws a KeyError we made a boo in sql stmt and forgot sa_total_count!
    total_count = _get_total_count(results)

    next_url = _default_paginator(
        request_url, offset, limit, current_len, total_count, url_start_index
    )
    return NextPageInfo(total_count=total_count, next_url=next_url)


class ListViewData(TypedDict):
    total_count: int
    next_url: str | None
    results: List[Dict[str, Any]]


# NOTE replace with RequestContext here... possible return a pydantic ListViewModelT directly here...
def model_mapper(
    result: sa.Result[Any], request_url: str, offset: int, limit: int
) -> ListViewData:
    results = [dict(r) for r in result.mappings()]
    page = get(results, request_url, offset, limit)
    return {
        "total_count": page.total_count,
        "next_url": page.next_url,
        "results": results,
    }
