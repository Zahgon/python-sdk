import base64
import hashlib
import time
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import AnyHttpUrl, AnyUrl, BaseModel, Field, TypeAdapter, ValidationError
from starlette.requests import Request

from mcp.server.auth.errors import stringify_pydantic_error
from mcp.server.auth.json_response import PydanticJSONResponse
from mcp.server.auth.middleware.client_auth import AuthenticationError, ClientAuthenticator
from mcp.server.auth.provider import OAuthAuthorizationServerProvider, TokenError, TokenErrorCode
from mcp.shared.auth import OAuthToken


class AuthorizationCodeRequest(BaseModel):
    # See https://datatracker.ietf.org/doc/html/rfc6749#section-4.1.3
    grant_type: Literal["authorization_code"]
    code: str = Field(..., description="The authorization code")
    redirect_uri: AnyUrl | None = Field(None, description="Must be the same as redirect URI provided in /authorize")
    client_id: str
    # we use the client_secret param, per https://datatracker.ietf.org/doc/html/rfc6749#section-2.3.1
    client_secret: str | None = None
    # See https://datatracker.ietf.org/doc/html/rfc7636#section-4.5
    code_verifier: str = Field(..., description="PKCE code verifier")
    # RFC 8707 resource indicator
    resource: str | None = Field(None, description="Resource indicator for the token")


class RefreshTokenRequest(BaseModel):
    # See https://datatracker.ietf.org/doc/html/rfc6749#section-6
    grant_type: Literal["refresh_token"]
    refresh_token: str = Field(..., description="The refresh token")
    scope: str | None = Field(None, description="Optional scope parameter")
    client_id: str
    # we use the client_secret param, per https://datatracker.ietf.org/doc/html/rfc6749#section-2.3.1
    client_secret: str | None = None
    # RFC 8707 resource indicator
    resource: str | None = Field(None, description="Resource indicator for the token")


TokenRequest = Annotated[AuthorizationCodeRequest | RefreshTokenRequest, Field(discriminator="grant_type")]
token_request_adapter = TypeAdapter[TokenRequest](TokenRequest)


class TokenErrorResponse(BaseModel):
    """See https://datatracker.ietf.org/doc/html/rfc6749#section-5.2"""

    error: TokenErrorCode
    error_description: str | None = None
    error_uri: AnyHttpUrl | None = None


# this is just an alias over OAuthToken; the only reason we do this
# is to have some separation between the HTTP response type, and the
# type returned by the provider
TokenSuccessResponse = OAuthToken


@dataclass
class TokenHandler:
    provider: OAuthAuthorizationServerProvider[Any, Any, Any]
    client_authenticator: ClientAuthenticator

    def response(self, obj: TokenSuccessResponse | TokenErrorResponse):
        pass

    async def handle(self, request: Request):
        pass
