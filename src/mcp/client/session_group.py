"""SessionGroup concurrently manages multiple MCP session connections.

Tools, resources, and prompts are aggregated across servers. Servers may
be connected to or disconnected from at any point after initialization.

This abstraction can handle naming collisions using a custom user-provided hook.
"""

import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Any, TypeAlias

import anyio
import httpx
from pydantic import BaseModel, Field
from typing_extensions import Self

import mcp
from mcp import types
from mcp.client.session import ElicitationFnT, ListRootsFnT, LoggingFnT, MessageHandlerFnT, SamplingFnT
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from mcp.shared.exceptions import MCPError
from mcp.shared.session import ProgressFnT


class SseServerParameters(BaseModel):
    """Parameters for initializing an sse_client."""

    # The endpoint URL.
    url: str

    # Optional headers to include in requests.
    headers: dict[str, Any] | None = None

    # HTTP timeout for regular operations (in seconds).
    timeout: float = 5.0

    # Timeout for SSE read operations (in seconds).
    sse_read_timeout: float = 300.0


class StreamableHttpParameters(BaseModel):
    """Parameters for initializing a streamable_http_client."""

    # The endpoint URL.
    url: str

    # Optional headers to include in requests.
    headers: dict[str, Any] | None = None

    # HTTP timeout for regular operations (in seconds).
    timeout: float = 30.0

    # Timeout for SSE read operations (in seconds).
    sse_read_timeout: float = 300.0

    # Close the client session when the transport closes.
    terminate_on_close: bool = True


ServerParameters: TypeAlias = StdioServerParameters | SseServerParameters | StreamableHttpParameters


# Use dataclass instead of Pydantic BaseModel
# because Pydantic BaseModel cannot handle Protocol fields.
@dataclass
class ClientSessionParameters:
    """Parameters for establishing a client session to an MCP server."""

    read_timeout_seconds: float | None = None
    sampling_callback: SamplingFnT | None = None
    elicitation_callback: ElicitationFnT | None = None
    list_roots_callback: ListRootsFnT | None = None
    logging_callback: LoggingFnT | None = None
    message_handler: MessageHandlerFnT | None = None
    client_info: types.Implementation | None = None


class ClientSessionGroup:
    """Client for managing connections to multiple MCP servers.

    This class is responsible for encapsulating management of server connections.
    It aggregates tools, resources, and prompts from all connected servers.

    For auxiliary handlers, such as resource subscription, this is delegated to
    the client and can be accessed via the session.

    Example:
        ```python
        name_fn = lambda name, server_info: f"{(server_info.name)}_{name}"
        async with ClientSessionGroup(component_name_hook=name_fn) as group:
            for server_param in server_params:
                await group.connect_to_server(server_param)
            ...
        ```
    """

    class _ComponentNames(BaseModel):
        """Used for reverse index to find components."""

        prompts: set[str] = Field(default_factory=set)
        resources: set[str] = Field(default_factory=set)
        tools: set[str] = Field(default_factory=set)

    # Standard MCP components.
    _prompts: dict[str, types.Prompt]
    _resources: dict[str, types.Resource]
    _tools: dict[str, types.Tool]

    # Client-server connection management.
    _sessions: dict[mcp.ClientSession, _ComponentNames]
    _tool_to_session: dict[str, mcp.ClientSession]
    _exit_stack: contextlib.AsyncExitStack
    _session_exit_stacks: dict[mcp.ClientSession, contextlib.AsyncExitStack]

    # Optional fn consuming (component_name, server_info) for custom names.
    # This is to provide a means to mitigate naming conflicts across servers.
    # Example: (tool_name, server_info) => "{result.server_info.name}.{tool_name}"
    _ComponentNameHook: TypeAlias = Callable[[str, types.Implementation], str]
    _component_name_hook: _ComponentNameHook | None

    def __init__(
        self,
        exit_stack: contextlib.AsyncExitStack | None = None,
        component_name_hook: _ComponentNameHook | None = None,
    ) -> None:
        """Initializes the MCP client."""

        self._tools = {}
        self._resources = {}
        self._prompts = {}

        self._sessions = {}
        self._tool_to_session = {}
        if exit_stack is None:
            self._exit_stack = contextlib.AsyncExitStack()
            self._owns_exit_stack = True
        else:
            self._exit_stack = exit_stack
            self._owns_exit_stack = False
        self._session_exit_stacks = {}
        self._component_name_hook = component_name_hook

    async def __aenter__(self) -> Self:  # pragma: no cover
        # Enter the exit stack only if we created it ourselves
        if self._owns_exit_stack:
            await self._exit_stack.__aenter__()
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> bool | None:  # pragma: no cover
        """Closes session exit stacks and main exit stack upon completion."""

        # Only close the main exit stack if we created it
        if self._owns_exit_stack:
            await self._exit_stack.aclose()

        # Concurrently close session stacks.
        async with anyio.create_task_group() as tg:
            for exit_stack in self._session_exit_stacks.values():
                tg.start_soon(exit_stack.aclose)

    @property
    def sessions(self) -> list[mcp.ClientSession]:
        """Returns the list of sessions being managed."""
        pass

    @property
    def prompts(self) -> dict[str, types.Prompt]:
        """Returns the prompts as a dictionary of names to prompts."""
        pass

    @property
    def resources(self) -> dict[str, types.Resource]:
        """Returns the resources as a dictionary of names to resources."""
        pass

    @property
    def tools(self) -> dict[str, types.Tool]:
        """Returns the tools as a dictionary of names to tools."""
        pass

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        read_timeout_seconds: float | None = None,
        progress_callback: ProgressFnT | None = None,
        *,
        meta: types.RequestParamsMeta | None = None,
    ) -> types.CallToolResult:
        """Executes a tool given its name and arguments."""
        pass

    async def disconnect_from_server(self, session: mcp.ClientSession) -> None:
        """Disconnects from a single MCP server."""
        pass

    async def connect_with_session(
        self, server_info: types.Implementation, session: mcp.ClientSession
    ) -> mcp.ClientSession:
        """Connects to a single MCP server."""
        pass

    async def connect_to_server(
        self,
        server_params: ServerParameters,
        session_params: ClientSessionParameters | None = None,
    ) -> mcp.ClientSession:
        """Connects to a single MCP server."""
        pass

    async def _establish_session(
        self,
        server_params: ServerParameters,
        session_params: ClientSessionParameters,
    ) -> tuple[types.Implementation, mcp.ClientSession]:
        """Establish a client session to an MCP server."""
        pass

    async def _aggregate_components(self, server_info: types.Implementation, session: mcp.ClientSession) -> None:
        """Aggregates prompts, resources, and tools from a given session."""
        pass

    def _component_name(self, name: str, server_info: types.Implementation) -> str:
        pass
