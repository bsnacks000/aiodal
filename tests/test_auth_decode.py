import pytest
import sqlalchemy as sa
import os
from aiodal.web import auth
import json

pytestmark = pytest.mark.anyio


class DummyUser(auth.Auth0User): ...


@pytest.mark.e2e
async def test_decode_token():
    AUTH0_DOMAIN = "dev-qfnm6uuqxtjs3l44.us.auth0.com"
    AUTH0_API_AUDIENCE = "https://testing.api"

    with open("./scripts/token.json", "r") as f:
        token_file = json.load(f)
        token = token_file["access_token"]

    AIODAL_E2E_ACCESS_TOKEN = token

    auth0 = auth.Auth0(
        domain=AUTH0_DOMAIN, api_audience=AUTH0_API_AUDIENCE, user_model=DummyUser
    )
    auth0.initialize_jwks()
    auth0._decode_token(AIODAL_E2E_ACCESS_TOKEN)
