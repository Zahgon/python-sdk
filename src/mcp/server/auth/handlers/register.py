import secrets
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ValidationError
from starlette.requests import Request
from starlette.responses import Response

from mcp.server.auth.errors import stringify_pydantic_error
from mcp.server.auth.json_response import PydanticJSONResponse
from mcp.server.auth.provider import OAuthAuthorizationServerProvider, RegistrationError, RegistrationErrorCode
from mcp.server.auth.settings import ClientRegistrationOptions
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata

# this alias is a no-op; it's just to separate out the types exposed to the
# provider from what we use in the HTTP handler
RegistrationRequest = OAuthClientMetadata


class RegistrationErrorResponse(BaseModel):
    error: RegistrationErrorCode
    error_description: str | None


@dataclass
class RegistrationHandler:
    provider: OAuthAuthorizationServerProvider[Any, Any, Any]
    options: ClientRegistrationOptions

    async def handle(self, request: Request) -> Response:
        # Implements dynamic client registration as defined in https://datatracker.ietf.org/doc/html/rfc7591#section-3.1
        pass
