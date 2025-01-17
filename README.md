# aiodal 
--- 

A small toolset for working with sqlalchemy core using the reflection API and asyncio extension. 

Going forward this library only supports postgres via `asyncpg` and uses `sqlalchemy>=2`

## dal 

The `dal` module is a wrapper around a sqlalchemy engine with some useful functionality for managing transactions. It is based loosely on patterns from Myers __Essential Sqlalchemy__
which date back to before the ORM was introduced. 

We prefer to use `pydantic` as our object mapping layer which is more flexible in development. The Sqlalchemy tables are
reflected and held by a DataAccessLayer instance at object start. 

```python
engine = create_async_engine("...")
meta = sa.Metadata()

db = DataAccessLayer()
await db.reflect(engine, meta)

```

The instance is essentially just a proxy into the `engine` with a simpler API and easier access to some of the underlying objects. 

Similarly we use a `TransactionManager` to proxy into an `AsyncConnection` instance. 

```python
async with db.engine.connect() as conn:
    transaction = TransactionManager(conn, db)

    #... do stuff with the transaction instance
```

Usually we use `TransactionManager` in an `asynccontextmanager`. We provide a simple one by default, though it is very easy to build this in an application. A similar pattern is common as a FastAPI dependency. 

```python
async with dal.transaction() as transaction: 
    # ... do stuff  
```

On both `DataAccessLayer` and `TransactionManager` we offer a few helper methods to get at some underlying object metadata such as unique constraints and tables. We reflect views by default and cache any TableValuedAlias and unique constraints for easier lookup. 


## pytest_plugin

Probably most useful is the pytest plugin. We've chosen to decouple it from `alembic` which means your dev environment will have to manage set up and tear down for any tests. You can look at our `docker-compose.yaml` file to see how this can be done using `psql` for isolating local tests. 

There are a number of python fixutres provided to setup an engine, but the minimal conftest should just need the following.
```python 
# conftest.py 

#1. Set anyio backend fixture scoped to session 
@pytest.fixture(scope="session")
def anyio_backend():
    """Override this to use a different backend for testing"""
    return "asyncio"

# 2. provide the testdb you are connecting to.
@pytest.fixture(scope="session")
def engine_uri() -> str:
    return "postgresql+asyncpg://user:pass@host:port/dbname

```

To see the other overrides you can look at `aiodal.pytest_plugin`. 

This give you access to an active `transaction` fixture that you can pass around. This is a common pattern found in alot of projects and is nothing new. Its default is to rollback after each test case.  

## bulk 

In `0.7` we decided to use the `asyncpg` library itself in order to create a `bulk` data loading API centered around postgres' powerful `COPY` command. The purpose of this was to create a programmatic and optimized API to facilitate writing testable bulk loading scripts and clis.

A common ETL practice with `psql` for bulk copying data is to stage the data into a `temp table` on the postgres server from csv before munging it into its appropriate tables. 

See `tests/test_bulk.py` for an example of how to set up ETL with `bulk` classes.



## web 


#### slack notifier

Below demonstrates adding slack notifier as middleware to log unhandle error responses from routes and internals

```python
from aiodal.web.slack_notify import SlackNotifier
from aiodal.web.auth import Auth0
# authentication set up
auth = Auth0(domain=AUTH0_TESTING_DOMAIN, api_audience=AUTH0_TESTING_API_AUDIENCE)
app = FastAPI(lifespan=lifespan)
# slack_notifier obj
slack_notifier = SlackNotifier(authentication=auth, webhook_url=WEBHOOK_URL, environtments_trigger=["testing"])


# add slack_notifier as middileware
@app.middleware("http")
async def slack_notify_middleware(request: Request, call_next: Any):  # type: ignore
    try:
        response = await call_next(request)
    except Exception as err:
        await slack_notifier.slack_notify(request, err, "testing")
        raise  # let starlette handle it with a plain 500
    return response


@app.get("/error")
async def endpoint_with_error():
    raise ValueError("hello from aiodal testing!") 
    # return {"message": "Anonymous user"}
```
Above, if `/error` route is called, it will raise error and the error will get sent to appropriate channel in slack pointed by `WEBHOOK_URL`. `auth` will provide user information on who's caused the error.

Moreover, one can construct a route to foward error into slack with `aiodal.web.slack_notify.send_slack_message`
```python
from aiodal.web.slack_notify import SlackLogger, send_slack_message
router = APIRouter(prefix="/slack")

@router.post("/", status_code=204)
async def forward_slack_logger(
    payload: SlackLogger,
) -> Response:
    response = await send_slack_message(_WEBHOOK_URL, blocks=payload.blocks)
    if response.status_code != 200:
        logger.error(
            f"Slack webhook call failed with status code {response.status_code}\n {response.text}"
        )
        return Response(content=response.text, status_code=response.status_code)
    return Response(status_code=204)
```