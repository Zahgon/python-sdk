import importlib.metadata
import logging
import sys
import warnings

import anyio

from mcp.server.models import InitializationOptions
from mcp.server.session import ServerSession
from mcp.server.stdio import stdio_server
from mcp.types import ServerCapabilities

if not sys.warnoptions:
    warnings.simplefilter("ignore")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")


async def receive_loop(session: ServerSession):
    pass


async def main():
    pass


if __name__ == "__main__":
    anyio.run(main, backend="trio")
