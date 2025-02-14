from aiodal.web import auth
import pytest
from fastapi import HTTPException
from fastapi.security import SecurityScopes, HTTPAuthorizationCredentials
import pytest
from typing import Dict, Any
import jwt

pytestmark = pytest.mark.anyio


def test_check_for_orgid():
    payload = {"org_id": "cia"}
    auth_ = auth.Auth0(
        domain="verynice",
        api_audience="wild",
        org_id="cia",
        scopes={"read:scope": "read scope"},
    )
    auth_.check_for_org_id(payload)
    auth_.check_for_org_id({})  # no org_id so it passes

    with pytest.raises(auth.Auth0UnauthorizedException):
        auth_.check_for_org_id({"org_id": "yeah"})


def test_check_for_grant_type():
    payload = {"gty": "client-credentials"}
    auth_ = auth.Auth0(
        domain="verynice",
        api_audience="wild",
        org_id="cia",
        scopes={"read:scope": "read scope"},
    )
    auth_.check_for_grant_type(payload)
    auth_.check_for_grant_type({})  # no gty so it passes

    with pytest.raises(auth.Auth0UnauthorizedException):
        auth_.check_for_grant_type({"gty": "yeah"})


def test_check_for_scopes():
    payload = {"scope": "read:scope1 read:scope2"}
    # this may get set by fastapi during dependency injection; here it doesn't matter so faking it
    security_scopes = SecurityScopes(scopes=["read:scope1", "read:scope2"])
    auth_ = auth.Auth0(
        domain="verynice",
        api_audience="wild",
        org_id="cia",
        # this may work in tandem with fastapi security module
        scopes={
            "read:scope1": "read scope 1",
            "read:scope2": "read scope 2",
        },
    )

    auth_.check_for_scopes(security_scopes=security_scopes, payload=payload)

    with pytest.raises(auth.Auth0UnauthorizedException):
        auth_.check_for_scopes(
            security_scopes=security_scopes,
            payload={"scope": "read:scope1 read:notscope"},
        )

    # scope not str
    with pytest.raises(auth.Auth0UnauthorizedException):
        auth_.check_for_scopes(
            security_scopes=security_scopes,
            payload={"scope": {"attack": "Attack!"}},
        )


def test_parse_user_from_payload():
    payload = {"sub": "whatsup", "permissions": ["crude"], "email": "blah@yada.com"}
    auth_ = auth.Auth0(
        domain="verynice",
        api_audience="wild",
        org_id="cia",
        scopes={"read:scope": "read scope"},
    )

    auth_._parse_user_from_payload(payload)

    auth_.email_auto_error = True
    payload.pop("email")
    with pytest.raises(auth.Auth0UnauthorizedException):
        auth_._parse_user_from_payload(payload)  # email not present

    # pydantic validation error
    with pytest.raises(auth.Auth0UnauthorizedException):
        auth_._parse_user_from_payload(payload={"sup": "sup"})


def test_parse_user_from_payload_with_custom_model():
    payload = {
        "sub": "whatsup",
        "permissions": ["crude"],
        "email": "blah@yada.com",
        "extra": {"agencies": [1, 2]},
    }

    class Custom(auth.Auth0User):
        extra: Dict[str, Any]

    auth_ = auth.Auth0(
        domain="verynice",
        api_audience="wild",
        org_id="cia",
        scopes={"read:scope": "read scope"},
        user_model=Custom,
    )

    auth_._parse_user_from_payload(payload)

    auth_.email_auto_error = True
    payload.pop("email")
    with pytest.raises(auth.Auth0UnauthorizedException):
        auth_._parse_user_from_payload(payload)  # email not present

    # pydantic validation error
    with pytest.raises(auth.Auth0UnauthorizedException):
        auth_._parse_user_from_payload(payload={"sup": "sup"})
    # payload without extra
    payload["extra"] = 1
    payload["email"] = "good@email.com"
    with pytest.raises(auth.Auth0UnauthorizedException):
        auth_._parse_user_from_payload(payload=payload)


async def test_get_user(mocker):
    payload = {
        "sub": "whatsub",
        "permissions": ["crude"],
        # "email": "blah@yada.com",
        "scope": "read:scope1 read:scope2",
        "gty": "client-credentials",
        "org_id": "cia",
    }
    auth_ = auth.Auth0(
        domain="verynice",
        api_audience="wild",
        org_id="cia",
        scopes={"read:scope1": "read scope1", "read:scope2": "read scope 2"},
    )
    # mock decoder
    mocker.patch("aiodal.web.auth.Auth0._decode_token", return_value=payload)
    security_scopes = SecurityScopes(scopes=["read:scope1", "read:scope2"])
    cred = HTTPAuthorizationCredentials(
        scheme="Auth0ImplicitBearer", credentials="tolkien_black"
    )
    res = await auth_.get_user(security_scopes, cred)
    assert res.id == "whatsub"
    # XXX email name space must be defined in auth0 rule
    # assert res.email == "blah@yada.com"
    assert res.permissions == ["crude"]


