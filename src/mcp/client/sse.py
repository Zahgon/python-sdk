import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import anyio
import httpx
from anyio.abc import TaskStatus
from httpx_sse import aconnect_sse
from httpx_sse._exceptions import SSEError

from mcp import types
from mcp.shared._context_streams import create_context_streams
from mcp.shared._httpx_utils import McpHttpClientFactory, create_mcp_http_client
from mcp.shared.message import SessionMessage

logger = logging.getLogger(__name__)


def remove_request_params(url: str) -> str:
    pass


def _extract_session_id_from_endpoint(endpoint_url: str) -> str | None:
    pass


@asynccontextmanager
async def sse_client(
    url: str,
    headers: dict[str, Any] | None = None,
    timeout: float = 5.0,
    sse_read_timeout: float = 300.0,
    httpx_client_factory: McpHttpClientFactory = create_mcp_http_client,
    auth: httpx.Auth | None = None,
    on_session_created: Callable[[str], None] | None = None,
):
    """Client transport for SSE.

    `sse_read_timeout` determines how long (in seconds) the client will wait for a new
    event before disconnecting. All other HTTP operations are controlled by `timeout`.

    Args:
        url: The SSE endpoint URL.
        headers: Optional headers to include in requests.
        timeout: HTTP timeout for regular operations (in seconds).
        sse_read_timeout: Timeout for SSE read operations (in seconds).
        httpx_client_factory: Factory function for creating the HTTPX client.
        auth: Optional HTTPX authentication handler.
        on_session_created: Optional callback invoked with the session ID when received.
    """
    pass
