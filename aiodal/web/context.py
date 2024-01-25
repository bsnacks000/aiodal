from typing import Any, Dict, Generic

from fastapi import Request

from .auth import Auth0UserT, PermissionDataT
from .models import IQueryParams
from .version import EtagHandler, SoftDeleteHandler

PathParamDict = Dict[str, Any]


class RequestContext(Generic[Auth0UserT]):
    def __init__(
        self,
        user: Auth0UserT,
        request: Request,
        *,
        query_params: IQueryParams | None = None,
        paths: PathParamDict | None = None,
        etag: EtagHandler | None = None,
        soft_delete_handler: SoftDeleteHandler | None = None,
        **extras: Any
    ):
        """This is a simple proxy class to use to hold request data in a standardized way.
        It exposes an API to bridge needed request data to our sqlalchemy/aiodal queries.
        """
        self.user = user
        self.request = request
        self.query_params = query_params
        self.paths = paths
        self.extras = extras
        self.etag = etag
        self.soft_delete_handler = soft_delete_handler

    @property
    def request_url(self) -> str:
        """Exposes the url of the request object as a str.

        Returns:
            str: _description_
        """
        return str(self.request.url)

    def query_param(self, lookup: str) -> Any:
        """Guard for query param lookup. If this was not set in the
        request context lookups will fail fast with an error.

        Args:
            lookup (str): _description_

        Returns:
            Any: _description_
        """
        assert self.query_params is not None, "params not set"
        return self.query_params.param(lookup)

    def path_param(self, lookup: str) -> Any:
        """This is a guard around path param lookup. If this was not set in the
        request context it will fail fast with an error.

        Args:
            lookup (str): _description_

        Returns:
            Any: _description_
        """
        assert self.paths is not None, "paths not set"
        return self.paths.get(lookup)

    def extra(self, key: str) -> Any:
        """Lookup an extra piece of data tied to the context.

        Args:
            key (str): The lookup field.

        Returns:
            Any: The value of the object.
        """
        return self.extras[key]

    def allowed(self) -> PermissionDataT | None:
        """Proxy a call into the user object to get allowed agencies for filtering purposes.

        Returns:
            _Ids | None: _description_
        """
        return self.user.get_permissions()
