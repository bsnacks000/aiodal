# Etag stuff
from .models import VersionedResourceModel
import sqlalchemy as sa

from typing import Any
from fastapi import HTTPException, Response

import uuid

from .context import RequestContext
from .auth import Auth0UserT


class SoftDeleteHandler:
    def __init__(self, soft_delete_field: str = "deleted"):
        """A simple handler to check the status of whether an item was soft deleted as defined by the application."""
        self.soft_delete_field = soft_delete_field

    def status(self, obj: sa.Row[Any]):
        """Validates that the row contains the correct deleted field specified and then checks its boolean value.
        If the item was in the database at one point and then marked as deleted we can return a 410 response here.

        """
        assert hasattr(obj, self.soft_delete_field), "No soft delete field"

        if getattr(obj, self.soft_delete_field):
            raise HTTPException(status_code=410, detail="Gone.")


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

    def set_current_etag(self, ctx: RequestContext[Auth0UserT], obj: sa.Row[Any]):
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

        if "If-Match" not in ctx.request.headers:
            raise HTTPException(
                status_code=428, detail="Update requires If-Match header."
            )

        if obj.etag_version != ctx.request.headers["If-Match"]:
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
