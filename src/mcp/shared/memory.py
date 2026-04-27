"""In-memory transports"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from mcp.shared._context_streams import ContextReceiveStream, ContextSendStream, create_context_streams
from mcp.shared.message import SessionMessage

MessageStream = tuple[ContextReceiveStream[SessionMessage | Exception], ContextSendStream[SessionMessage | Exception]]


@asynccontextmanager
async def create_client_server_memory_streams() -> AsyncGenerator[tuple[MessageStream, MessageStream], None]:
    """Creates a pair of bidirectional memory streams for client-server communication.

    Yields:
        A tuple of (client_streams, server_streams) where each is a tuple of
        (read_stream, write_stream)
    """
    pass
