import pytest

# from hivedb.api import log_handler
import httpx
import json
import fastapi

from aiodal.web.slack_notify import SlackNotifier, send_slack_message
from aiodal.web.auth import Auth0
from .conftest import WEBHOOK_URL

pytestmark = pytest.mark.anyio


dummy_auth = Auth0(domain="", api_audience="")
slack_notifier = SlackNotifier(auth0_model=dummy_auth, webhook_url=WEBHOOK_URL)


class DummyURL:

    def __init__(self, path: str):
        self.path = path


class DummyResponse:
    def __init__(self, status_code: int, body: str = ""):
        self.status_code = status_code
        self.body = body


class DummyRequest:

    def __init__(
        self,
        url: DummyURL,
        query_params: str,
        headers: dict[str, str] = {},
        method: str = "GET",
    ):
        self.url = url
        self.query_params = query_params
        self.method = method
        self.headers = headers

    async def body(self) -> str:
        return json.dumps({"body": "dumb"})


async def test_send_slack_message(respx_mock):
    if WEBHOOK_URL:
        respx_mock.post(WEBHOOK_URL).mock(return_value=httpx.Response(200))
        res = await send_slack_message(WEBHOOK_URL, [{"text": "Testing text"}])
        assert res.status_code == 200


async def test_exception_logger(mocker, respx_mock):
    if WEBHOOK_URL:
        respx_mock.post(WEBHOOK_URL).mock(return_value=httpx.Response(200))
        mocker.patch(
            "aiodal.web.auth.Auth0._decode_token",
            return_value={"sub": "aaa", "email": "run@run.com"},
        )

        dummy_url = DummyURL(path="/righteous_path/")
        dummy_request = DummyRequest(
            url=dummy_url, query_params="", headers={"Authorization": "Bearer 1"}
        )

        err = RuntimeError(str("born to run and stumble"))
        await slack_notifier.slack_notify(dummy_request, err, "testing")


# note we are not going to be able to capture log cause async :(
async def test_exception_logger_slack_webhook_failed(mocker, respx_mock):
    if WEBHOOK_URL:
        respx_mock.post(WEBHOOK_URL).mock(return_value=httpx.Response(400))
        mocker.patch(
            "aiodal.web.auth.Auth0._decode_token",
            return_value={"sub": "aaa", "email": "run@run.com"},
        )

        dummy_url = DummyURL(path="/righteous_path/")
        dummy_request = DummyRequest(
            url=dummy_url, query_params="", headers={"Authorization": "Bearer 1"}
        )

        err = RuntimeError(str("born to run and stumble"))
        await slack_notifier.slack_notify(dummy_request, err, "testing")


async def test_generate_slack_log_msg(mocker):
    mocker.patch(
        "aiodal.web.auth.Auth0._decode_token",
        return_value={"sub": "aaa", "email": "run@run.com"},
    )

    dummy_url = DummyURL(path="/righteous_path/")
    dummy_request = DummyRequest(
        url=dummy_url, query_params="", headers={"Authorization": "Bearer 1"}
    )

    await slack_notifier._generate_slack_log_msg(
        dummy_request, url=dummy_url.path, msg="dum dum", env="testing"
    )


async def test_generate_slack_log_msg_without_header(mocker):

    dummy_url = DummyURL(path="/righteous_path/")
    dummy_request = DummyRequest(url=dummy_url, query_params="")

    await slack_notifier._generate_slack_log_msg(
        dummy_request, url=dummy_url.path, msg="dum dum", env="testing"
    )


async def test_configure_request_url():
    dummy_url = DummyURL(path="/righteous_path/")
    dummy_request = DummyRequest(
        url=dummy_url, query_params="", headers={"Authorization": "Bearer 1"}
    )
    m = await slack_notifier._configure_request_url(dummy_request)
    b = json.dumps({"body": "dumb"})
    expected_msg = f"GET /righteous_path/" + "\n" + str(b)
    assert m == expected_msg


async def test_configure_exception_message(mocker):
    r = RuntimeError("born to run and stumble")
    mocker.patch(
        "sys.exc_info", return_value=(r, "born to run and stumble", "tracing back yah")
    )

    msg = slack_notifier._configure_exception_message(url="/righteous_path/", exc=r)
    assert "born to run and stumble" in msg
    assert "/righteous_path/" in msg


# async def test_slack_webhook(test_app, mocker, respx_mock):
#     if WEBHOOK_URL:
#         app = test_app

#         respx_mock.post(WEBHOOK_URL).mock(return_value=httpx.Response(200))
#         mocker.patch(
#             "aiodal.web.auth.Auth0._decode_token",
#             return_value={"sub": "aaa", "email": "run@run.com"},
#         )

#         blocks = [
#             {
#                 "type": "header",
#                 "text": {"type": "plain_text", "text": "forever webhook scaries"},
#             }
#         ]

#         async with httpx.AsyncClient(
#             transport=httpx.ASGITransport(app=app), base_url="https://fake.com"
#         ) as client:
#             path = app.url_path_for("forward_slack_logger")
#             res = await client.post(path, json={"blocks": blocks})
#             assert res.status_code == 204
