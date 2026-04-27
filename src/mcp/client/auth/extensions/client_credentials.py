"""OAuth client credential extensions for MCP.

Provides OAuth providers for machine-to-machine authentication flows:
- ClientCredentialsOAuthProvider: For client_credentials with client_id + client_secret
- PrivateKeyJWTOAuthProvider: For client_credentials with private_key_jwt authentication
  (typically using a pre-built JWT from workload identity federation)
- RFC7523OAuthClientProvider: For jwt-bearer grant (RFC 7523 Section 2.1)
"""

import time
import warnings
from collections.abc import Awaitable, Callable
from typing import Any, Literal
from uuid import uuid4

import httpx
import jwt
from pydantic import BaseModel, Field

from mcp.client.auth import OAuthClientProvider, OAuthFlowError, OAuthTokenError, TokenStorage
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata


class ClientCredentialsOAuthProvider(OAuthClientProvider):
    """OAuth provider for client_credentials grant with client_id + client_secret.

    This provider sets client_info directly, bypassing dynamic client registration.
    Use this when you already have client credentials (client_id and client_secret).

    Example:
        ```python
        provider = ClientCredentialsOAuthProvider(
            server_url="https://api.example.com",
            storage=my_token_storage,
            client_id="my-client-id",
            client_secret="my-client-secret",
        )
        ```
    """

    def __init__(
        self,
        server_url: str,
        storage: TokenStorage,
        client_id: str,
        client_secret: str,
        token_endpoint_auth_method: Literal["client_secret_basic", "client_secret_post"] = "client_secret_basic",
        scopes: str | None = None,
    ) -> None:
        """Initialize client_credentials OAuth provider.

        Args:
            server_url: The MCP server URL.
            storage: Token storage implementation.
            client_id: The OAuth client ID.
            client_secret: The OAuth client secret.
            token_endpoint_auth_method: Authentication method for token endpoint.
                Either "client_secret_basic" (default) or "client_secret_post".
            scopes: Optional space-separated list of scopes to request.
        """
        # Build minimal client_metadata for the base class
        client_metadata = OAuthClientMetadata(
            redirect_uris=None,
            grant_types=["client_credentials"],
            token_endpoint_auth_method=token_endpoint_auth_method,
            scope=scopes,
        )
        super().__init__(server_url, client_metadata, storage, None, None, 300.0)
        # Store client_info to be set during _initialize - no dynamic registration needed
        self._fixed_client_info = OAuthClientInformationFull(
            redirect_uris=None,
            client_id=client_id,
            client_secret=client_secret,
            grant_types=["client_credentials"],
            token_endpoint_auth_method=token_endpoint_auth_method,
            scope=scopes,
        )

    async def _initialize(self) -> None:
        """Load stored tokens and set pre-configured client_info."""
        pass

    async def _perform_authorization(self) -> httpx.Request:
        """Perform client_credentials authorization."""
        pass

    async def _exchange_token_client_credentials(self) -> httpx.Request:
        """Build token exchange request for client_credentials grant."""
        pass


def static_assertion_provider(token: str) -> Callable[[str], Awaitable[str]]:
    """Create an assertion provider that returns a static JWT token.

    Use this when you have a pre-built JWT (e.g., from workload identity federation)
    that doesn't need the audience parameter.

    Example:
        ```python
        provider = PrivateKeyJWTOAuthProvider(
            server_url="https://api.example.com",
            storage=my_token_storage,
            client_id="my-client-id",
            assertion_provider=static_assertion_provider(my_prebuilt_jwt),
        )
        ```

    Args:
        token: The pre-built JWT assertion string.

    Returns:
        An async callback suitable for use as an assertion_provider.
    """
    pass


