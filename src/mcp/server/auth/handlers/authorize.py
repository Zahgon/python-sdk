import logging
from dataclasses import dataclass
from typing import Any, Literal

# TODO(Marcelo): We should drop the `RootModel`.
from pydantic import AnyUrl, BaseModel, Field, RootModel, ValidationError  # noqa: TID251
from starlette.datastructures import FormData, QueryParams
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from mcp.server.auth.errors import stringify_pydantic_error
from mcp.server.auth.json_response import PydanticJSONResponse
from mcp.server.auth.provider import (
    AuthorizationErrorCode,
    AuthorizationParams,
    AuthorizeError,
    OAuthAuthorizationServerProvider,
    construct_redirect_uri,
)
from mcp.shared.auth import InvalidRedirectUriError, InvalidScopeError

logger = logging.getLogger(__name__)


class AuthorizationRequest(BaseModel):
    # See https://datatracker.ietf.org/doc/html/rfc6749#section-4.1.1
    client_id: str = Field(..., description="The client ID")
    redirect_uri: AnyUrl | None = Field(None, description="URL to redirect to after authorization")

    # see OAuthClientMetadata; we only support `code`
    response_type: Literal["code"] = Field(..., description="Must be 'code' for authorization code flow")
    code_challenge: str = Field(..., description="PKCE code challenge")
    code_challenge_method: Literal["S256"] = Field("S256", description="PKCE code challenge method, must be S256")
    state: str | None = Field(None, description="Optional state parameter")
    scope: str | None = Field(
        None,
        description="Optional scope; if specified, should be a space-separated list of scope strings",
    )
    resource: str | None = Field(
        None,
        description="RFC 8707 resource indicator - the MCP server this token will be used with",
    )


class AuthorizationErrorResponse(BaseModel):
    error: AuthorizationErrorCode
    error_description: str | None
    error_uri: AnyUrl | None = None
    # must be set if provided in the request
    state: str | None = None


def best_effort_extract_string(key: str, params: None | FormData | QueryParams) -> str | None:
    if params is None:  # pragma: no cover
        return None
    value = params.get(key)
    if isinstance(value, str):
        return value
    return None


class AnyUrlModel(RootModel[AnyUrl]):
    root: AnyUrl


@dataclass
class AuthorizationHandler:
    provider: OAuthAuthorizationServerProvider[Any, Any, Any]

    async def handle(self, request: Request) -> Response:
        # implements authorization requests for grant_type=code;
        # see https://datatracker.ietf.org/doc/html/rfc6749#section-4.1.1

        pass
