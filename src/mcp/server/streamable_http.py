"""StreamableHTTP Server Transport Module

This module implements an HTTP transport layer with Streamable HTTP.

The transport handles bidirectional communication using HTTP requests and
responses, with streaming support for long-running operations.
"""

import logging
import re
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

import anyio
import pydantic_core
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from pydantic import ValidationError
from sse_starlette import EventSourceResponse
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Receive, Scope, Send

from mcp.server.transport_security import TransportSecurityMiddleware, TransportSecuritySettings
from mcp.shared._context_streams import ContextReceiveStream, ContextSendStream, create_context_streams
from mcp.shared._stream_protocols import ReadStream, WriteStream
from mcp.shared.message import ServerMessageMetadata, SessionMessage
from mcp.shared.version import SUPPORTED_PROTOCOL_VERSIONS
from mcp.types import (
    DEFAULT_NEGOTIATED_VERSION,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    PARSE_ERROR,
    ErrorData,
    JSONRPCError,
    JSONRPCMessage,
    JSONRPCRequest,
    JSONRPCResponse,
    RequestId,
    jsonrpc_message_adapter,
)

logger = logging.getLogger(__name__)


# Header names
MCP_SESSION_ID_HEADER = "mcp-session-id"
MCP_PROTOCOL_VERSION_HEADER = "mcp-protocol-version"
LAST_EVENT_ID_HEADER = "last-event-id"

# Content types
CONTENT_TYPE_JSON = "application/json"
CONTENT_TYPE_SSE = "text/event-stream"

# Special key for the standalone GET stream
GET_STREAM_KEY = "_GET_stream"

# Session ID validation pattern (visible ASCII characters ranging from 0x21 to 0x7E)
# Pattern ensures entire string contains only valid characters by using ^ and $ anchors
SESSION_ID_PATTERN = re.compile(r"^[\x21-\x7E]+$")

# Type aliases
StreamId = str
EventId = str


@dataclass
class EventMessage:
    """A JSONRPCMessage with an optional event ID for stream resumability."""

    message: JSONRPCMessage
    event_id: str | None = None


EventCallback = Callable[[EventMessage], Awaitable[None]]


class EventStore(ABC):
    """Interface for resumability support via event storage."""

    @abstractmethod
    async def store_event(self, stream_id: StreamId, message: JSONRPCMessage | None) -> EventId:
        """Stores an event for later retrieval.

        Args:
            stream_id: ID of the stream the event belongs to
            message: The JSON-RPC message to store, or None for priming events

        Returns:
            The generated event ID for the stored event.
        """
        pass  # pragma: no cover

    @abstractmethod
    async def replay_events_after(
        self,
        last_event_id: EventId,
        send_callback: EventCallback,
    ) -> StreamId | None:
        """Replays events that occurred after the specified event ID.

        Args:
            last_event_id: The ID of the last event the client received
            send_callback: A callback function to send events to the client

        Returns:
            The stream ID of the replayed events, or None if no events were found.
        """
        pass  # pragma: no cover


