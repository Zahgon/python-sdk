import argparse
import logging
import sys
import warnings
from functools import partial
from urllib.parse import urlparse

import anyio

from mcp import types
from mcp.client._transport import ReadStream, WriteStream
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.shared.message import SessionMessage
from mcp.shared.session import RequestResponder

if not sys.warnoptions:
    warnings.simplefilter("ignore")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("client")


async def message_handler(
    message: RequestResponder[types.ServerRequest, types.ClientResult] | types.ServerNotification | Exception,
) -> None:
    pass


async def run_session(
    read_stream: ReadStream[SessionMessage | Exception],
    write_stream: WriteStream[SessionMessage],
    client_info: types.Implementation | None = None,
):
    pass


async def main(command_or_url: str, args: list[str], env: list[tuple[str, str]]):
    pass


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("command_or_url", help="Command or URL to connect to")
    parser.add_argument("args", nargs="*", help="Additional arguments")
    parser.add_argument(
        "-e",
        "--env",
        nargs=2,
        action="append",
        metavar=("KEY", "VALUE"),
        help="Environment variables to set. Can be used multiple times.",
        default=[],
    )

    args = parser.parse_args()
    anyio.run(partial(main, args.command_or_url, args.args, args.env), backend="trio")


if __name__ == "__main__":
    cli()
