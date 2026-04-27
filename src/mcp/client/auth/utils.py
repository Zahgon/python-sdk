import re
from urllib.parse import urljoin, urlparse

from httpx import Request, Response
from pydantic import AnyUrl, ValidationError

from mcp.client.auth import OAuthRegistrationError, OAuthTokenError
from mcp.client.streamable_http import MCP_PROTOCOL_VERSION
from mcp.shared.auth import (
    OAuthClientInformationFull,
    OAuthClientMetadata,
    OAuthMetadata,
    OAuthToken,
    ProtectedResourceMetadata,
)
from mcp.types import LATEST_PROTOCOL_VERSION


def extract_field_from_www_auth(response: Response, field_name: str) -> str | None:
    """Extract field from WWW-Authenticate header.

    Returns:
        Field value if found in WWW-Authenticate header, None otherwise
    """
    pass


def extract_scope_from_www_auth(response: Response) -> str | None:
    """Extract scope parameter from WWW-Authenticate header as per RFC 6750.

    Returns:
        Scope string if found in WWW-Authenticate header, None otherwise
    """
    pass


def extract_resource_metadata_from_www_auth(response: Response) -> str | None:
    """Extract protected resource metadata URL from WWW-Authenticate header as per RFC 9728.

    Returns:
        Resource metadata URL if found in WWW-Authenticate header, None otherwise
    """
    pass


def build_protected_resource_metadata_discovery_urls(www_auth_url: str | None, server_url: str) -> list[str]:
    """Build ordered list of URLs to try for protected resource metadata discovery.

    Per SEP-985, the client MUST:
    1. Try resource_metadata from WWW-Authenticate header (if present)
    2. Fall back to path-based well-known URI: /.well-known/oauth-protected-resource/{path}
    3. Fall back to root-based well-known URI: /.well-known/oauth-protected-resource

    Args:
        www_auth_url: Optional resource_metadata URL extracted from the WWW-Authenticate header
        server_url: Server URL

    Returns:
        Ordered list of URLs to try for discovery
    """
    pass


def get_client_metadata_scopes(
    www_authenticate_scope: str | None,
    protected_resource_metadata: ProtectedResourceMetadata | None,
    authorization_server_metadata: OAuthMetadata | None = None,
    client_grant_types: list[str] | None = None,
) -> str | None:
    """Select effective scopes and augment for refresh token support."""
    pass


def build_oauth_authorization_server_metadata_discovery_urls(auth_server_url: str | None, server_url: str) -> list[str]:
    """Generate an ordered list of URLs for authorization server metadata discovery.

    Args:
        auth_server_url: OAuth Authorization Server Metadata URL if found, otherwise None
        server_url: URL for the MCP server, used as a fallback if auth_server_url is None
    """
    pass


async def handle_protected_resource_response(
    response: Response,
) -> ProtectedResourceMetadata | None:
    """Handle protected resource metadata discovery response.

    Per SEP-985, supports fallback when discovery fails at one URL.

    Returns:
        ProtectedResourceMetadata if successfully discovered, None if we should try next URL
    """
    pass


async def handle_auth_metadata_response(response: Response) -> tuple[bool, OAuthMetadata | None]:
    pass


def create_oauth_metadata_request(url: str) -> Request:
    pass


def create_client_registration_request(
    auth_server_metadata: OAuthMetadata | None, client_metadata: OAuthClientMetadata, auth_base_url: str
) -> Request:
    """Build a client registration request."""
    pass


async def handle_registration_response(response: Response) -> OAuthClientInformationFull:
    """Handle registration response."""
    pass


def is_valid_client_metadata_url(url: str | None) -> bool:
    """Validate that a URL is suitable for use as a client_id (CIMD).

    The URL must be HTTPS with a non-root pathname.

    Args:
        url: The URL to validate

    Returns:
        True if the URL is a valid HTTPS URL with a non-root pathname
    """
    pass


def should_use_client_metadata_url(
    oauth_metadata: OAuthMetadata | None,
    client_metadata_url: str | None,
) -> bool:
    """Determine if URL-based client ID (CIMD) should be used instead of DCR.

    URL-based client IDs should be used when:
    1. The server advertises client_id_metadata_document_supported=True
    2. The client has a valid client_metadata_url configured

    Args:
        oauth_metadata: OAuth authorization server metadata
        client_metadata_url: URL-based client ID (already validated)

    Returns:
        True if CIMD should be used, False if DCR should be used
    """
    pass


def create_client_info_from_metadata_url(
    client_metadata_url: str, redirect_uris: list[AnyUrl] | None = None
) -> OAuthClientInformationFull:
    """Create client information using a URL-based client ID (CIMD).

    When using URL-based client IDs, the URL itself becomes the client_id
    and no client_secret is used (token_endpoint_auth_method="none").

    Args:
        client_metadata_url: The URL to use as the client_id
        redirect_uris: The redirect URIs from the client metadata (passed through for
            compatibility with OAuthClientInformationFull which inherits from OAuthClientMetadata)

    Returns:
        OAuthClientInformationFull with the URL as client_id
    """
    pass


async def handle_token_response_scopes(
    response: Response,
) -> OAuthToken:
    """Parse and validate a token response.

    Parses token response JSON. Callers should check response.status_code before calling.

    Args:
        response: HTTP response from token endpoint (status already checked by caller)

    Returns:
        Validated OAuthToken model

    Raises:
        OAuthTokenError: If response JSON is invalid
    """
    pass
