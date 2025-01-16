from fastapi import Request
import pydantic
import httpx
import json
import logging
import sys
import traceback
from typing import Any, Dict, List, Sequence


from . import auth

# router = APIRouter(prefix="/slack")

logger = logging.getLogger("uvicorn")
logger.setLevel(logging.getLevelName(logging.INFO))


async def send_slack_message(
    slack_url: str,
    blocks: Sequence[Dict[str, Any]] | None,
) -> httpx.Response:
    """Sends the outbout request to the slack API using httpx

    Args:
        slack_url (str): _description_
        blocks (Sequence[Dict[str, Any]] | None): _description_

    Returns:
        httpx.Response: _description_
    """
    headers = {"Content-Type": "application/json;charset=utf-8"}
    body = {"blocks": blocks}
    async with httpx.AsyncClient() as client:
        res = await client.post(slack_url, json=body, headers=headers)
    return res


class SlackNotifier:
    auth0_model: auth.Auth0
    webhook_url: str | None = None
    # environment: str | None = None

    def __init__(self, auth0_model: auth.Auth0, webhook_url: str):
        self.auth0_model = auth0_model
        self.webhook_url = webhook_url
        # self.environment = environment

    async def slack_notify(
        self, req: Request, exc: Exception, environment: str
    ) -> None:
        # i dont think we need env in if stmt here
        if self.webhook_url:
            url = await self._configure_request_url(req)
            msg = self._configure_exception_message(url, exc)
            payload = await self._generate_slack_log_msg(req, url, msg, environment)
            await self._slack_webhook_handler(
                self.webhook_url, environment, payload=payload
            )
        return None

    async def _generate_slack_log_msg(
        self,
        req: Request,
        url: str,
        msg: str,
        env: str,
    ) -> List[Any]:
        """Construct the log message for slack webhook. Note that the
        token must be decoded and a user object created since we do not
        have direct access to that in the exception handler interface.

        Args:
            req (Request): _description_
            url (str): _description_
            msg (str): _description_
            env (str): _description_

        Returns:
            str: _description_
        """
        # NOTE we should not need error handling here since if we had a malformed token
        # it would have thrown already.

        try:
            token = req.headers["Authorization"].split("Bearer ")[-1]
            user_payload = self.auth0_model._decode_token(token)
            email = user_payload["email"]
            # user = HiveAuth0User(**payload)
            # email = user.email
        except KeyError:
            email = "Unauthenticated User."

        # construct request info
        body = await req.body()
        payload: Dict[str, Any] = {
            "method": req.method,
            "url": url,
            "exception": msg,
            "body": json.loads(body) if body else "",
            "params": str(req.query_params),
            "traceback": traceback.format_exc(),
        }
        # construct blocks for slack logging
        blocks: List[Dict[str, Any]] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Log", "emoji": True},
            },
            {
                "type": "context",
                "elements": [
                    {"type": "plain_text", "text": f"{email}", "emoji": True},
                    {"type": "plain_text", "text": env, "emoji": True},
                    {"type": "plain_text", "text": "@tinnaing347", "emoji": True},
                ],
            },
            {"type": "divider"},
            {
                "type": "rich_text",
                "elements": [
                    {
                        "type": "rich_text_preformatted",
                        "elements": [
                            {
                                "type": "text",
                                "text": json.dumps(payload, indent=2).replace(
                                    "\\n", "\n"
                                ),
                            },
                        ],
                    },
                ],
            },
        ]

        return blocks

    async def _slack_webhook_handler(
        self, webhook_url: str, env: str, payload: List[Any]
    ) -> httpx.Response | None:
        """Handle the call to the slack webhook using their sdk.
        If the call fails report the status code and response body.

        Args:
            webhook_url (str): _description_
            env (str): _description_
        """
        if webhook_url and env:
            response = await send_slack_message(webhook_url, blocks=payload)
            if response.status_code != 200:
                logger.error(
                    f"Slack webhook call failed with status code {response.status_code}\n {response.text}"
                )
            return response
        return None

    async def _configure_request_url(self, req: Request) -> str:
        url = f"{req.url.path}?{req.query_params}" if req.query_params else req.url.path
        body = await req.body()
        return f"{req.method} " + url + "\n" + str(body)

    def _configure_exception_message(self, url: str, exc: Exception) -> str:
        exception_type, exception_value, exception_traceback = sys.exc_info()
        exception_name = getattr(exception_type, "__name__", None)

        return (
            f'"{url}"\n<{exception_name}: {exception_value}> \n {exception_traceback}'
        )


# async def slack_notify(req: Request, exc: Exception, config: SlackConfig) -> None:
#     """Fire the slack notify if we had an error. This is called in main from a starlette middleware
#     wrapper. It should intercept any unhandled server side exceptions.

#     Args:
#         req (Request): _description_
#         exc (Exception): _description_
#     """
#     if config.webhook_url and config.environment:
#         url = await _configure_request_url(req)
#         msg = _configure_exception_message(url, exc)
#         payload = await _generate_slack_log_msg(req, url, msg, config.environment)
#         await _slack_webhook_handler(config.webhook_url, config.environment, payload=payload)

#     return None


# NOTE this is only used in the forward logger calls from the frontend ..
# it is treated as a private endpoint and does require authorization...
class SlackLogger(pydantic.BaseModel):
    blocks: list[Any]
