"""Implements StreamableHTTP transport for MCP clients."""

from __future__ import annotations as _annotations

import contextlib
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass

import anyio
import httpx
from anyio.abc import TaskGroup
from httpx_sse import EventSource, ServerSentEvent, aconnect_sse
from pydantic import ValidationError

from mcp.client._transport import TransportStreams
from mcp.shared._context_streams import ContextReceiveStream, ContextSendStream, create_context_streams
from mcp.shared._httpx_utils import create_mcp_http_client
from mcp.shared.message import ClientMessageMetadata, SessionMessage
from mcp.types import (
    INTERNAL_ERROR,
    INVALID_REQUEST,
    PARSE_ERROR,
    ErrorData,
    InitializeResult,
    JSONRPCError,
    JSONRPCMessage,
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    RequestId,
    jsonrpc_message_adapter,
)

logger = logging.getLogger(__name__)


# TODO(Marcelo): Put the TransportStreams in a module under shared, so we can import here.
SessionMessageOrError = SessionMessage | Exception
StreamWriter = ContextSendStream[SessionMessageOrError]
StreamReader = ContextReceiveStream[SessionMessage]

MCP_SESSION_ID = "mcp-session-id"
MCP_PROTOCOL_VERSION = "mcp-protocol-version"
LAST_EVENT_ID = "last-event-id"

# Reconnection defaults
DEFAULT_RECONNECTION_DELAY_MS = 1000  # 1 second fallback when server doesn't provide retry
MAX_RECONNECTION_ATTEMPTS = 2  # Max retry attempts before giving up


class StreamableHTTPError(Exception):
    """Base exception for StreamableHTTP transport errors."""


class ResumptionError(StreamableHTTPError):
    """Raised when resumption request is invalid."""


@dataclass
class RequestContext:
    """Context for a request operation."""

    client: httpx.AsyncClient
    session_id: str | None
    session_message: SessionMessage
    metadata: ClientMessageMetadata | None
    read_stream_writer: StreamWriter


class StreamableHTTPTransport:
    """StreamableHTTP client transport implementation."""

    def __init__(self, url: str) -> None:
        """Initialize the StreamableHTTP transport.

        Args:
            url: The endpoint URL.
        """
        self.url = url
        self.session_id: str | None = None
        self.protocol_version: str | None = None

    def _prepare_headers(self) -> dict[str, str]:
        """Build MCP-specific request headers.

        These headers will be merged with the httpx.AsyncClient's default headers,
        with these MCP-specific headers taking precedence.
        """
        pass

    def _is_initialization_request(self, message: JSONRPCMessage) -> bool:
        """Check if the message is an initialization request."""
        pass

    def _is_initialized_notification(self, message: JSONRPCMessage) -> bool:
        """Check if the message is an initialized notification."""
        pass

    def _maybe_extract_session_id_from_response(self, response: httpx.Response) -> None:
        """Extract and store session ID from response headers."""
        pass

    def _maybe_extract_protocol_version_from_message(self, message: JSONRPCMessage) -> None:
        """Extract protocol version from initialization response message."""
        pass

    async def _handle_sse_event(
        self,
        sse: ServerSentEvent,
        read_stream_writer: StreamWriter,
        original_request_id: RequestId | None = None,
        resumption_callback: Callable[[str], Awaitable[None]] | None = None,
        is_initialization: bool = False,
    ) -> bool:
        """Handle an SSE event, returning True if the response is complete."""
        pass

    async def handle_get_stream(self, client: httpx.AsyncClient, read_stream_writer: StreamWriter) -> None:
        """Handle GET stream for server-initiated messages with auto-reconnect."""
        pass

    async def _handle_resumption_request(self, ctx: RequestContext) -> None:
        """Handle a resumption request using GET with SSE."""
        pass

    async def _handle_post_request(self, ctx: RequestContext) -> None:
        """Handle a POST request with response processing."""
        pass

    async def _handle_json_response(
        self,
        response: httpx.Response,
        read_stream_writer: StreamWriter,
        is_initialization: bool = False,
        *,
        request_id: RequestId,
    ) -> None:
        """Handle JSON response from the server."""
        pass

    async def _handle_sse_response(
        self,
        response: httpx.Response,
        ctx: RequestContext,
        is_initialization: bool = False,
    ) -> None:
        """Handle SSE response from the server."""
        pass

    async def _handle_reconnection(
        self,
        ctx: RequestContext,
        last_event_id: str,
        retry_interval_ms: int | None = None,
        attempt: int = 0,
    ) -> None:
        """Reconnect with Last-Event-ID to resume stream after server disconnect."""
        pass

    async def post_writer(
        self,
        client: httpx.AsyncClient,
        write_stream_reader: StreamReader,
        read_stream_writer: StreamWriter,
        write_stream: ContextSendStream[SessionMessage],
        start_get_stream: Callable[[], None],
        tg: TaskGroup,
    ) -> None:
        """Handle writing requests to the server."""
        pass

    async def terminate_session(self, client: httpx.AsyncClient) -> None:
        """Terminate the session by sending a DELETE request."""
        pass

    # TODO(Marcelo): Check the TODO below, and cover this with tests if necessary.
    def get_session_id(self) -> str | None:
        """Get the current session ID."""
        pass


# TODO(Marcelo): I've dropped the `get_session_id` callback because it breaks the Transport protocol. Is that needed?
# It's a completely wrong abstraction, so removal is a good idea. But if we need the client to find the session ID,
# we should think about a better way to do it. I believe we can achieve it with other means.
@asynccontextmanager
async def streamable_http_client(
    url: str,
    *,
    http_client: httpx.AsyncClient | None = None,
    terminate_on_close: bool = True,
) -> AsyncGenerator[TransportStreams, None]:
    """Client transport for StreamableHTTP.

    Args:
        url: The MCP server endpoint URL.
        http_client: Optional pre-configured httpx.AsyncClient. If None, a default
            client with recommended MCP timeouts will be created. To configure headers,
            authentication, or other HTTP settings, create an httpx.AsyncClient and pass it here.
        terminate_on_close: If True, send a DELETE request to terminate the session when the context exits.

    Yields:
        Tuple containing:
            - read_stream: Stream for reading messages from the server
            - write_stream: Stream for sending messages to the server

    Example:
        See examples/snippets/clients/ for usage patterns.
    """
    pass
