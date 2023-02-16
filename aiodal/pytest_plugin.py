import pytest

from typing import Optional, Tuple, Callable
from alembic import command
from alembic.config import Config as AlembicConfig
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from .dal import DataAccessLayer, custom_json_encoder, TransactionManager
from .database import create_database, drop_database

import pathlib
import logging 
import secrets
import anyio

logger = logging.getLogger(__name__)

from alembic.runtime.environment import EnvironmentContext
from alembic.script import ScriptDirectory

# 1. the location of alembic.ini to run the migrations 
# 2. 



def do_run_migrations(connection: sa.Connection, cfg: AlembicConfig) -> None:
    script = ScriptDirectory.from_config(cfg)

    def upgrade(rev, context):
        return script._upgrade_revs('head', rev)
    
    context = EnvironmentContext(cfg, 
                                 script,
                                 fn=upgrade,
                                 as_sql=False,
                                 starting_rev=None,
                                 destination_rev='head')
    
    context.configure(connection, )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations(engine: AsyncEngine, alembic_cfg: AlembicConfig): 

    async with engine.connect() as conn: 
        await conn.run_sync(do_run_migrations, alembic_cfg)



@pytest.fixture(scope='session')
def testdb_name():
    """ Override this if you want to provide a specific name  
    """ 
    return 'test_' + str(secrets.token_hex(4))


@pytest.fixture(scope='session')
def json_serializer():
    """ Override this to change what function you want to use for json_serializer  
    """ 
    return custom_json_encoder


import dataclasses 

@dataclasses.dataclass
class TestConfig: 
    engine: AsyncEngine 
    alembic_cfg: AlembicConfig


@pytest.fixture(scope='session')
def aiodal_test_config(pytestconfig: pytest.Config, testdb_name: str, json_serializer: Callable[[], str]) -> TestConfig: 
    """ Override this to change how you want your engine to setup for the duration of the session 
    """
    cfg_path = pytestconfig.getini('alembic_config_file')
    alembic_cfg = AlembicConfig(str(cfg_path.resolve())) 

    url = sa.make_url(alembic_cfg.get_main_option('sqlalchemy.url'))
    url = url._replace(database=testdb_name)
    alembic_cfg.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
    
    engine = create_async_engine(alembic_cfg.get_main_option('sqlalchemy.url'), 
                               echo=False, 
                               json_serializer=json_serializer)
    return TestConfig(engine, alembic_cfg)


def pytest_addoption(parser: pytest.Parser, 
                     pluginmanager: pytest.PytestPluginManager): 
    parser.addini(
        'alembic_config_file', 
        'path to alembic config file. Default is ./alembic', 
        type='paths', 
        default=pathlib.Path('alembic.ini')) 



@pytest.fixture(scope='session')
async def db(aiodal_test_config): 
    """ Create the database and mirate using an os call to alembic. 
    Setup the database internals and seed critical data. 
    Yield the DataAccessLayer object for the rest of the tests.
    
    """
    # test db name is autogenerated 
    engine, alembic_cfg = \
        aiodal_test_config.engine, aiodal_test_config.alembic_cfg
    test_url = engine.url.render_as_string(hide_password=False)


    try:

        await create_database(test_url)
        await run_migrations(engine, alembic_cfg)
        
        db = DataAccessLayer()
        meta = sa.MetaData()
        
        await db.reflect(engine, meta)
        yield db 
    except Exception as err:
        logger.exception(err)
    finally: 
        await engine.dispose()
        await drop_database(test_url)


@pytest.fixture
async def transaction(db): 
    """ auto rollback. Used by get_transaction to create isolation in tests."""
    async with db.engine.connect() as conn: 
        transaction = TransactionManager(conn, db)
        try: 
            yield transaction
        finally:
            await transaction.rollback()