async def test_get_user_with_exceptions(mocker):
    auth_ = auth.Auth0(
        domain="verynice",
        api_audience="wild",
        org_id="cia",
        scopes={"read:scope1": "read scope1", "read:scope2": "read scope 2"},
    )

    security_scopes = SecurityScopes(scopes=["read:scope1", "read:scope2"])
    # cred is none --> i.e no token
    with pytest.raises(HTTPException):
        await auth_.get_user(security_scopes, None)

    cred = HTTPAuthorizationCredentials(
        scheme="Auth0ImplicitBearer", credentials="tolkien_black"
    )

    # general exception
    with pytest.raises(auth.Auth0UnauthenticatedException):

        def _raise_error(token: str):
            raise Exception

        mocker.patch("aiodal.web.auth.Auth0._decode_token", side_effect=_raise_error)
        await auth_.get_user(security_scopes, cred)

    # jwt.ExpiredSignatureError
    with pytest.raises(auth.Auth0UnauthenticatedException):

        def _raise_error(token: str):
            raise jwt.ExpiredSignatureError

        mocker.patch("aiodal.web.auth.Auth0._decode_token", side_effect=_raise_error)
        await auth_.get_user(security_scopes, cred)

    # jwt.JWTClaimsError
    with pytest.raises(auth.Auth0UnauthenticatedException):

        def _raise_error(token: str):
            raise jwt.JWTClaimsError

        mocker.patch("aiodal.web.auth.Auth0._decode_token", side_effect=_raise_error)
        await auth_.get_user(security_scopes, cred)

    # jwt.JWTError
    with pytest.raises(auth.Auth0UnauthenticatedException):

        def _raise_error(token: str):
            raise jwt.JWTError

        mocker.patch("aiodal.web.auth.Auth0._decode_token", side_effect=_raise_error)
        await auth_.get_user(security_scopes, cred)

    # Auth0UnauthenticatedException raise from _decode_token
    with pytest.raises(auth.Auth0UnauthenticatedException):

        def _raise_error(token: str):
            raise auth.Auth0UnauthenticatedException("invalid header")

        mocker.patch("aiodal.web.auth.Auth0._decode_token", side_effect=_raise_error)
        await auth_.get_user(security_scopes, cred)

    payload = {
        "sub": "whatsub",
        "permissions": ["crude"],
        # "email": "blah@yada.com",
        "scope": "read:scope1 read:scope2",
        "gty": "client-credentials",
        "org_id": "cia",
    }
    # Auth0UnauthorizedException
    with pytest.raises(auth.Auth0UnauthorizedException):
        payload["gty"] = "something_wrong"
        mocker.patch("aiodal.web.auth.Auth0._decode_token", return_value=payload)
        await auth_.get_user(security_scopes, cred)

    payload["gty"] = "client-credentials"  # reset
    payload["org_id"] = "fbi"
    with pytest.raises(auth.Auth0UnauthorizedException):
        mocker.patch("aiodal.web.auth.Auth0._decode_token", return_value=payload)
        await auth_.get_user(security_scopes, cred)

    payload["org_id"] = "cia"  # reset
    payload.pop("sub")
    with pytest.raises(auth.Auth0UnauthorizedException):
        mocker.patch("aiodal.web.auth.Auth0._decode_token", return_value=payload)
        await auth_.get_user(security_scopes, cred)


async def test_decode_token_mocked(mocker):
    unverified_header = {"kid": "veryrealkid"}

    keys = {
        "kid": "veryrealkid",
        "kty": "RSA",
        "use": "veryreal_use",
        "n": "veryreal_n",
        "e": "veryreal_e",
    }

    mocker.patch.object(
        jwt.PyJWKClient,
        "get_signing_key_from_jwt",
        return_value=jwt.PyJWK.from_dict(keys),
    )

    payload = {
        "sub": "whatsub",
        "permissions": ["crude"],
        # "email": "blah@yada.com",
        "scope": "read:scope1 read:scope2",
        "gty": "client-credentials",
        "org_id": "cia",
    }
    auth_ = auth.Auth0(
        domain="verynice",
        api_audience="wild",
        org_id="cia",
        scopes={"read:scope1": "read scope1", "read:scope2": "read scope 2"},
    )
    auth_.jwks = jwt.PyJWKClient("https://fake.url")
    auth_.algorithms = ["RSA"]
    mocker.patch("jwt.get_unverified_header", return_value=unverified_header)

    mocker.patch("jwt.decode", return_value=payload)
    exp_payload = auth_._decode_token("token")


@pytest.mark.skip("deprecated")
async def test_decode_token_kid_missing_error(mocker):
    mocker.patch("jwt.get_unverified_header", return_value={})

    auth_ = auth.Auth0(
        domain="verynice",
        api_audience="wild",
        org_id="cia",
        scopes={"read:scope1": "read scope1", "read:scope2": "read scope 2"},
    )

    with pytest.raises(auth.Auth0UnauthenticatedException):
        auth_._decode_token("token")


@pytest.mark.skip("deprecated")
async def test_decode_token_kid_mismatch_error(mocker):
    unverified_header = {"kid": "extrarealkid"}

    keys = {
        "kid": "veryrealkid",
        "kty": "RSA",
        "use": "veryreal_use",
        "n": "veryreal_n",
        "e": "veryreal_e",
    }

    mocker.patch.object(
        jwt.PyJWKClient,
        "get_signing_key_from_jwt",
        return_value=jwt.PyJWK.from_dict(keys),
    )

    auth_ = auth.Auth0(
        domain="verynice",
        api_audience="wild",
        org_id="cia",
        scopes={"read:scope1": "read scope1", "read:scope2": "read scope 2"},
    )

    auth_.jwks = jwt.PyJWKClient("https://fake.url")
    auth_.algorithms = ["RSA"]
    mocker.patch("jwt.get_unverified_header", return_value=unverified_header)
    with pytest.raises(auth.Auth0UnauthenticatedException):
        auth_._decode_token("token")
