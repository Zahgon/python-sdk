"""OAuth2 Authentication implementation for HTTPX.

Implements authorization code flow with PKCE and automatic token refresh.
"""

import base64
import hashlib
import logging
import secrets
import string
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import quote, urlencode, urljoin, urlparse

import anyio
import httpx
from pydantic import BaseModel, Field, ValidationError

from mcp.client.auth.exceptions import OAuthFlowError, OAuthTokenError
from mcp.client.auth.utils import (
    build_oauth_authorization_server_metadata_discovery_urls,
    build_protected_resource_metadata_discovery_urls,
    create_client_info_from_metadata_url,
    create_client_registration_request,
    create_oauth_metadata_request,
    extract_field_from_www_auth,
    extract_resource_metadata_from_www_auth,
    extract_scope_from_www_auth,
    get_client_metadata_scopes,
    handle_auth_metadata_response,
    handle_protected_resource_response,
    handle_registration_response,
    handle_token_response_scopes,
    is_valid_client_metadata_url,
    should_use_client_metadata_url,
)
from mcp.client.streamable_http import MCP_PROTOCOL_VERSION
from mcp.shared.auth import (
    OAuthClientInformationFull,
    OAuthClientMetadata,
    OAuthMetadata,
    OAuthToken,
    ProtectedResourceMetadata,
)
from mcp.shared.auth_utils import (
    calculate_token_expiry,
    check_resource_allowed,
    resource_url_from_server_url,
)

logger = logging.getLogger(__name__)


class PKCEParameters(BaseModel):
    """PKCE (Proof Key for Code Exchange) parameters."""

    code_verifier: str = Field(..., min_length=43, max_length=128)
    code_challenge: str = Field(..., min_length=43, max_length=128)

    @classmethod
    def generate(cls) -> "PKCEParameters":
        """Generate new PKCE parameters."""
        pass


class TokenStorage(Protocol):
    """Protocol for token storage implementations."""

    async def get_tokens(self) -> OAuthToken | None:
        """Get stored tokens."""
        ...

    async def set_tokens(self, tokens: OAuthToken) -> None:
        """Store tokens."""
        ...

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        """Get stored client information."""
        ...

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        """Store client information."""
        ...


