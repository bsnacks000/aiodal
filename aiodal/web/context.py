from typing import Any, Generic
from fastapi import Request
from . import models, auth, version
from typing import Mapping


class RequestContext(Generic[auth.Auth0UserT]):
    def __init__(
        self,
        *,
        user: auth.Auth0UserT,
        request: Request,
    ):
        """The base context just holds a reference to the current user and access to the
        current request.

        Args:
            user (auth.Auth0UserT): _description_
            request (Request): _description_
        """
        self.user = user
        self.request = request

    @property
    def request_url(self) -> str:
        """Exposes the url of the request object as a str.

        Returns:
            str: _description_
        """
        return str(self.request.url)


class ListContext(
    RequestContext[auth.Auth0UserT],
    Generic[models.ListViewQueryParamsModelT, auth.Auth0UserT],
):
    def __init__(
        self,
        *,
        user: auth.Auth0UserT,
        request: Request,
        query_params: models.ListViewQueryParamsModelT,
        path_params: Mapping[str, Any] | None = None,
    ):
        """QueryListContext specializes in list view queries. Our APIs must support pagination in the
        form of limit/offset which is provided by inheriting from ListViewModel. This type is specifically
        required to work with the ListViewController.

        Path params are less restrictive and optional. They should be set directly in the route or in a dependency
        before the data is passed into a controller.

        Args:
            user (auth.Auth0UserT): _description_
            request (Request): _description_
            query_params (models.ListViewModelT): _description_
            path_params (Mapping[str, Any] | None, optional): _description_. Defaults to None.
        """
        self.user = user
        self.request = request
        self.query_params = query_params
        self.path_params = path_params


class DetailContext(RequestContext[auth.Auth0UserT]):
    def __init__(
        self,
        *,
        user: auth.Auth0UserT,
        request: Request,
        params: Mapping[str, Any] | None = None,
    ):
        """A QueryDetailContext specializes in a detail view. Detail views are often associated specifically with an
        identifier (book/42) located in a path param. Some detail views however may return structured data represented as
        a single object from a url without an identifier so this is optional. So in a sense this can be defined as any GET that is
        _NOT_ a list view.

        For updates we will often require an extra query to grab a lock or look up state.

        In cases where we want to check a "deleted" status for a detail to throw 410 you can pass a
        SoftDeleteHandler instance. Our detail Controller will use this if it is found.

        Args:
            user (auth.Auth0UserT): _description_
            request (Request): _description_
            params (Mapping[str, Any] | None, optional): _description_. Defaults to None.
            soft_delete_handler (version.SoftDeleteHandler | None, optional): _description_. Defaults to None.
        """
        self.user = user
        self.request = request
        self.params = params


class CreateContext(
    RequestContext[auth.Auth0UserT],
    Generic[models.FormModelT, auth.Auth0UserT],
):
    def __init__(
        self,
        *,
        user: auth.Auth0UserT,
        request: Request,
        form: models.FormModelT,
    ):
        self.user = user
        self.request = request
        self.form = form


class UpdateContext(
    RequestContext[auth.Auth0UserT],
    Generic[models.FormModelT, auth.Auth0UserT],
):
    def __init__(
        self,
        *,
        user: auth.Auth0UserT,
        request: Request,
        form: models.FormModelT | None,
        etag: version.EtagHandler,
        params: Mapping[str, Any] | None = None,
    ):
        self.user = user
        self.request = request
        self.form = form
        self.params = params
        self.etag = etag
