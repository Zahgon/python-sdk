"""Experimental handlers for the low-level MCP server.

WARNING: These APIs are experimental and may change without notice.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Generic

from typing_extensions import TypeVar

from mcp.server.context import ServerRequestContext
from mcp.server.experimental.task_support import TaskSupport
from mcp.shared.exceptions import MCPError
from mcp.shared.experimental.tasks.helpers import cancel_task
from mcp.shared.experimental.tasks.in_memory_task_store import InMemoryTaskStore
from mcp.shared.experimental.tasks.message_queue import InMemoryTaskMessageQueue, TaskMessageQueue
from mcp.shared.experimental.tasks.store import TaskStore
from mcp.types import (
    INVALID_PARAMS,
    CancelTaskRequestParams,
    CancelTaskResult,
    GetTaskPayloadRequest,
    GetTaskPayloadRequestParams,
    GetTaskPayloadResult,
    GetTaskRequestParams,
    GetTaskResult,
    ListTasksResult,
    PaginatedRequestParams,
    ServerCapabilities,
    ServerTasksCapability,
    ServerTasksRequestsCapability,
    TasksCallCapability,
    TasksCancelCapability,
    TasksListCapability,
    TasksToolsCapability,
)

logger = logging.getLogger(__name__)

LifespanResultT = TypeVar("LifespanResultT", default=Any)


class ExperimentalHandlers(Generic[LifespanResultT]):
    """Experimental request/notification handlers.

    WARNING: These APIs are experimental and may change without notice.
    """

    def __init__(
        self,
        add_request_handler: Callable[
            [str, Callable[[ServerRequestContext[LifespanResultT], Any], Awaitable[Any]]], None
        ],
        has_handler: Callable[[str], bool],
    ) -> None:
        self._add_request_handler = add_request_handler
        self._has_handler = has_handler
        self._task_support: TaskSupport | None = None

    @property
    def task_support(self) -> TaskSupport | None:
        """Get the task support configuration, if enabled."""
        pass

    def update_capabilities(self, capabilities: ServerCapabilities) -> None:
        # Only add tasks capability if handlers are registered
        if not any(self._has_handler(method) for method in ["tasks/get", "tasks/list", "tasks/cancel", "tasks/result"]):
            return

        capabilities.tasks = ServerTasksCapability()
        if self._has_handler("tasks/list"):
            capabilities.tasks.list = TasksListCapability()
        if self._has_handler("tasks/cancel"):
            capabilities.tasks.cancel = TasksCancelCapability()

        capabilities.tasks.requests = ServerTasksRequestsCapability(
            tools=TasksToolsCapability(call=TasksCallCapability())
        )  # assuming always supported for now

    def enable_tasks(
        self,
        store: TaskStore | None = None,
        queue: TaskMessageQueue | None = None,
        *,
        on_get_task: Callable[[ServerRequestContext[LifespanResultT], GetTaskRequestParams], Awaitable[GetTaskResult]]
        | None = None,
        on_task_result: Callable[
            [ServerRequestContext[LifespanResultT], GetTaskPayloadRequestParams], Awaitable[GetTaskPayloadResult]
        ]
        | None = None,
        on_list_tasks: Callable[
            [ServerRequestContext[LifespanResultT], PaginatedRequestParams | None], Awaitable[ListTasksResult]
        ]
        | None = None,
        on_cancel_task: Callable[
            [ServerRequestContext[LifespanResultT], CancelTaskRequestParams], Awaitable[CancelTaskResult]
        ]
        | None = None,
    ) -> TaskSupport:
        """Enable experimental task support.

        This sets up the task infrastructure and registers handlers for
        tasks/get, tasks/result, tasks/list, and tasks/cancel. Custom handlers
        can be provided via the on_* kwargs; any not provided will use defaults.

        Args:
            store: Custom TaskStore implementation (defaults to InMemoryTaskStore)
            queue: Custom TaskMessageQueue implementation (defaults to InMemoryTaskMessageQueue)
            on_get_task: Custom handler for tasks/get
            on_task_result: Custom handler for tasks/result
            on_list_tasks: Custom handler for tasks/list
            on_cancel_task: Custom handler for tasks/cancel

        Returns:
            The TaskSupport configuration object

        Example:
            Simple in-memory setup:

            ```python
            server.experimental.enable_tasks()
            ```

            Custom store/queue for distributed systems:

            ```python
            server.experimental.enable_tasks(
                store=RedisTaskStore(redis_url),
                queue=RedisTaskMessageQueue(redis_url),
            )
            ```

        WARNING: This API is experimental and may change without notice.
        """
        pass
