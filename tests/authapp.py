# only need this to make a mock app for testing aiodal.web.auth

from typing import Optional, AsyncGenerator, Any
from fastapi import FastAPI, Depends, Security, Request, HTTPException
from pydantic import Field
from contextlib import asynccontextmanager

from aiodal.web.auth import Auth0, Auth0User, security_responses
from aiodal.web.slack_notify import SlackNotifier, send_slack_message
import os


###############################################################################
class CustomAuth0User(Auth0User):
    grant_type: Optional[str] = Field(None, alias="gty")


###############################################################################

AUTH0_TESTING_DOMAIN = "dev-qfnm6uuqxtjs3l44.us.auth0.com"
AUTH0_TESTING_API_AUDIENCE = "https://aiodal.ci.dev"
WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")


auth = Auth0(domain=AUTH0_TESTING_DOMAIN, api_audience=AUTH0_TESTING_API_AUDIENCE)
auth_custom = Auth0(
    domain=AUTH0_TESTING_DOMAIN,
    api_audience=AUTH0_TESTING_API_AUDIENCE,
    user_model=CustomAuth0User,
)


@asynccontextmanager
async def lifespan(
    app: FastAPI,
) -> AsyncGenerator[Any, Any]:
    auth.initialize_jwks()
    auth_custom.initialize_jwks()
    yield


app = FastAPI(lifespan=lifespan)
slack_notifier = SlackNotifier(auth0_model=auth, webhook_url=WEBHOOK_URL)


@app.middleware("http")
async def slack_notify_middleware(request: Request, call_next: Any):  # type: ignore
    try:
        response = await call_next(request)
    except Exception as err:
        await slack_notifier.slack_notify(request, err, "testing")
        raise  # let starlette handle it with a plain 500
    return response


@app.get("/public")
async def get_public():
    return {"message": "Anonymous user"}


@app.get("/error")
async def get_raise_error():
    raise ValueError("hello from aiodal testing!")
    # return {"message": "Anonymous user"}


@app.get("/also-public", dependencies=[Depends(auth.implicit_scheme)])
async def get_public2():
    return {
        "message": "Anonymous user (token is received from swagger ui but not verified)"
    }


@app.get(
    "/secure",
    dependencies=[Depends(auth.implicit_scheme)],
    responses=security_responses,
)
async def get_secure(user: Auth0User = Security(auth.get_user)):
    return user


@app.get("/also-secure")
async def get_also_secure(user: Auth0User = Security(auth.get_user)):
    return user


@app.get("/also-secure-2", dependencies=[Depends(auth.get_user)])
async def get_also_secure_2():
    return {"message": "I dont care who you are but I know you are authorized"}


@app.get("/secure-scoped")
async def get_secure_scoped(
    user: Auth0User = Security(auth.get_user, scopes=["read:scope1"])
):
    return user


@app.get("/secure-custom-user")
async def get_secure_custom_user(
    user: CustomAuth0User = Security(auth_custom.get_user),
):
    return user
