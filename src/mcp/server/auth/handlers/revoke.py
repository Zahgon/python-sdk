from dataclasses import dataclass
from functools import partial
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from starlette.requests import Request
from starlette.responses import Response

from mcp.server.auth.errors import (
    stringify_pydantic_error,
)
from mcp.server.auth.json_response import PydanticJSONResponse
from mcp.server.auth.middleware.client_auth import AuthenticationError, ClientAuthenticator
from mcp.server.auth.provider import AccessToken, OAuthAuthorizationServerProvider, RefreshToken


class RevocationRequest(BaseModel):
    """See https://datatracker.ietf.org/doc/html/rfc7009#section-2.1"""

    token: str
    token_type_hint: Literal["access_token", "refresh_token"] | None = None
    client_id: str
    client_secret: str | None


class RevocationErrorResponse(BaseModel):
    error: Literal["invalid_request", "unauthorized_client"]
    error_description: str | None = None


@dataclass
class RevocationHandler:
    provider: OAuthAuthorizationServerProvider[Any, Any, Any]
    client_authenticator: ClientAuthenticator

    async def handle(self, request: Request) -> Response:
        """Handler for the OAuth 2.0 Token Revocation endpoint."""
        pass
