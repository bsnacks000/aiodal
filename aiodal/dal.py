import contextlib
from typing import List, AsyncIterator, Optional, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncConnection

import sqlalchemy as sa
from sqlalchemy.sql import expression
from sqlalchemy.engine import ResultProxy
from sqlalchemy.engine.interfaces import (
    _CoreAnyExecuteParams,
    CoreExecuteOptionsParameter,
)
from collections.abc import Iterable

from typing import Dict, Sequence


class DataAccessLayer(object):
    """The main controller for sqla db access. We use the reflection API via the reflect method which
    serves as the true initialization of the object. This is done for common cases such as web apps when we
    need to a db instance around but need to connect to the db as part of a startup hook. This object will hold
    references to AsyncEngine, MetaData, Inspector as well as populate any unique_constraints in the database.
    """

    _constraints: dict[str, List[str]] = {}
    _aliased_tables: Dict[str, sa.TableValuedAlias] = {}

    @property
    def metadata(self) -> sa.MetaData:
        return self._metadata

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @property
    def inspector(self) -> sa.Inspector:
        return self._inspector

    async def reflect(
        self,
        engine: AsyncEngine,
        metadata: Optional[sa.MetaData] = None,
        schema: str | None | List[str] = None,
        views: bool = True,
        only: Sequence[str] | None = None,
        extend_existing: bool = False,
        autoload_replace: bool = True,
        resolve_fks: bool = True,
        **dialect_kwargs: Any,
    ) -> None:
        """Takes an AsyncEngine and uses sqlalchemy reflection API to reflect the table data.
            Sets this state on the object.

            Ex.
            engine = create_async_engine(...)
            db = DataAccessLayer()
            await db.reflect(engine)   # success!

        Args:
            engine (AsyncEngine): The sqla engine to bind on
            metadata (Optional[sa.MetaData], optional): An optional MetaData object. Defaults to None. If none sets to default `MetaData()`.
            schema (str | None | List[str], optional): see `sa.MetaData.reflect`. Defaults to None. Can be a single schema (str) or a list of schema (list[str])
            views (bool, optional): see `sa.MetaData.reflect`. Defaults to True.
            only (Sequence[str] | None, optional): see `sa.MetaData.reflect`. Defaults to None.
            extend_existing (bool, optional): see `sa.MetaData.reflect`. Defaults to False.
            autoload_replace (bool, optional): see `sa.MetaData.reflect`. Defaults to True.
            resolve_fks (bool, optional): see `sa.MetaData.reflect`. Defaults to True.

        """
        relect_metadata_first = True if metadata and metadata.schema else False

        if not metadata:
            metadata = sa.MetaData()

        ls_schema: List[str | None] = [None]  # for tables without schema name
        # XXX probably should just limit to a list instead of iterable..mypy does not like it
        if isinstance(schema, Iterable) and not isinstance(schema, str):
            ls_schema += schema
        elif isinstance(schema, str):
            ls_schema += [schema]

        def _reflect(con: sa.Connection) -> sa.Inspector:
            assert metadata is not None
            if relect_metadata_first:  # metadata with schema is provided
                metadata.reflect(
                    bind=con,
                    views=views,
                    only=only,
                    extend_existing=extend_existing,
                    autoload_replace=autoload_replace,
                    resolve_fks=resolve_fks,
                    **dialect_kwargs,
                )

            for schema_ in ls_schema:
                metadata.reflect(
                    bind=con,
                    views=views,
                    schema=schema_,
                    only=only,
                    extend_existing=extend_existing,
                    autoload_replace=autoload_replace,
                    resolve_fks=resolve_fks,
                    **dialect_kwargs,
                )

            inspector = sa.inspect(con)
            self._gather_unique_contstraints(metadata, inspector)
            return inspector

        async with engine.connect() as conn:
            self._inspector: sa.Inspector = await conn.run_sync(_reflect)

        self._engine = engine
        self._metadata = metadata

    def set_aliased(self, name: str, t: sa.TableValuedAlias) -> None:
        """Set an aliased table on the transaction. This is allows us to use postgres functions easily with the `oqm`.
        See `oqm.alias`

        Args:
            name (str): The name to use for later lookup.
            t (sa.TableValuedAlias): The TableValuedAlias
        """
        self._aliased_tables[name] = t

    def get_aliased(self, name: str) -> sa.TableValuedAlias:
        """Retrieve an instance of TableValuedAlias that was defined elsewhere and stored in the current transaction
        at an earlier point.

        Args:
            name (str): The name to use for lookup.

        Returns:
            sa.TableValuedAlias: The TableValuedAlias
        """
        return self._aliased_tables[name]

    def get_table(self, name: str) -> sa.Table:
        """Get a reference to a table in the database. Should only be called after reflect.

        Args:
            name (str): The name of the table

        Returns:
            sa.Table: The table.
        """
        return self.metadata.tables[name]

    def _gather_unique_contstraints(
        self, metadata: sa.MetaData, inspector: sa.Inspector
    ) -> None:
        tablenames: List[Tuple[str, Optional[str]]] = [
            (t.name, t.schema) for t in metadata.sorted_tables
        ]
        for t, s in tablenames:
            ucs = inspector.get_unique_constraints(t, s)  # list[dict]
            for uc in ucs:
                k: str = f"{s}.{t}" if s else t
                self._constraints[k] = uc["column_names"]

    def get_unique_constraint(self, name: str) -> List[str]:
        """Get a unique constraint by key name. This works well if you name your unique constraints
        which you really should.

        Args:
            name (str): The name of the constraint

        Returns:
            List[str]: A list of the column names associated with that constraint.
        """
        return self._constraints[name]


