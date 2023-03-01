import pytest

POSTGRES_TEST_URI = "postgresql+asyncpg://bsnacks000:iamgroot666@tsdb:5432/testdb"


# NOTE must add this to local scope
@pytest.fixture(scope="session")
def anyio_backend():
    """Override this to use a different backend for testing"""
    return "asyncio"


@pytest.fixture(scope="session")
def postgres_testdb_uri() -> str:
    return POSTGRES_TEST_URI
