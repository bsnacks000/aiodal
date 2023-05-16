from aiodal import dal, helpers as aiodalhelpers
from sqlalchemy.ext.asyncio import create_async_engine

import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
import sys
from typing import Any


async def connect(
    url: sa.URL | str,
    metadata: sa.MetaData | None = None,
    reflect_views: bool = True,
    **engine_options: Any,
) -> dal.DataAccessLayer:
    """A factory or a DataAccessLayer object. Builds the the async engine and calls
    reflect with the given params

    Args:
        url (sa.URL | str): Valid pg database url
        metadata (sa.MetaData | None, optional): If your app needs to preconfigure a MetaData. Defaults to None for aiodal to auto create.
        reflect_views (bool, optional): Reflect views as well as tables for your project. Defaults to True.
        **engine_options: Options passed onto `create_async_engine`
    Returns:
        dal.DataAccessLayer: A configured DataAccessLayer instance.
    """

    engine = create_async_engine(url, **engine_options)
    db = dal.DataAccessLayer()
    await db.reflect(engine, metadata, reflect_views)

    return db


async def or_fail(
    url: sa.URL | str,
    metadata: sa.MetaData | None = None,
    reflect_views: bool = True,
    with_exit: bool = True,
    **engine_options: Any,
) -> dal.DataAccessLayer:
    """Attempts to connect to a postgres database via aiodal DataAccessLayer. If we cannot
    connect or reflect tables and with_exit is set to true will automatically print an error message
    and call sys.exit(1)

    Args:
        url (sa.URL | str): Valid pg database url
        metadata (sa.MetaData | None, optional): If your app needs to preconfigure a MetaData. Defaults to None for aiodal to auto create.
        reflect_views (bool, optional): Reflect views as well as tables for your project. Defaults to True.
        with_exit (bool, optional): Exit the program cleanly with error code 1 and a status message. Defaults to True.
        **engine_options: Options passed onto `create_async_engine`
    Returns:
        dal.DataAccessLayer: A configured DataAccessLayer instance.
    """
    try:
        return await connect(url, metadata, reflect_views, **engine_options)
    except SQLAlchemyError as err:
        if with_exit:
            print(
                f"{err.__class__.__name__} : {err}",
                file=sys.stderr,
            )
            sys.exit(1)
        raise
