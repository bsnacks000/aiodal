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
    authentication: auth.Auth0 | None = None
    webhook_url: str | None = None
    environment: List[str] | None = None

    def __init__(
        self,
        webhook_url: str,
        authentication: auth.Auth0 | None = None,
        environments_trigger: List[str] | None = None,
    ):
        self.webhook_url = webhook_url
        self.authentication = authentication
        self.environments_trigger = environments_trigger

    async def slack_notify(
        self, req: Request, exc: Exception, environment: str
    ) -> None:
        """public method to send notification of errors/messages into slack channel.

        Args:
            req (Request): request object
            exc (Exception): exception raised that needs to be notified in slack
            environment (str): an optional enviroment str. `environments_trigger` must be set in the class to use this.
                                if the provided `environment` is not present in `environments_trigger`, messaages will not be sent to slack.

        Returns:
            _type_: _description_
        """
        if self.webhook_url and self._trigger_on_environment(environment):
            url = await self._configure_request_url(req)
            msg = self._configure_exception_message(url, exc)
            payload = await self._generate_slack_log_msg(req, url, msg, environment)
            await self._slack_webhook_handler(
                self.webhook_url, environment, payload=payload
            )
        return None

    def _trigger_on_environment(self, environment: str) -> bool:
        if not self.environments_trigger:
            return True
        return environment in self.environments_trigger

    def _get_user_email(self, req: Request) -> str:
        """get or parse user eamil from request if authorization is present in headers and authentication is provided in class constructor

        Args:
            req (Request): _description_
        """
        email: str
        #  if auth is provided and there is Authorization in request headers, parse user info
        # NOTE we should not need error handling here since if we had a malformed token
        # it would have thrown already.
        if self.authentication and "Authorization" in req.headers:
            token = req.headers["Authorization"].split("Bearer ")[-1]
            user_payload = self.authentication._decode_token(token)
            email = (
                user_payload["email"]
                if "email" in user_payload.keys()
                else "Authenticated User (no email)"
            )
        else:
            email = "Unauthenticated User"
        return email

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

        email = self._get_user_email(req)

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


# NOTE this is only used in the forward logger calls from the frontend ..
# it is treated as a private endpoint and does require authorization...
class SlackLogger(pydantic.BaseModel):
    blocks: list[Any]
