# aiodal 
--- 
A small toolset for working with sqlalchemy core using the reflection API and asyncio extension. 

Supports sqlalchemy 1.4+ and 2.x, alembic 1.x and asyncpg.  

## about
---- 

What about the ORM? We've been using sqlalchemy for many years in a variety of contexts. We made the transition away from the ORM for several reasons. 

* We use timescaledb which did not play nice with ORM and alembic. There were some hacky solutions but basically autogenerate did not work very well and we had to write our alembic migrations by hand anyway (which isn't really that complicated honestly).
* We often need to write alot of complicated queries and/or interact with the postgresql extension which we found much easier to manage using the core API.  
* When asyncio support was introduced the ORM was not available to us. We prefer async python in our stack.  
* We use pydantic for object modeling and many of these models do not always map directly to a database table, but rather a query. We found it inconvenient and redundent to keep lots of models around for different these different contexts

After doing a number of projects without the ORM we've found we don't really miss it all that much. Using `core` with the reflection API keeps the parts of our business logic related to querying away from object serialization and other application code which is nice.   

This little API is the backbone of most of our database and rest API projects.

The `DataAccessLayer` class is the centerpiece and acts as a controller and proxy. It is borrowed from an old book on sqlalchemy back from before the ORM was even a thing by Rick Copeland. You call `await reflect` by passing in an engine and the dal will keep an instance of MetaData populated for the duration of your app. We also include automatically include views and allow for convenient lookup of unique constraints.  

A `TransactionManager` is created via an async `contextmanager` by passing in a connection and a reference to the dal instance. This wraps some of the basic patterns found in the documentation for sqlalchmey 1.4+. We yield this transaction and do our work. It will automatically commit or rollback on error. This is a pretty standard pattern we've written a million times. 

I've included a json encoder that we use that will handle enums and datetimes.  

Most useful is the pytest plugin. This will allow a number of fixtures to be made available to you and handles running migrations via alembic. This is in the style of django where a test database will be spun up and torn down. It works by pointing it to an alembic.ini file which can be set in pytests ini config (default is to use alembic.ini at project root). There are several session scoped fixtures that essentially let you turn this behavior on and off if you need to work with a persistent test database and manage data migrations without alembic. 

A transaction fixture is provided that will automatically rollback tests as well as entrypoints to swap out the `json_encoder`. Again this all follows basic patterns found in numerous libraries. 

Note that we are using anyio for testing and automatically configure the event loop at session scope to use `asyncio`. This can be modified but should remain at session scope to avoid issues with the event loop.

## future work

Future work will include building a `mixins.py` that would provide interfaces for basic CRUD ops and filtering that could be used with any object. Still spec'ing this out but the goal would be to allow the API to be mixed in to a library like pydantic without tightly coupling it. 

Also I might add some functionality for postgres specific sqlalchemy API like `on_conflict_do_update` for upsert which is extremely useful.
