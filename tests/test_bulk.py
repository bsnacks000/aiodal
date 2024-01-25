import pytest
import pathlib
from aiodal import bulk

pytestmark = pytest.mark.anyio
import asyncpg

# bulk upload some authors and books using jsonl
# we will load this in as rows of jsonb and then munge them into the correct tables
# authors will have their ids assigned... the book insert op will need to do a lookup on authors.

fixture_dir = pathlib.Path(__file__).parent / "fixtures"


async def test_bulk_api(asyncpg_engine_uri):
    jsonl_cols = bulk.TableColumns(cols=[bulk.TableColumn("record", "jsonb")])

    # I predefined this op since its simple.
    tmp_auth = bulk.TempTableOp("author_tmp", cols=jsonl_cols)
    tmp_book = bulk.TempTableOp("book_tmp", cols=jsonl_cols)

    # load authors from temp table
    class AuthorJsonlLoadOp(bulk.StmtOp):
        def stmt(self) -> str:
            return """ 
                insert into author (name)
                    select 
                        (record->>'name')::varchar as name 
                    from author_tmp;
        """

    class BookLoadOp(bulk.StmtOp):
        def stmt(self) -> str:
            return """ 
                insert into book (author_id, name, catalog)
                    select 
                        (select au.id from author au where au.name = (bt.record->>'author')::varchar) as author_id,
                        (bt.record->>'name')::varchar as name,
                        (bt.record->>'catelog')::varchar as catalog
                    from book_tmp bt
        """

    author_load = AuthorJsonlLoadOp()
    book_load = BookLoadOp()

    auth_handler = bulk.LoadOpHandler(
        tmp=tmp_auth, target=author_load, source=fixture_dir / "authors.jsonl"
    )

    book_handler = bulk.LoadOpHandler(
        tmp=tmp_book, target=book_load, source=fixture_dir / "books.jsonl"
    )

    script = bulk.BulkLoadScript(
        url=asyncpg_engine_uri, ops=[auth_handler, book_handler], verbose=True
    )

    await script.run()

    conn = await asyncpg.connect(asyncpg_engine_uri)

    result = await conn.fetch("select * from author;")
    assert len(result) == 3

    result = await conn.fetch("select * from book;")
    assert len(result) == 3

    await conn.execute("delete from author; delete from book;")
