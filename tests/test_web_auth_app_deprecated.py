from .authapp import app, CustomAuth0User

import pytest
from fastapi.testclient import TestClient
from aiodal.web.auth import Auth0User
import jwt

client = TestClient(app)


@pytest.mark.skip(reason="deprecated")
def test_public():
    resp = client.get("/public")
    assert resp.status_code == 200, resp.text

    resp = client.get("/also-public")
    assert resp.status_code == 200, resp.text

    resp = client.get("/secure")
    assert resp.status_code == 403, resp.text

    resp = client.get("/also-secure")
    assert (
        resp.status_code == 403
    ), resp.text  # should be 401, see https://github.com/tiangolo/fastapi/pull/2120

    resp = client.get("/also-secure-2")
    assert (
        resp.status_code == 403
    ), resp.text  # should be 401, see https://github.com/tiangolo/fastapi/pull/2120

    resp = client.get("/secure-scoped")
    assert (
        resp.status_code == 403
    ), resp.text  # should be 401, see https://github.com/tiangolo/fastapi/pull/2120


@pytest.mark.skip(reason="deprecated")
def test_private(authapp_access_token):
    headers = {"Authorization": authapp_access_token}
    resp = client.get("/secure", headers=headers)
    assert resp.status_code == 200, resp.text

    resp = client.get("/also-secure", headers=headers)
    assert resp.status_code == 200, resp.text

    resp2 = client.get("/also-secure-2", headers=headers)
    assert resp2.status_code == 200, resp2.text

    user = Auth0User(**resp.json())
    assert user.id == "whatsub"
    assert user.permissions == ["crude"]

    # M2M app is not subject to RBAC, so any permission given to it will also authorize the scope.
    resp = client.get("/secure-scoped", headers=headers)
    assert resp.status_code == 200, resp.text

    resp = client.get("/secure-custom-user", headers=headers)
    assert resp.status_code == 200, resp.text
    user = CustomAuth0User(**resp.json())
    assert user.grant_type in ["client-credentials", "client_credentials"]
