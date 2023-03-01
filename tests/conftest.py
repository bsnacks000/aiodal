import pytest 

# NOTE must add this to local scope
@pytest.fixture(scope='session')
def anyio_backend():
    """ Override this to use a different backend for testing 
    """
    return 'asyncio'