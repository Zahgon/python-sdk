"""SSE Server Transport Module

This module implements a Server-Sent Events (SSE) transport layer for MCP servers.

Example:
    ```python
    # Create an SSE transport at an endpoint
    sse = SseServerTransport("/messages/")

    # Create Starlette routes for SSE and message handling
    routes = [
        Route("/sse", endpoint=handle_sse, methods=["GET"]),
        Mount("/messages/", app=sse.handle_post_message),
    ]

    # Define handler functions
    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await app.run(
                streams[0], streams[1], app.create_initialization_options()
            )
        # Return empty response to avoid NoneType error
        return Response()

    # Create and run Starlette app
    starlette_app = Starlette(routes=routes)
    uvicorn.run(starlette_app, host="127.0.0.1", port=port)
    ```

Note: The handle_sse function must return a Response to avoid a
"TypeError: 'NoneType' object is not callable" error when client disconnects. The example above returns
an empty Response() after the SSE connection ends to fix this.

See SseServerTransport class documentation for more details.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import quote
from uuid import UUID, uuid4

import anyio
from pydantic import ValidationError
from sse_starlette import EventSourceResponse
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Receive, Scope, Send

from mcp import types
from mcp.server.transport_security import (
    TransportSecurityMiddleware,
    TransportSecuritySettings,
)
from mcp.shared._context_streams import ContextSendStream, create_context_streams
from mcp.shared.message import ServerMessageMetadata, SessionMessage

logger = logging.getLogger(__name__)


class SseServerTransport:
    """SSE server transport for MCP. This class provides two ASGI applications,
    suitable for use with a framework like Starlette and a server like Hypercorn:

        1. connect_sse() is an ASGI application which receives incoming GET requests,
           and sets up a new SSE stream to send server messages to the client.
        2. handle_post_message() is an ASGI application which receives incoming POST
           requests, which should contain client messages that link to a
           previously-established SSE session.
    """

    _endpoint: str
    _read_stream_writers: dict[UUID, ContextSendStream[SessionMessage | Exception]]
    _security: TransportSecurityMiddleware

    def __init__(self, endpoint: str, security_settings: TransportSecuritySettings | None = None) -> None:
        """Creates a new SSE server transport, which will direct the client to POST
        messages to the relative path given.

        Args:
            endpoint: A relative path where messages should be posted
                    (e.g., "/messages/").
            security_settings: Optional security settings for DNS rebinding protection.

        Note:
            We use relative paths instead of full URLs for several reasons:
            1. Security: Prevents cross-origin requests by ensuring clients only connect
               to the same origin they established the SSE connection with
            2. Flexibility: The server can be mounted at any path without needing to
               know its full URL
            3. Portability: The same endpoint configuration works across different
               environments (development, staging, production)

        Raises:
            ValueError: If the endpoint is a full URL instead of a relative path
        """

        super().__init__()

        # Validate that endpoint is a relative path and not a full URL
        if "://" in endpoint or endpoint.startswith("//") or "?" in endpoint or "#" in endpoint:
            raise ValueError(
                f"Given endpoint: {endpoint} is not a relative path (e.g., '/messages/'), "
                "expecting a relative path (e.g., '/messages/')."
            )

        # Ensure endpoint starts with a forward slash
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint

        self._endpoint = endpoint
        self._read_stream_writers = {}
        self._security = TransportSecurityMiddleware(security_settings)
        logger.debug(f"SseServerTransport initialized with endpoint: {endpoint}")

    @asynccontextmanager
    async def connect_sse(self, scope: Scope, receive: Receive, send: Send):  # pragma: no cover
        if scope["type"] != "http":
            logger.error("connect_sse received non-HTTP request")
            raise ValueError("connect_sse can only handle HTTP requests")

        # Validate request headers for DNS rebinding protection
        request = Request(scope, receive)
        error_response = await self._security.validate_request(request, is_post=False)
        if error_response:
            await error_response(scope, receive, send)
            raise ValueError("Request validation failed")

        logger.debug("Setting up SSE connection")

        read_stream_writer, read_stream = create_context_streams[SessionMessage | Exception](0)
        write_stream, write_stream_reader = create_context_streams[SessionMessage](0)

        session_id = uuid4()
        self._read_stream_writers[session_id] = read_stream_writer
        logger.debug(f"Created new session with ID: {session_id}")

        # Determine the full path for the message endpoint to be sent to the client.
        # scope['root_path'] is the prefix where the current Starlette app
        # instance is mounted.
        # e.g., "" if top-level, or "/api_prefix" if mounted under "/api_prefix".
        root_path = scope.get("root_path", "")

        # self._endpoint is the path *within* this app, e.g., "/messages".
        # Concatenating them gives the full absolute path from the server root.
        # e.g., "" + "/messages" -> "/messages"
        # e.g., "/api_prefix" + "/messages" -> "/api_prefix/messages"
        full_message_path_for_client = root_path.rstrip("/") + self._endpoint

        # This is the URI (path + query) the client will use to POST messages.
        client_post_uri_data = f"{quote(full_message_path_for_client)}?session_id={session_id.hex}"

        sse_stream_writer, sse_stream_reader = anyio.create_memory_object_stream[dict[str, Any]](0)

        async def sse_writer():
            pass

        async with anyio.create_task_group() as tg:

            async def response_wrapper(scope: Scope, receive: Receive, send: Send):
                """The EventSourceResponse returning signals a client close / disconnect.
                In this case we close our side of the streams to signal the client that
                the connection has been closed.
                """
                pass

            logger.debug("Starting SSE response task")
            tg.start_soon(response_wrapper, scope, receive, send)

            logger.debug("Yielding read and write streams")
            yield (read_stream, write_stream)

    async def handle_post_message(self, scope: Scope, receive: Receive, send: Send) -> None:  # pragma: no cover
        pass
