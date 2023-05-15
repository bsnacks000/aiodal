from aiodal import dal, helpers as aiodalhelpers
from sqlalchemy.ext.asyncio import create_async_engine

import sqlalchemy as sa
import sys
from typing import Any


async def connect(url: sa.URL | str, **kwargs: Any) -> dal.DataAccessLayer:
    """A connection object for use with the cli

    Args:
        url (sa.URL | str): _description_.
        **kwargs (Any): _description_.

    Returns:
        dal.DataAccessLayer: _description_

    """

    engine = create_async_engine(url, **kwargs)
    db = dal.DataAccessLayer()
    await db.reflect(engine)

    return db


async def or_fail(
    url: sa.URL | str,
    **kwargs: Any,
) -> dal.DataAccessLayer:
    """Wraps a connect call in a sys.exit in case we cannot connect. This should
    be the default way to call into

    Args:
        uri (sa.URL | str): _description_.
        **kwargs (Any): _description_.

    Returns:
        dal.DataAccessLayer: _description_
    """
    try:
        return await connect(url, **kwargs)
    except Exception as err:
        print(f"ERROR: cannot connect to bemadb: {str(err)}", file=sys.stderr)
        sys.exit(1)