@dataclass
class OAuthContext:
    """OAuth flow context."""

    server_url: str
    client_metadata: OAuthClientMetadata
    storage: TokenStorage
    redirect_handler: Callable[[str], Awaitable[None]] | None
    callback_handler: Callable[[], Awaitable[tuple[str, str | None]]] | None
    timeout: float = 300.0
    client_metadata_url: str | None = None

    # Discovered metadata
    protected_resource_metadata: ProtectedResourceMetadata | None = None
    oauth_metadata: OAuthMetadata | None = None
    auth_server_url: str | None = None
    protocol_version: str | None = None

    # Client registration
    client_info: OAuthClientInformationFull | None = None

    # Token management
    current_tokens: OAuthToken | None = None
    token_expiry_time: float | None = None

    # State
    lock: anyio.Lock = field(default_factory=anyio.Lock)

    def get_authorization_base_url(self, server_url: str) -> str:
        """Extract base URL by removing path component."""
        pass

    def update_token_expiry(self, token: OAuthToken) -> None:
        """Update token expiry time using shared util function."""
        pass

    def is_token_valid(self) -> bool:
        """Check if current token is valid."""
        pass

    def can_refresh_token(self) -> bool:
        """Check if token can be refreshed."""
        pass

    def clear_tokens(self) -> None:
        """Clear current tokens."""
        pass

    def get_resource_url(self) -> str:
        """Get resource URL for RFC 8707.

        Uses PRM resource if it's a valid parent, otherwise uses canonical server URL.
        """
        pass

    def should_include_resource_param(self, protocol_version: str | None = None) -> bool:
        """Determine if the resource parameter should be included in OAuth requests.

        Returns True if:
        - Protected resource metadata is available, OR
        - MCP-Protocol-Version header is 2025-06-18 or later
        """
        pass

    def prepare_token_auth(
        self, data: dict[str, str], headers: dict[str, str] | None = None
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Prepare authentication for token requests.

        Args:
            data: The form data to send
            headers: Optional headers dict to update

        Returns:
            Tuple of (updated_data, updated_headers)
        """
        pass


class OAuthClientProvider(httpx.Auth):
    """OAuth2 authentication for httpx.

    Handles OAuth flow with automatic client registration and token storage.
    """

    requires_response_body = True

    def __init__(
        self,
        server_url: str,
        client_metadata: OAuthClientMetadata,
        storage: TokenStorage,
        redirect_handler: Callable[[str], Awaitable[None]] | None = None,
        callback_handler: Callable[[], Awaitable[tuple[str, str | None]]] | None = None,
        timeout: float = 300.0,
        client_metadata_url: str | None = None,
        validate_resource_url: Callable[[str, str | None], Awaitable[None]] | None = None,
    ):
        """Initialize OAuth2 authentication.

        Args:
            server_url: The MCP server URL.
            client_metadata: OAuth client metadata for registration.
            storage: Token storage implementation.
            redirect_handler: Handler for authorization redirects.
            callback_handler: Handler for authorization callbacks.
            timeout: Timeout for the OAuth flow.
            client_metadata_url: URL-based client ID. When provided and the server
                advertises client_id_metadata_document_supported=True, this URL will be
                used as the client_id instead of performing dynamic client registration.
                Must be a valid HTTPS URL with a non-root pathname.
            validate_resource_url: Optional callback to override resource URL validation.
                Called with (server_url, prm_resource) where prm_resource is the resource
                from Protected Resource Metadata (or None if not present). If not provided,
                default validation rejects mismatched resources per RFC 8707.

        Raises:
            ValueError: If client_metadata_url is provided but not a valid HTTPS URL
                with a non-root pathname.
        """
        # Validate client_metadata_url if provided
        if client_metadata_url is not None and not is_valid_client_metadata_url(client_metadata_url):
            raise ValueError(
                f"client_metadata_url must be a valid HTTPS URL with a non-root pathname, got: {client_metadata_url}"
            )

        self.context = OAuthContext(
            server_url=server_url,
            client_metadata=client_metadata,
            storage=storage,
            redirect_handler=redirect_handler,
            callback_handler=callback_handler,
            timeout=timeout,
            client_metadata_url=client_metadata_url,
        )
        self._validate_resource_url_callback = validate_resource_url
        self._initialized = False

    async def _handle_protected_resource_response(self, response: httpx.Response) -> bool:
        """Handle protected resource metadata discovery response.

        Per SEP-985, supports fallback when discovery fails at one URL.

        Returns:
            True if metadata was successfully discovered, False if we should try next URL
        """
        pass

    async def _perform_authorization(self) -> httpx.Request:
        """Perform the authorization flow."""
        pass

    async def _perform_authorization_code_grant(self) -> tuple[str, str]:
        """Perform the authorization redirect and get auth code."""
        pass

    def _get_token_endpoint(self) -> str:
        pass

    async def _exchange_token_authorization_code(
        self, auth_code: str, code_verifier: str, *, token_data: dict[str, Any] | None = {}
    ) -> httpx.Request:
        """Build token exchange request for authorization_code flow."""
        pass

    async def _handle_token_response(self, response: httpx.Response) -> None:
        """Handle token exchange response."""
        pass

    async def _refresh_token(self) -> httpx.Request:
        """Build token refresh request."""
        pass

    async def _handle_refresh_response(self, response: httpx.Response) -> bool:  # pragma: no cover
        """Handle token refresh response. Returns True if successful."""
        pass

    async def _initialize(self) -> None:  # pragma: no cover
        """Load stored tokens and client info."""
        pass

    def _add_auth_header(self, request: httpx.Request) -> None:
        """Add authorization header to request if we have valid tokens."""
        pass

    async def _handle_oauth_metadata_response(self, response: httpx.Response) -> None:
        pass

    async def _validate_resource_match(self, prm: ProtectedResourceMetadata) -> None:
        """Validate that PRM resource matches the server URL per RFC 8707."""
        pass

    async def async_auth_flow(self, request: httpx.Request) -> AsyncGenerator[httpx.Request, httpx.Response]:
        """HTTPX auth flow integration."""
        pass