class SignedJWTParameters(BaseModel):
    """Parameters for creating SDK-signed JWT assertions.

    Use `create_assertion_provider()` to create an assertion provider callback
    for use with `PrivateKeyJWTOAuthProvider`.

    Example:
        ```python
        jwt_params = SignedJWTParameters(
            issuer="my-client-id",
            subject="my-client-id",
            signing_key=private_key_pem,
        )
        provider = PrivateKeyJWTOAuthProvider(
            server_url="https://api.example.com",
            storage=my_token_storage,
            client_id="my-client-id",
            assertion_provider=jwt_params.create_assertion_provider(),
        )
        ```
    """

    issuer: str = Field(description="Issuer for JWT assertions (typically client_id).")
    subject: str = Field(description="Subject identifier for JWT assertions (typically client_id).")
    signing_key: str = Field(description="Private key for JWT signing (PEM format).")
    signing_algorithm: str = Field(default="RS256", description="Algorithm for signing JWT assertions.")
    lifetime_seconds: int = Field(default=300, description="Lifetime of generated JWT in seconds.")
    additional_claims: dict[str, Any] | None = Field(default=None, description="Additional claims.")

    def create_assertion_provider(self) -> Callable[[str], Awaitable[str]]:
        """Create an assertion provider callback for use with PrivateKeyJWTOAuthProvider.

        Returns:
            An async callback that takes the audience (authorization server issuer URL)
            and returns a signed JWT assertion.
        """
        pass


class PrivateKeyJWTOAuthProvider(OAuthClientProvider):
    """OAuth provider for client_credentials grant with private_key_jwt authentication.

    Uses RFC 7523 Section 2.2 for client authentication via JWT assertion.

    The JWT assertion's audience MUST be the authorization server's issuer identifier
    (per RFC 7523bis security updates). The `assertion_provider` callback receives
    this audience value and must return a JWT with that audience.

    **Option 1: Pre-built JWT via Workload Identity Federation**

    In production scenarios, the JWT assertion is typically obtained from a workload
    identity provider (e.g., GCP, AWS IAM, Azure AD):

        ```python
        async def get_workload_identity_token(audience: str) -> str:
            # Fetch JWT from your identity provider
            # The JWT's audience must match the provided audience parameter
            return await fetch_token_from_identity_provider(audience=audience)

        provider = PrivateKeyJWTOAuthProvider(
            server_url="https://api.example.com",
            storage=my_token_storage,
            client_id="my-client-id",
            assertion_provider=get_workload_identity_token,
        )
        ```

    **Option 2: Static pre-built JWT**

    If you have a static JWT that doesn't need the audience parameter:

        ```python
        provider = PrivateKeyJWTOAuthProvider(
            server_url="https://api.example.com",
            storage=my_token_storage,
            client_id="my-client-id",
            assertion_provider=static_assertion_provider(my_prebuilt_jwt),
        )
        ```

    **Option 3: SDK-signed JWT (for testing/simple setups)**

    For testing or simple deployments, use `SignedJWTParameters.create_assertion_provider()`:

        ```python
        jwt_params = SignedJWTParameters(
            issuer="my-client-id",
            subject="my-client-id",
            signing_key=private_key_pem,
        )
        provider = PrivateKeyJWTOAuthProvider(
            server_url="https://api.example.com",
            storage=my_token_storage,
            client_id="my-client-id",
            assertion_provider=jwt_params.create_assertion_provider(),
        )
        ```
    """

    def __init__(
        self,
        server_url: str,
        storage: TokenStorage,
        client_id: str,
        assertion_provider: Callable[[str], Awaitable[str]],
        scopes: str | None = None,
    ) -> None:
        """Initialize private_key_jwt OAuth provider.

        Args:
            server_url: The MCP server URL.
            storage: Token storage implementation.
            client_id: The OAuth client ID.
            assertion_provider: Async callback that takes the audience (authorization
                server's issuer identifier) and returns a JWT assertion. Use
                `SignedJWTParameters.create_assertion_provider()` for SDK-signed JWTs,
                `static_assertion_provider()` for pre-built JWTs, or provide your own
                callback for workload identity federation.
            scopes: Optional space-separated list of scopes to request.
        """
        # Build minimal client_metadata for the base class
        client_metadata = OAuthClientMetadata(
            redirect_uris=None,
            grant_types=["client_credentials"],
            token_endpoint_auth_method="private_key_jwt",
            scope=scopes,
        )
        super().__init__(server_url, client_metadata, storage, None, None, 300.0)
        self._assertion_provider = assertion_provider
        # Store client_info to be set during _initialize - no dynamic registration needed
        self._fixed_client_info = OAuthClientInformationFull(
            redirect_uris=None,
            client_id=client_id,
            grant_types=["client_credentials"],
            token_endpoint_auth_method="private_key_jwt",
            scope=scopes,
        )

    async def _initialize(self) -> None:
        """Load stored tokens and set pre-configured client_info."""
        pass

    async def _perform_authorization(self) -> httpx.Request:
        """Perform client_credentials authorization with private_key_jwt."""
        pass

    async def _add_client_authentication_jwt(self, *, token_data: dict[str, Any]) -> None:
        """Add JWT assertion for client authentication to token endpoint parameters."""
        pass

    async def _exchange_token_client_credentials(self) -> httpx.Request:
        """Build token exchange request for client_credentials grant with private_key_jwt."""
        pass


