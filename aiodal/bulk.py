# type: ignore
""" An interface for using bulk insert/upsert/export via asyncpg `COPY`.
These are essentially wrappers around asyncpg.Connection.copy_to_table and asyncpg.Connection.copy_from_query

Inserting creates a script that uses the following basic steps.
1. create temp table (on commit drop).
2. bulk COPY data from a file (csv/jsonl/text) into the temp table.
3. insert/upsert data into the actual table.

Each of the above can have pre and post hooks that default to None.

A BulkUploadScript class manages the entire transaction and is passed a list of BulkLoad 
objects and simply calls each in a row.

Exporting is simpler and is controlled by a single query.
1. Export using copy given a specific query to a file / stdout.

"""
import abc
from typing import Any, AsyncIterable, BinaryIO, Sequence, Tuple, Callable, Coroutine
from os import PathLike
import asyncpg  # type: ignore
from dataclasses import dataclass


class IOpExecutor(abc.ABC):
    @abc.abstractmethod
    async def execute(self, conn: asyncpg.Connection) -> str:
        ...


class StmtOp(IOpExecutor):
    def __init__(
        self,
        execute_args: Tuple[Any, ...] = (),
        timeout: int = 10,
    ):
        self.execute_args = execute_args
        self.timeout = timeout

    @abc.abstractmethod
    def stmt(self) -> str:
        ...

    async def execute(self, conn: asyncpg.Connection) -> str:
        return await conn.execute(self.stmt(), *self.execute_args, timeout=self.timeout)  # type: ignore[no-any-return]


@dataclass
class TableColumn:
    name: str
    col_type: str
    postfix: str = ""

    def __repr__(self) -> str:
        return f"{self.name} {self.col_type} {self.postfix}"


@dataclass
class TableColumns:
    cols: Sequence[TableColumn]

    def __repr__(self) -> str:
        len_cols = len(self.cols)
        out = ""
        for i, c in enumerate(self.cols):
            out += str(c)
            if i != len_cols - 1:
                out += ","
        return out


class TempTableOp(StmtOp):
    def __init__(
        self,
        tablename: str,
        cols: TableColumns,
        execute_args: Tuple[Any, ...] = (),
        timeout: int = 10,
    ):
        self.tablename = tablename
        self.cols = cols
        super().__init__(execute_args, timeout)

    def stmt(self) -> str:
        return f"create temp table {self.tablename} ({self.cols}) on commit drop;"


class LoadOpHandler(IOpExecutor):
    def __init__(
        self,
        tmp: TempTableOp,
        target: StmtOp,
        source: PathLike[Any] | BinaryIO | AsyncIterable[bytes],
        post_copy: StmtOp | None = None,
        **copy_kwargs: Any,
    ):
        self.tmp = tmp
        self.target = target
        self.post_copy = post_copy
        self.source = source
        self.copy_kwargs = copy_kwargs

    async def execute(self, conn: asyncpg.Connection) -> str:
        out = ""
        result = await self.tmp.execute(conn)
        out += result + "\n"

        result = await conn.copy_to_table(
            self.tmp.tablename, source=self.source, **self.copy_kwargs
        )

        if self.post_copy:
            result = await self.post_copy.execute(conn)
            out += result + "\n"

        result = await self.target.execute(conn)
        out += result + "\n"

        return out


class BulkLoadScript:
    def __init__(
        self,
        url: str,
        ops: Sequence[LoadOpHandler],
        verbose: bool = True,
        **connect_kwargs: Any,
    ):
        self.url = url
        self.ops = ops
        self.verbose = verbose
        self.connect_kwargs = connect_kwargs

    async def run(self, verbose: bool = True) -> None:
        conn = await asyncpg.connect(self.url, **self.connect_kwargs)
        async with conn.transaction():
            for op in self.ops:
                result = await op.execute(conn)
                if verbose:
                    print(result)


class ExportOpHandler(IOpExecutor):
    def __init__(
        self,
        query: str,
        output: PathLike[Any] | BinaryIO | Callable[[bytes], Coroutine[Any, Any, None]],
        query_args: Tuple[Any, ...] = (),
        **copy_kwargs: Any,
    ):
        self.query = query
        self.output = output
        self.query_args = query_args
        self.copy_kwargs = copy_kwargs

    async def execute(self, conn: asyncpg.Connection) -> str:
        return await conn.copy_from_query(  # type: ignore[no-any-return]
            self.query, *self.query_args, output=self.output, **self.copy_kwargs
        )