class TransactionManager(object):
    __slots__ = ("_conn", "_db", "_aliased_tables")

    def __init__(self, conn: AsyncConnection, db: DataAccessLayer):
        """Manages the lifecycle of a transaction and allows us to proxy into both the connection
        instance and other attributes of the DataAccessLayer without needing a direct ref to the DAL.

        You should not really instantiate this yourself but use with a dedicated async context manager such
        as `transaction`.

        Args:
            conn (AsyncConnection): The current connection.
            db (DataAccessLayer): A "parent" DataAccessLayer.
        """
        self._conn = conn
        self._db = db
        self._aliased_tables: Dict[str, sa.TableValuedAlias] = {}

    @property
    def conn(self) -> AsyncConnection:
        return self._conn

    @property
    def engine(self) -> AsyncEngine:
        return self._db.engine

    def set_aliased(self, name: str, t: sa.TableValuedAlias) -> None:
        """Set an aliased table on the transaction itself. This is allows us to use functions we define for select statements
        easily. This does not overwrite any aliased tables set in the underlying DataAccessLayer.

        Args:
            name (str): The name to use for later lookup.
            t (sa.TableValuedAlias): The TableValuedAlias
        """
        self._aliased_tables[name] = t

    def get_aliased(self, name: str) -> sa.TableValuedAlias:
        """Retrieve an instance of TableValuedAlias that was defined elsewhere and stored in the current transaction. If
        `name` matches a name in DataAccessLayer._aliased_tables the transaction's alias will be returned first. If no
        alias with `name` in transaction is found then it will check DataAccessLayer. This will fail with a typical KeyError if
        it does not exist in DataAccessLayer.

        Args:
            name (str): The name to use for lookup.

        Returns:
            sa.TableValuedAlias: The TableValuedAlias
        """

        alias = self._aliased_tables.get(name)
        if alias is None:
            return self._db.get_aliased(name)
        else:
            return alias

    def get_table(self, name: str) -> sa.Table:
        """Get a table or view from the dal.

        Args:
            name (str): The name to use for lookup. This should be the name defined in the database.

        Returns:
            sa.Table: The Table.
        """
        return self._db.get_table(name)

    def get_unique_constraint(self, tablename: str) -> List[str]:
        """Get a unique constraint from the dal.

        Args:
            name (str): The tablename

        Returns:
            List[str]: List of column names
        """
        return self._db.get_unique_constraint(tablename)

    async def get_dbapi_connection(self) -> Any | None:
        """Shortcut for returning the underlying dbapi driver connection.
        This cuts out several proxy layers.  Handle with care.

        From https://docs.sqlalchemy.org/en/20/faq/connections.html#accessing-the-underlying-connection-for-an-asyncio-driver/

        According to the docs this raw connection is returned to the pool just like any other
        sqlalchemy connection. The execution options should not be modified or we could poison the
        connection pool.

        NOTE that that execute commands on this raw connection will _NOT_ automatically be
        part of the open sqla transaction that TransactionManager governs. If multiple statements
        need to be executed by this connection you should use the driver to open a nested transaction and
        allow any errors to propagate.

        Returns:
            Any | None: Generic raw driver. Should assert type before use.
        """
        fairy = await self._conn.get_raw_connection()
        return fairy.driver_connection

    async def execute(
        self,
        statement: expression.Executable,
        parameters: _CoreAnyExecuteParams | None = None,
        *,
        execution_options: CoreExecuteOptionsParameter | None = None,
    ) -> ResultProxy[Any]:
        """Execute a sqlalchemy statement on the connection.

        Args:
            executable (expression.Executable): The expression to run.

        Returns:
            ResultProxy: A ResultProxy
        """
        return await self._conn.execute(
            statement, parameters, execution_options=execution_options
        )

    async def commit(self) -> None:
        """Call commit on the current connection."""
        await self._conn.commit()

    async def rollback(self) -> None:
        """Call rollback on the current connection."""
        await self._conn.rollback()


@contextlib.asynccontextmanager
async def transaction(
    db: DataAccessLayer, with_commit: bool = True
) -> AsyncIterator[TransactionManager]:
    """This is the "public" API for a transaction. It assures that if any exception occurs after
    the transaction manager is yielded

    Args:
        db (DataAccessLayer): _description_
        with_commit (bool, optional): _description_. Defaults to True.

    Returns:
        AsyncIterator[TransactionManager]: _description_

    Yields:
        Iterator[AsyncIterator[TransactionManager]]: _description_
    """

    async with db.engine.connect() as conn:
        transaction = TransactionManager(conn, db)
        try:
            yield transaction
            if with_commit:
                await transaction.commit()
        except Exception:
            await transaction.rollback()
            raise
