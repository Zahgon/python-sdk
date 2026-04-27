from contextlib import asynccontextmanager

import anyio
from pydantic_core import ValidationError
from starlette.types import Receive, Scope, Send
from starlette.websockets import WebSocket

from mcp import types
from mcp.shared._context_streams import create_context_streams
from mcp.shared.message import SessionMessage


@asynccontextmanager
async def websocket_server(scope: Scope, receive: Receive, send: Send):
    """WebSocket server transport for MCP. This is an ASGI application, suitable for use
    with a framework like Starlette and a server like Hypercorn.
    """
    pass
