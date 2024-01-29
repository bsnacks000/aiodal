# Etag stuff
from .models import VersionedResourceModel
import sqlalchemy as sa

from typing import Any
from fastapi import HTTPException, Response

from starlette.datastructures import Headers

import uuid


class EtagHandler:
    def __init__(self, etag_version_field: str = "etag_version"):
        """We use the EtagHandler to manage the state of object versioning during the request lifecycle. We exclusively use
        uuid for this. One is generated when this object is instantiated and so a new instance should be made at the start of
        each request, either in the route or as a FastAPI dependency.

        Args:
            etag_version_field (str, optional): Name of the field to look up in the sa.Row. Defaults to "etag_version".
        """
        self.etag_version_field = etag_version_field
        self.new_etag = uuid.uuid4().hex
        self.current_etag = None

    def set_current(self, headers: Headers, obj: sa.Row[Any]) -> None:
        """First checks the header of the request context for If-Match, throwing 428 if not found. If this check passes it
        will then comparethe queried object's etag version against what was found in the request header.

        If these do not match then the client sent stale data to the request and we will fail with 412. If this succeeds we set the
        `current_etag` field to whatever was currently in the database. Update handlers should then make use of this in a where clause
        to implement optmistic locking pattern when applicable.

        Args:
            ctx (RequestContext[Auth0UserT]): The request context.
            obj (sa.Row[Any]): Any row from the database

        Raises:
            HTTPException: 412 If data comes up stale.
            HTTPException: 428 If no etag in header.
        """
        assert hasattr(obj, self.etag_version_field), "No etag version"

        if "If-Match" not in headers:
            raise HTTPException(
                status_code=428, detail="Update requires If-Match header."
            )

        if obj.etag_version != headers["If-Match"]:
            # print(obj.etag_version, headers["If-Match"])
            raise HTTPException(status_code=412, detail="Precondition Failed.")

        self.current_etag = obj.etag_version


def set_header(response: Response, result: VersionedResourceModel) -> None:
    """Set Etag on response headers if exists.

    Args:
        response (Response): A fastapi Response
        result (ResourceModel): The ResourceModel being returned by the request.
    """
    if result.etag_version:
        response.headers["Etag"] = result.etag_version
