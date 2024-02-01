import abc

from typing import TypeVar, Annotated, Dict, Generic, Any

import pydantic
from fastapi import FastAPI, Query
from starlette.datastructures import URLPath


# base for all app models
class ApiBaseModel(pydantic.BaseModel, abc.ABC):
    model_config = pydantic.ConfigDict(from_attributes=True)
    _fastapi: FastAPI | None = pydantic.PrivateAttr()

    @classmethod
    def init_app(cls, app: FastAPI) -> None:
        cls._fastapi = app


# outgoing resources (details)
class ResourceModel(ApiBaseModel):
    ...


# inbound resources (update/insert)
class FormModel(ApiBaseModel):
    ...


ResourceModelT = TypeVar("ResourceModelT", bound=ResourceModel)
FormModelT = TypeVar("FormModelT", bound=FormModel)
ResourceUri = Annotated[str, URLPath]


class VersionedResourceModel(ResourceModel):
    etag_version: str


# base for parent resource i.e parent/<id>/children
# should compute hyperlinks
class ParentResourceModel(ResourceModel):
    """Base class for all outgoing parent resources."""

    @pydantic.computed_field  # type: ignore[misc]
    @property
    def links(self) -> Dict[str, ResourceUri] | None:  # override in child class
        ...


class ListViewModel(ApiBaseModel, Generic[ResourceModelT]):
    """Base class for all outgoing list views"""

    next_url: str | None = None
    total_count: int = 0
    results: list[ResourceModelT]


ListViewModelT = TypeVar("ListViewModelT", bound=ListViewModel[Any])


class ListViewQueryParamsModel:
    """Query Params for list views should contain at least offset/limit to control the paginator."""

    def __init__(
        self,
        offset: int = Query(0, ge=0),
        limit: int = Query(1000, ge=0, le=1000),
    ):
        self.offset = offset
        self.limit = limit


ListViewQueryParamsModelT = TypeVar(
    "ListViewQueryParamsModelT", bound=ListViewQueryParamsModel
)
