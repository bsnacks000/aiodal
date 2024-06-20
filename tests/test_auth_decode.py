import pytest
import sqlalchemy as sa
import os
from aiodal.web import auth
import json
from .conftest import AUTH0_TESTING_API_AUDIENCE, AUTH0_TESTING_DOMAIN

pytestmark = pytest.mark.anyio


class DummyUser(auth.Auth0User): ...


@pytest.mark.e2e
async def test_decode_token(authapp_access_token):

    access_token = authapp_access_token
    auth0 = auth.Auth0(
        domain=AUTH0_TESTING_DOMAIN,
        api_audience=AUTH0_TESTING_API_AUDIENCE,
        user_model=DummyUser,
    )
    auth0.initialize_jwks()
    payload = auth0._decode_token(access_token)
