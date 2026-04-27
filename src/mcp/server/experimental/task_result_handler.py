"""TaskResultHandler - Integrated handler for tasks/result endpoint.

This implements the dequeue-send-wait pattern from the MCP Tasks spec:
1. Dequeue all pending messages for the task
2. Send them to the client via transport with relatedRequestId routing
3. Wait if task is not in terminal state
4. Return final result when task completes

This is the core of the task message queue pattern.
"""

import logging
from typing import Any

import anyio

from mcp.server.session import ServerSession
from mcp.shared.exceptions import MCPError
from mcp.shared.experimental.tasks.helpers import RELATED_TASK_METADATA_KEY, is_terminal
from mcp.shared.experimental.tasks.message_queue import TaskMessageQueue
from mcp.shared.experimental.tasks.resolver import Resolver
from mcp.shared.experimental.tasks.store import TaskStore
from mcp.shared.message import ServerMessageMetadata, SessionMessage
from mcp.types import (
    INVALID_PARAMS,
    ErrorData,
    GetTaskPayloadRequest,
    GetTaskPayloadResult,
    RelatedTaskMetadata,
    RequestId,
)

logger = logging.getLogger(__name__)


class TaskResultHandler:
    """Handler for tasks/result that implements the message queue pattern.

    This handler:
    1. Dequeues pending messages (elicitations, notifications) for the task
    2. Sends them to the client via the response stream
    3. Waits for responses and resolves them back to callers
    4. Blocks until task reaches terminal state
    5. Returns the final result

    Usage:
        async def handle_task_result(
            ctx: ServerRequestContext, params: GetTaskPayloadRequestParams
        ) -> GetTaskPayloadResult:
            ...

        server.experimental.enable_tasks(
            on_task_result=handle_task_result,
        )
    """

    def __init__(
        self,
        store: TaskStore,
        queue: TaskMessageQueue,
    ):
        self._store = store
        self._queue = queue
        # Map from internal request ID to resolver for routing responses
        self._pending_requests: dict[RequestId, Resolver[dict[str, Any]]] = {}

    async def send_message(
        self,
        session: ServerSession,
        message: SessionMessage,
    ) -> None:
        """Send a message via the session.

        This is a helper for delivering queued task messages.
        """
        pass

    async def handle(
        self,
        request: GetTaskPayloadRequest,
        session: ServerSession,
        request_id: RequestId,
    ) -> GetTaskPayloadResult:
        """Handle a tasks/result request.

        This implements the dequeue-send-wait loop:
        1. Dequeue all pending messages
        2. Send each via transport with relatedRequestId = this request's ID
        3. If task not terminal, wait for status change
        4. Loop until task is terminal
        5. Return final result

        Args:
            request: The GetTaskPayloadRequest
            session: The server session for sending messages
            request_id: The request ID for relatedRequestId routing

        Returns:
            GetTaskPayloadResult with the task's final payload
        """
        pass

    async def _deliver_queued_messages(
        self,
        task_id: str,
        session: ServerSession,
        request_id: RequestId,
    ) -> None:
        """Dequeue and send all pending messages for a task.

        Each message is sent via the session's write stream with
        relatedRequestId set so responses route back to this stream.
        """
        pass

    async def _wait_for_task_update(self, task_id: str) -> None:
        """Wait for task to be updated (status change or new message).

        Races between store update and queue message - first one wins.
        """
        pass

    def route_response(self, request_id: RequestId, response: dict[str, Any]) -> bool:
        """Route a response back to the waiting resolver.

        This is called when a response arrives for a queued request.

        Args:
            request_id: The request ID from the response
            response: The response data

        Returns:
            True if response was routed, False if no pending request
        """
        pass

    def route_error(self, request_id: RequestId, error: ErrorData) -> bool:
        """Route an error back to the waiting resolver.

        Args:
            request_id: The request ID from the error response
            error: The error data

        Returns:
            True if error was routed, False if no pending request
        """
        pass