class StreamableHTTPServerTransport:
    """HTTP server transport with event streaming support for MCP.

    Handles JSON-RPC messages in HTTP POST requests with SSE streaming.
    Supports optional JSON responses and session management.
    """

    # Server notification streams for POST requests as well as standalone SSE stream
    _read_stream_writer: ContextSendStream[SessionMessage | Exception] | None = None
    _read_stream: ContextReceiveStream[SessionMessage | Exception] | None = None
    _write_stream: ContextSendStream[SessionMessage] | None = None
    _write_stream_reader: ContextReceiveStream[SessionMessage] | None = None
    _security: TransportSecurityMiddleware

    def __init__(
        self,
        mcp_session_id: str | None,
        is_json_response_enabled: bool = False,
        event_store: EventStore | None = None,
        security_settings: TransportSecuritySettings | None = None,
        retry_interval: int | None = None,
    ) -> None:
        """Initialize a new StreamableHTTP server transport.

        Args:
            mcp_session_id: Optional session identifier for this connection.
                            Must contain only visible ASCII characters (0x21-0x7E).
            is_json_response_enabled: If True, return JSON responses for requests
                                    instead of SSE streams. Default is False.
            event_store: Event store for resumability support. If provided,
                        resumability will be enabled, allowing clients to
                        reconnect and resume messages.
            security_settings: Optional security settings for DNS rebinding protection.
            retry_interval: Retry interval in milliseconds to suggest to clients in SSE
                           retry field. When set, the server will send a retry field in
                           SSE priming events to control client reconnection timing for
                           polling behavior. Only used when event_store is provided.

        Raises:
            ValueError: If the session ID contains invalid characters.
        """
        if mcp_session_id is not None and not SESSION_ID_PATTERN.fullmatch(mcp_session_id):
            raise ValueError("Session ID must only contain visible ASCII characters (0x21-0x7E)")

        self.mcp_session_id = mcp_session_id
        self.is_json_response_enabled = is_json_response_enabled
        self._event_store = event_store
        self._security = TransportSecurityMiddleware(security_settings)
        self._retry_interval = retry_interval
        self._request_streams: dict[
            RequestId,
            tuple[
                MemoryObjectSendStream[EventMessage],
                MemoryObjectReceiveStream[EventMessage],
            ],
        ] = {}
        self._sse_stream_writers: dict[RequestId, MemoryObjectSendStream[dict[str, str]]] = {}
        self._terminated = False
        # Idle timeout cancel scope; managed by the session manager.
        self.idle_scope: anyio.CancelScope | None = None

    @property
    def is_terminated(self) -> bool:
        """Check if this transport has been explicitly terminated."""
        pass

    def close_sse_stream(self, request_id: RequestId) -> None:  # pragma: no cover
        """Close SSE connection for a specific request without terminating the stream.

        This method closes the HTTP connection for the specified request, triggering
        client reconnection. Events continue to be stored in the event store and will
        be replayed when the client reconnects with Last-Event-ID.

        Use this to implement polling behavior during long-running operations -
        the client will reconnect after the retry interval specified in the priming event.

        Args:
            request_id: The request ID whose SSE stream should be closed.

        Note:
            This is a no-op if there is no active stream for the request ID.
            Requires event_store to be configured for events to be stored during
            the disconnect.
        """
        pass

    def close_standalone_sse_stream(self) -> None:  # pragma: no cover
        """Close the standalone GET SSE stream, triggering client reconnection.

        This method closes the HTTP connection for the standalone GET stream used
        for unsolicited server-to-client notifications. The client SHOULD reconnect
        with Last-Event-ID to resume receiving notifications.

        Use this to implement polling behavior for the notification stream -
        the client will reconnect after the retry interval specified in the priming event.

        Note:
            This is a no-op if there is no active standalone SSE stream.
            Requires event_store to be configured for events to be stored during
            the disconnect.
            Currently, client reconnection for standalone GET streams is NOT
            implemented - this is a known gap (see test_standalone_get_stream_reconnection).
        """
        pass

    def _create_session_message(
        self,
        message: JSONRPCMessage,
        request: Request,
        request_id: RequestId,
        protocol_version: str,
    ) -> SessionMessage:
        """Create a session message with metadata including close_sse_stream callback.

        The close_sse_stream callbacks are only provided when the client supports
        resumability (protocol version >= 2025-11-25). Old clients can't resume if
        the stream is closed early because they didn't receive a priming event.
        """
        pass

    async def _maybe_send_priming_event(
        self,
        request_id: RequestId,
        sse_stream_writer: MemoryObjectSendStream[dict[str, Any]],
        protocol_version: str,
    ) -> None:
        """Send priming event for SSE resumability if event_store is configured.

        Only sends priming events to clients with protocol version >= 2025-11-25,
        which includes the fix for handling empty SSE data. Older clients would
        crash trying to parse empty data as JSON.
        """
        pass

    def _create_error_response(
        self,
        error_message: str,
        status_code: HTTPStatus,
        error_code: int = INVALID_REQUEST,
        headers: dict[str, str] | None = None,
    ) -> Response:
        """Create an error response with a simple string message."""
        pass

    def _create_json_response(
        self,
        response_message: JSONRPCMessage | None,
        status_code: HTTPStatus = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
    ) -> Response:
        """Create a JSON response from a JSONRPCMessage."""
        pass

    def _get_session_id(self, request: Request) -> str | None:
        """Extract the session ID from request headers."""
        pass

    def _create_event_data(self, event_message: EventMessage) -> dict[str, str]:
        """Create event data dictionary from an EventMessage."""
        pass

    async def _clean_up_memory_streams(self, request_id: RequestId) -> None:
        """Clean up memory streams for a given request ID."""
        pass

    async def handle_request(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Application entry point that handles all HTTP requests."""
        pass

    def _check_accept_headers(self, request: Request) -> tuple[bool, bool]:
        """Check if the request accepts the required media types.

        Supports wildcard media types per RFC 7231, section 5.3.2:
        - */* matches any media type
        - application/* matches any application/ subtype
        - text/* matches any text/ subtype
        """
        pass

    def _check_content_type(self, request: Request) -> bool:
        """Check if the request has the correct Content-Type."""
        pass

    async def _validate_accept_header(self, request: Request, scope: Scope, send: Send) -> bool:
        """Validate Accept header based on response mode. Returns True if valid."""
        pass

    async def _handle_post_request(self, scope: Scope, request: Request, receive: Receive, send: Send) -> None:
        """Handle POST requests containing JSON-RPC messages."""
        pass

    async def _handle_get_request(self, request: Request, send: Send) -> None:
        """Handle GET request to establish SSE.

        This allows the server to communicate to the client without the client
        first sending data via HTTP POST. The server can send JSON-RPC requests
        and notifications on this stream.
        """
        pass

    async def _handle_delete_request(self, request: Request, send: Send) -> None:
        """Handle DELETE requests for explicit session termination."""
        pass

    async def terminate(self) -> None:
        """Terminate the current session, closing all streams.

        Once terminated, all requests with this session ID will receive 404 Not Found.
        """
        pass

    async def _handle_unsupported_request(self, request: Request, send: Send) -> None:  # pragma: no cover
        """Handle unsupported HTTP methods."""
        pass

    async def _validate_request_headers(self, request: Request, send: Send) -> bool:  # pragma: lax no cover
        pass

    async def _validate_session(self, request: Request, send: Send) -> bool:
        """Validate the session ID in the request."""
        pass

    async def _validate_protocol_version(self, request: Request, send: Send) -> bool:
        """Validate the protocol version header in the request."""
        pass

    async def _replay_events(self, last_event_id: str, request: Request, send: Send) -> None:  # pragma: no cover
        """Replays events that would have been sent after the specified event ID.

        Only used when resumability is enabled.
        """
        pass

    @asynccontextmanager
    async def connect(
        self,
    ) -> AsyncGenerator[
        tuple[
            ReadStream[SessionMessage | Exception],
            WriteStream[SessionMessage],
        ],
        None,
    ]:
        """Context manager that provides read and write streams for a connection.

        Yields:
            Tuple of (read_stream, write_stream) for bidirectional communication
        """
        pass
