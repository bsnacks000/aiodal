# aiodal 
--- 
A small toolset for working with sqlalchemy core using the reflection API and asyncio extension. 

Supports sqlalchemy 2.x.  

## about
---- 

What about the ORM? We've been using `sqlalchemy` for many years in a variety of contexts. We made the transition away from the ORM for several reasons. 

* We use timescaledb which did not play nice with ORM and alembic. There were some hacky solutions but basically autogenerate did not work very well and we had to write our alembic migrations by hand anyway (which isn't really that complicated honestly).
* We often need to write alot of complicated queries and/or interact with the postgresql extension (tsdb, crosstab) which we found much easier to manage using the core API.  
* When asyncio support was first introduced we could only use it with core and have developed alot of projects without the ORM. We prefer async python in our stack.  
* We use pydantic for object modeling and many of these models do not always map directly to a database table, but rather a complicated. We found it inconvenient and redundent to keep lots of models around for these different contexts

After doing a number of projects without the ORM we've found we don't really miss it all that much. Using `core` with the reflection API keeps the parts of our business logic related to querying away from object serialization and other application code which is nice. There are generally only one set of "models" for the project and these are often used with pydantic.

This little API is the backbone of most of our database and rest API projects.

The `DataAccessLayer` class is the centerpiece and acts as a controller and proxy. It is borrowed from an old book on sqlalchemy back from before the ORM was even a thing by Rick Copeland. It's designed to be instantiated in two parts so you can lazily initialize the db connection if need be. You call `await reflect` by passing in an engine and the dal will keep an instance of MetaData populated for the duration of your app. We also include automatically include views and allow for convenient lookup of unique constraints.  

A `TransactionManager` is created via an async `contextmanager` by passing in a connection and a reference to the dal instance. This wraps some of the basic patterns found in the documentation for sqlalchmey 1.4+. We yield this transaction which maintains a reference to both the dal itself and the active connection. It assures that the transaction will automatically commit after it goes out of scope or rollback on error. This is a pretty standard pattern we've written a million times. The same exact pattern works for a fastapi application using the dependency injection system.

I've included a json encoder that we use that will handle enums and datetimes.  

Even though we use postgres and I am testing this code using asyncpg and alembic this _should_ be compatible with any async sqlalchemy driver for any of the supported databases.

## pytest-plugin

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


## future work

Future work will include building a `mixins` module that would provide interfaces for basic CRUD ops and filtering that could be used with any object. Still spec'ing this out but the goal would be to allow the API to be mixed in to a library like pydantic without tightly coupling it. 

Also I might add some functionality for postgres specific sqlalchemy API like `on_conflict_do_update` for upsert which is extremely useful.
