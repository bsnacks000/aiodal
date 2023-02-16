
import contextlib
import json 
import datetime
import enum

from typing import List, AsyncIterator, Any
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncConnection
import sqlalchemy as sa 
from sqlalchemy.sql import expression
from sqlalchemy.engine import ResultProxy

class DataAccessLayer: 

    _constraints = {}


    def __init__(self):
        self._engine = None 
        self._metadata = None 
        self._inspector = None 
    
    @property 
    def metadata(self): 
        return self._metadata 


    @property 
    def engine(self) -> AsyncEngine: 
        return self._engine 


    async def reflect(self, engine: AsyncEngine, metadata: sa.MetaData) -> None: 
        """Reflect the metadata via the engine. Must be called at init time.

        Args:
            engine (AsyncEngine): _description_
            metadata (sa.MetaData): _description_
        """
        
        def _reflect(con): 
            metadata.reflect(bind=con, views=True)
            inspector = sa.inspect(con)
            tablenames = [t.name for t in metadata.sorted_tables]
            for t in tablenames: 
                ucs = inspector.get_unique_constraints(t) # list[dict]
                for uc in ucs: 
                    self._constraints[t] = uc['column_names']

        async with engine.connect() as conn:
            await conn.run_sync(_reflect)
        
        self._engine = engine 
        self._metadata = metadata 


    def get_table(self, name: str) -> sa.Table:
        return self._metadata.tables[name]


    def get_unique_constraint(self, name: str) -> List[str]: 
        return self._constraints[name]




class TransactionManager(object): 
    """ Proxy into an instance of AsyncConnection and DataAccesLayer
    """

    def __init__(self, conn: AsyncConnection, db: DataAccessLayer): 
        self._conn = conn 
        self._db = db 


    def get_table(self, name: str) -> sa.Table: 
        return self._db.get_table(name)


    def get_unique_constraint(self, name: str) -> List[str]: 
        return self._db.get_unique_constraint(name)


    async def execute(self, executable: expression.Executable) -> ResultProxy:
        return await self._conn.execute(executable)


    async def commit(self) -> None: 
        await self._conn.commit()


    async def rollback(self) -> None: 
        await self._conn.rollback()



@contextlib.asynccontextmanager
async def transaction(db: DataAccessLayer, with_commit: bool=True) -> AsyncIterator[TransactionManager]:
    async with db.engine.connect() as conn:
        transaction = TransactionManager(conn, db)
        try:
            yield transaction 
            if with_commit:
                await transaction.commit()
        except Exception: 
            await transaction.rollback()
            raise 


class CustomJsonEncoder(json.JSONEncoder):
    """ This class extends the builtin json encoder to handle datetime.date and enum objects 
    the way we want for database serialization with JSONB. 
    """ 
    def default(self, o: Any):
        if isinstance(o, datetime.date): 
            return o.strftime("%Y-%m-%d")
        elif isinstance(o, enum.Enum): 
            return o.value 
        return super().default(o)


def custom_json_encoder(o: Any) -> str: 
    return json.dumps(o, cls=CustomJsonEncoder)