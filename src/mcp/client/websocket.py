import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from pydantic import ValidationError
from websockets.asyncio.client import connect as ws_connect
from websockets.typing import Subprotocol

from mcp import types
from mcp.shared.message import SessionMessage


@asynccontextmanager
async def websocket_client(
    url: str,
) -> AsyncGenerator[
    tuple[MemoryObjectReceiveStream[SessionMessage | Exception], MemoryObjectSendStream[SessionMessage]],
    None,
]:
    """WebSocket client transport for MCP, symmetrical to the server version.

    Connects to 'url' using the 'mcp' subprotocol, then yields:
        (read_stream, write_stream)

    - read_stream: As you read from this stream, you'll receive either valid
      SessionMessage objects or Exception objects (when validation fails).
    - write_stream: Write SessionMessage objects to this stream to send them
      over the WebSocket to the server.
    """
    pass
