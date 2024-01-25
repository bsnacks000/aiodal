import json
import datetime
import enum
import sqlalchemy as sa
from typing import Any


class CustomJsonEncoder(json.JSONEncoder):
    """This class extends the builtin json encoder to handle datetime.date and enum objects
    the way we want for database serialization with JSONB. This is provided as a convenience for
    working with JSONB and can easily reimplemented per project based on the user's needs.
    """

    def default(self, o: Any) -> Any:
        """This basic handler just does some basics for datetime.date and enum serialization.

        Args:
            o (Any): Any object

        Returns:
            Any: Any object that gets serialized
        """
        if isinstance(o, datetime.date):
            return o.strftime("%Y-%m-%d")

        elif isinstance(o, enum.Enum):
            return o.value

        return super().default(o)


def json_serializer(o: Any) -> str:
    """A simple callable wrapper using the standard json library, provided as a convenience for working
    with JSONB. Pass this to an AsyncEngine

    Ex.
    engine = create_async_engine(..., json_serializer=aiodal.helpers.json_serializer)

    Args:
        o (Any): _description_

    Returns:
        str: _description_
    """
    return json.dumps(o, cls=CustomJsonEncoder)


def sa_total_count(c: sa.Column[Any]) -> Any:
    """Handy shortcut for returning total_count. Useful for paginating. Pass a
    unique column in your query to get the count before limit/offset is applied.

    Args:
        c (sa.Column): A sqla column. Should be unique like "id"

    Returns:
        sa.Label: The labeled Column (total_count)
    """
    return sa.func.count(c).over().label("total_count")