class JWTParameters(BaseModel):
    """JWT parameters."""

    assertion: str | None = Field(
        default=None,
        description="JWT assertion for JWT authentication. "
        "Will be used instead of generating a new assertion if provided.",
    )

    issuer: str | None = Field(default=None, description="Issuer for JWT assertions.")
    subject: str | None = Field(default=None, description="Subject identifier for JWT assertions.")
    audience: str | None = Field(default=None, description="Audience for JWT assertions.")
    claims: dict[str, Any] | None = Field(default=None, description="Additional claims for JWT assertions.")
    jwt_signing_algorithm: str | None = Field(default="RS256", description="Algorithm for signing JWT assertions.")
    jwt_signing_key: str | None = Field(default=None, description="Private key for JWT signing.")
    jwt_lifetime_seconds: int = Field(default=300, description="Lifetime of generated JWT in seconds.")

    def to_assertion(self, with_audience_fallback: str | None = None) -> str:
        pass


class RFC7523OAuthClientProvider(OAuthClientProvider):
    """OAuth client provider for RFC 7523 jwt-bearer grant.

    .. deprecated::
        Use :class:`ClientCredentialsOAuthProvider` for client_credentials with
        client_id + client_secret, or :class:`PrivateKeyJWTOAuthProvider` for
        client_credentials with private_key_jwt authentication instead.

    This provider supports the jwt-bearer authorization grant (RFC 7523 Section 2.1)
    where the JWT itself is the authorization grant.
    """

    def __init__(
        self,
        server_url: str,
        client_metadata: OAuthClientMetadata,
        storage: TokenStorage,
        redirect_handler: Callable[[str], Awaitable[None]] | None = None,
        callback_handler: Callable[[], Awaitable[tuple[str, str | None]]] | None = None,
        timeout: float = 300.0,
        jwt_parameters: JWTParameters | None = None,
    ) -> None:
        warnings.warn(
            "RFC7523OAuthClientProvider is deprecated. Use ClientCredentialsOAuthProvider "
            "or PrivateKeyJWTOAuthProvider instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(server_url, client_metadata, storage, redirect_handler, callback_handler, timeout)
        self.jwt_parameters = jwt_parameters

    async def _exchange_token_authorization_code(
        self, auth_code: str, code_verifier: str, *, token_data: dict[str, Any] | None = None
    ) -> httpx.Request:  # pragma: no cover
        """Build token exchange request for authorization_code flow."""
        pass

    async def _perform_authorization(self) -> httpx.Request:  # pragma: no cover
        """Perform the authorization flow."""
        pass

    def _add_client_authentication_jwt(self, *, token_data: dict[str, Any]):  # pragma: no cover
        """Add JWT assertion for client authentication to token endpoint parameters."""
        pass

    async def _exchange_token_jwt_bearer(self) -> httpx.Request:
        """Build token exchange request for JWT bearer grant."""
        pass
