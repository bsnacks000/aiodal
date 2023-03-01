import contextlib
from typing import List, AsyncIterator, Optional, Any
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncConnection

import sqlalchemy as sa
from sqlalchemy.sql import expression
from sqlalchemy.engine import ResultProxy


class DataAccessLayer(object):
    """The main controller for sqla db access. We use the reflection API via the reflect method which
    serves as the true initialization of the object. This is done for common cases such as web apps when we
    need to a db instance around but need to connect to the db as part of a startup hook. This object will hold
    references to AsyncEngine, MetaData, Inspector as well as populate any unique_constraints in the database.
    """

    _constraints: dict[str, List[str]] = {}

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
        views: bool = True,
    ) -> None:
        """Takes an AsyncEngine and uses sqlalchemy reflection API to reflect the table data.
        Sets this state on the object.

        Ex.
        engine = create_async_engine(...)
        db = DataAccessLayer()
        await db.reflect(engine)   # success!

        Args:
            engine (AsyncEngine): An AsyncEngine
            metadata (Optional[sa.MetaData], optional): A MetaData instance,
                if not provided then automatically creates one. Defaults to None.
            views (bool, optional): Whether to reflect views. Defaults to True.
        """
        if not metadata:
            metadata = sa.MetaData()

        def _reflect(con: sa.Connection) -> sa.Inspector:
            assert metadata is not None

            metadata.reflect(bind=con, views=views)
            inspector = sa.inspect(con)
            tablenames = [t.name for t in metadata.sorted_tables]
            for t in tablenames:
                ucs = inspector.get_unique_constraints(t)  # list[dict]
                for uc in ucs:
                    self._constraints[t] = uc["column_names"]
            return inspector

        async with engine.connect() as conn:
            self._inspector: sa.Inspector = await conn.run_sync(_reflect)

        self._engine = engine
        self._metadata = metadata

    def get_table(self, name: str) -> sa.Table:
        """Get a reference to a table in the database. Should only be called after reflect.

        Args:
            name (str): The name of the table

        Returns:
            sa.Table: The table.
        """
        return self._metadata.tables[name]

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
    __slots__ = ("_conn", "_db")

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

    def get_table(self, name: str) -> sa.Table:
        """Get a table from the dal.

        Args:
            name (str): _description_

        Returns:
            sa.Table: _description_
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

    async def execute(self, executable: expression.Executable) -> ResultProxy[Any]:
        """Execute a sqlalchemy statement on the connection.

        Args:
            executable (expression.Executable): The expression to run.

        Returns:
            ResultProxy: A ResultProxy
        """
        return await self._conn.execute(executable)

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
