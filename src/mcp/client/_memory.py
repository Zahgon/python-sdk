"""In-memory transport for testing MCP servers without network overhead."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from types import TracebackType
from typing import Any

import anyio

from mcp.client._transport import TransportStreams
from mcp.server import Server
from mcp.server.mcpserver import MCPServer
from mcp.shared.memory import create_client_server_memory_streams


class InMemoryTransport:
    """In-memory transport for testing MCP servers without network overhead.

    This transport starts the server in a background task and provides
    streams for client-side communication. The server is automatically
    stopped when the context manager exits.
    """

    def __init__(self, server: Server[Any] | MCPServer, *, raise_exceptions: bool = False) -> None:
        """Initialize the in-memory transport.

        Args:
            server: The MCP server to connect to (Server or MCPServer instance)
            raise_exceptions: Whether to raise exceptions from the server
        """
        self._server = server
        self._raise_exceptions = raise_exceptions
        self._cm: AbstractAsyncContextManager[TransportStreams] | None = None

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[TransportStreams]:
        """Connect to the server and yield streams for communication."""
        pass

    async def __aenter__(self) -> TransportStreams:
        """Connect to the server and return streams for communication."""
        self._cm = self._connect()
        return await self._cm.__aenter__()

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        """Close the transport and stop the server."""
        if self._cm is not None:  # pragma: no branch
            await self._cm.__aexit__(exc_type, exc_val, exc_tb)
            self._cm = None
