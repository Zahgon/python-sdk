import base64
import binascii
import hmac
import time
from typing import Any
from urllib.parse import unquote

from starlette.requests import Request

from mcp.server.auth.provider import OAuthAuthorizationServerProvider
from mcp.shared.auth import OAuthClientInformationFull


class AuthenticationError(Exception):
    def __init__(self, message: str):
        self.message = message


class ClientAuthenticator:
    """ClientAuthenticator is a callable which validates requests from a client
    application, used to verify /token calls.

    If, during registration, the client requested to be issued a secret, the
    authenticator asserts that /token calls must be authenticated with
    that same secret.

    NOTE: clients can opt for no authentication during registration, in which case this
    logic is skipped.
    """

    def __init__(self, provider: OAuthAuthorizationServerProvider[Any, Any, Any]):
        """Initialize the authenticator.

        Args:
            provider: Provider to look up client information
        """
        self.provider = provider

    async def authenticate_request(self, request: Request) -> OAuthClientInformationFull:
        """Authenticate a client from an HTTP request.

        Extracts client credentials from the appropriate location based on the
        client's registered authentication method and validates them.

        Args:
            request: The HTTP request containing client credentials

        Returns:
            The authenticated client information

        Raises:
            AuthenticationError: If authentication fails
        """
        pass
