""" 
Async port of create_database and drop_database commands from sqlalchemy-utils library.

For now we only support postgresql
"""

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.engine.url import make_url
from typing import Optional 



def _check_dialect_and_driver(url: sa.URL): 
    dialect_name = url.get_dialect().name 
    dialect_driver = url.get_dialect().driver  

    if dialect_name != 'postgresql': 
        raise ValueError('Currently only support for postgresql dialect.')
    
    if dialect_driver != 'asyncpg': 
        raise ValueError('Currently only support asyncpg')
    

async def create_database(url: str, encoding: str='utf8', template: Optional[str]=None, echo: bool=True): 

    url = make_url(url)
    _check_dialect_and_driver(url)

    database = url.database # database to create 
    
    url = url._replace(database='postgres')
    engine = create_async_engine(url, echo=echo, isolation_level='AUTOCOMMIT')
    if not template:
        template = 'template1'
    
    async with engine.begin() as conn: 
        stmt = f""" 
        create database {database} encoding '{encoding}' template {template}
        """
        await conn.execute(sa.text(stmt)) 
    
    await engine.dispose()


async def drop_database(url: str,echo: bool=True): 

    url = make_url(url)
    _check_dialect_and_driver(url)

    database = url.database # database to create 
    url = url._replace(database='postgres')

    engine = create_async_engine(url, echo=echo, isolation_level='AUTOCOMMIT')
    
    async with engine.begin() as conn: 
        # explictly terminate connections and then drop the database
        version = conn.dialect.server_version_info 
        pid_column = 'pid' if (version >= (9, 2)) else 'procpid'
        stmt = f"""
        SELECT pg_terminate_backend(pg_stat_activity.{pid_column})
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = '{database}'
        AND {pid_column} <> pg_backend_pid()
        """
        await conn.execute(sa.text(stmt))

        stmt = f'drop database if exists {database}'
        await conn.execute(sa.text(stmt))
    await engine.dispose()