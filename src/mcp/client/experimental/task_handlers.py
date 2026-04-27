"""Experimental task handler protocols for server -> client requests.

This module provides Protocol types and default handlers for when servers
send task-related requests to clients (the reverse of normal client -> server flow).

WARNING: These APIs are experimental and may change without notice.

Use cases:
- Server sends task-augmented sampling/elicitation request to client
- Client creates a local task, spawns background work, returns CreateTaskResult
- Server polls client's task status via tasks/get, tasks/result, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from pydantic import TypeAdapter

from mcp import types
from mcp.shared._context import RequestContext
from mcp.shared.session import RequestResponder

if TYPE_CHECKING:
    from mcp.client.session import ClientSession


class GetTaskHandlerFnT(Protocol):
    """Handler for tasks/get requests from server.

    WARNING: This is experimental and may change without notice.
    """

    async def __call__(
        self,
        context: RequestContext[ClientSession],
        params: types.GetTaskRequestParams,
    ) -> types.GetTaskResult | types.ErrorData: ...  # pragma: no branch


class GetTaskResultHandlerFnT(Protocol):
    """Handler for tasks/result requests from server.

    WARNING: This is experimental and may change without notice.
    """

    async def __call__(
        self,
        context: RequestContext[ClientSession],
        params: types.GetTaskPayloadRequestParams,
    ) -> types.GetTaskPayloadResult | types.ErrorData: ...  # pragma: no branch


class ListTasksHandlerFnT(Protocol):
    """Handler for tasks/list requests from server.

    WARNING: This is experimental and may change without notice.
    """

    async def __call__(
        self,
        context: RequestContext[ClientSession],
        params: types.PaginatedRequestParams | None,
    ) -> types.ListTasksResult | types.ErrorData: ...  # pragma: no branch


class CancelTaskHandlerFnT(Protocol):
    """Handler for tasks/cancel requests from server.

    WARNING: This is experimental and may change without notice.
    """

    async def __call__(
        self,
        context: RequestContext[ClientSession],
        params: types.CancelTaskRequestParams,
    ) -> types.CancelTaskResult | types.ErrorData: ...  # pragma: no branch


class TaskAugmentedSamplingFnT(Protocol):
    """Handler for task-augmented sampling/createMessage requests from server.

    When server sends a CreateMessageRequest with task field, this callback
    is invoked. The callback should create a task, spawn background work,
    and return CreateTaskResult immediately.

    WARNING: This is experimental and may change without notice.
    """

    async def __call__(
        self,
        context: RequestContext[ClientSession],
        params: types.CreateMessageRequestParams,
        task_metadata: types.TaskMetadata,
    ) -> types.CreateTaskResult | types.ErrorData: ...  # pragma: no branch


class TaskAugmentedElicitationFnT(Protocol):
    """Handler for task-augmented elicitation/create requests from server.

    When server sends an ElicitRequest with task field, this callback
    is invoked. The callback should create a task, spawn background work,
    and return CreateTaskResult immediately.

    WARNING: This is experimental and may change without notice.
    """

    async def __call__(
        self,
        context: RequestContext[ClientSession],
        params: types.ElicitRequestParams,
        task_metadata: types.TaskMetadata,
    ) -> types.CreateTaskResult | types.ErrorData: ...  # pragma: no branch


async def default_get_task_handler(
    context: RequestContext[ClientSession],
    params: types.GetTaskRequestParams,
) -> types.GetTaskResult | types.ErrorData:
    pass


async def default_get_task_result_handler(
    context: RequestContext[ClientSession],
    params: types.GetTaskPayloadRequestParams,
) -> types.GetTaskPayloadResult | types.ErrorData:
    pass


async def default_list_tasks_handler(
    context: RequestContext[ClientSession],
    params: types.PaginatedRequestParams | None,
) -> types.ListTasksResult | types.ErrorData:
    pass


async def default_cancel_task_handler(
    context: RequestContext[ClientSession],
    params: types.CancelTaskRequestParams,
) -> types.CancelTaskResult | types.ErrorData:
    pass


async def default_task_augmented_sampling(
    context: RequestContext[ClientSession],
    params: types.CreateMessageRequestParams,
    task_metadata: types.TaskMetadata,
) -> types.CreateTaskResult | types.ErrorData:
    pass


async def default_task_augmented_elicitation(
    context: RequestContext[ClientSession],
    params: types.ElicitRequestParams,
    task_metadata: types.TaskMetadata,
) -> types.CreateTaskResult | types.ErrorData:
    pass


@dataclass
class ExperimentalTaskHandlers:
    """Container for experimental task handlers.

    Groups all task-related handlers that handle server -> client requests.
    This includes both pure task requests (get, list, cancel, result) and
    task-augmented request handlers (sampling, elicitation with task field).

    WARNING: These APIs are experimental and may change without notice.

    Example:
        ```python
        handlers = ExperimentalTaskHandlers(
            get_task=my_get_task_handler,
            list_tasks=my_list_tasks_handler,
        )
        session = ClientSession(..., experimental_task_handlers=handlers)
        ```
    """

    # Pure task request handlers
    get_task: GetTaskHandlerFnT = field(default=default_get_task_handler)
    get_task_result: GetTaskResultHandlerFnT = field(default=default_get_task_result_handler)
    list_tasks: ListTasksHandlerFnT = field(default=default_list_tasks_handler)
    cancel_task: CancelTaskHandlerFnT = field(default=default_cancel_task_handler)

    # Task-augmented request handlers
    augmented_sampling: TaskAugmentedSamplingFnT = field(default=default_task_augmented_sampling)
    augmented_elicitation: TaskAugmentedElicitationFnT = field(default=default_task_augmented_elicitation)

    def build_capability(self) -> types.ClientTasksCapability | None:
        """Build ClientTasksCapability from the configured handlers.

        Returns a capability object that reflects which handlers are configured
        (i.e., not using the default "not supported" handlers).

        Returns:
            ClientTasksCapability if any handlers are provided, None otherwise
        """
        pass

    @staticmethod
    def handles_request(request: types.ServerRequest) -> bool:
        """Check if this handler handles the given request type."""
        pass

    async def handle_request(
        self,
        ctx: RequestContext[ClientSession],
        responder: RequestResponder[types.ServerRequest, types.ClientResult],
    ) -> None:
        """Handle a task-related request from the server.

        Call handles_request() first to check if this handler can handle the request.
        """
        pass


# Backwards compatibility aliases
default_task_augmented_sampling_callback = default_task_augmented_sampling
default_task_augmented_elicitation_callback = default_task_augmented_elicitation
