from __future__ import annotations

import contextvars
import logging
from collections.abc import Callable
from contextlib import AsyncExitStack
from types import TracebackType
from typing import Any, Generic, Protocol, TypeVar

import anyio
from anyio.streams.memory import MemoryObjectSendStream
from opentelemetry.trace import SpanKind
from pydantic import BaseModel, TypeAdapter
from typing_extensions import Self

from mcp.shared._otel import inject_trace_context, otel_span
from mcp.shared._stream_protocols import ReadStream, WriteStream
from mcp.shared.exceptions import MCPError
from mcp.shared.message import MessageMetadata, ServerMessageMetadata, SessionMessage
from mcp.shared.response_router import ResponseRouter
from mcp.types import (
    CONNECTION_CLOSED,
    INVALID_PARAMS,
    REQUEST_TIMEOUT,
    CancelledNotification,
    ClientNotification,
    ClientRequest,
    ClientResult,
    ErrorData,
    JSONRPCError,
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    ProgressNotification,
    ProgressToken,
    RequestParamsMeta,
    ServerNotification,
    ServerRequest,
    ServerResult,
)

SendRequestT = TypeVar("SendRequestT", ClientRequest, ServerRequest)
SendResultT = TypeVar("SendResultT", ClientResult, ServerResult)
SendNotificationT = TypeVar("SendNotificationT", ClientNotification, ServerNotification)
ReceiveRequestT = TypeVar("ReceiveRequestT", ClientRequest, ServerRequest)
ReceiveResultT = TypeVar("ReceiveResultT", bound=BaseModel)
ReceiveNotificationT = TypeVar("ReceiveNotificationT", ClientNotification, ServerNotification)

RequestId = str | int


class ProgressFnT(Protocol):
    """Protocol for progress notification callbacks."""

    async def __call__(
        self, progress: float, total: float | None, message: str | None
    ) -> None: ...  # pragma: no branch


class RequestResponder(Generic[ReceiveRequestT, SendResultT]):
    """Handles responding to MCP requests and manages request lifecycle.

    This class MUST be used as a context manager to ensure proper cleanup and
    cancellation handling:

    Example:
        ```python
        with request_responder as resp:
            await resp.respond(result)
        ```

    The context manager ensures:
    1. Proper cancellation scope setup and cleanup
    2. Request completion tracking
    3. Cleanup of in-flight requests
    """

    def __init__(
        self,
        request_id: RequestId,
        request_meta: RequestParamsMeta | None,
        request: ReceiveRequestT,
        session: BaseSession[SendRequestT, SendNotificationT, SendResultT, ReceiveRequestT, ReceiveNotificationT],
        on_complete: Callable[[RequestResponder[ReceiveRequestT, SendResultT]], Any],
        message_metadata: MessageMetadata = None,
        context: contextvars.Context | None = None,
    ) -> None:
        self.request_id = request_id
        self.request_meta = request_meta
        self.request = request
        self.message_metadata = message_metadata
        self.context = context
        self._session = session
        self._completed = False
        self._cancel_scope = anyio.CancelScope()
        self._on_complete = on_complete
        self._entered = False  # Track if we're in a context manager

    def __enter__(self) -> RequestResponder[ReceiveRequestT, SendResultT]:
        """Enter the context manager, enabling request cancellation tracking."""
        self._entered = True
        self._cancel_scope = anyio.CancelScope()
        self._cancel_scope.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context manager, performing cleanup and notifying completion."""
        try:
            if self._completed:
                self._on_complete(self)
        finally:
            self._entered = False
            if not self._cancel_scope:  # pragma: no cover
                raise RuntimeError("No active cancel scope")
            self._cancel_scope.__exit__(exc_type, exc_val, exc_tb)

    async def respond(self, response: SendResultT | ErrorData) -> None:
        """Send a response for this request.

        Must be called within a context manager block.

        Raises:
            RuntimeError: If not used within a context manager
            AssertionError: If request was already responded to
        """
        pass

    async def cancel(self) -> None:
        """Cancel this request and mark it as completed."""
        if not self._entered:  # pragma: no cover
            raise RuntimeError("RequestResponder must be used as a context manager")
        if not self._cancel_scope:  # pragma: no cover
            raise RuntimeError("No active cancel scope")

        self._cancel_scope.cancel()
        self._completed = True  # Mark as completed so it's removed from in_flight
        # Send an error response to indicate cancellation
        await self._session._send_response(  # type: ignore[reportPrivateUsage]
            request_id=self.request_id,
            response=ErrorData(code=0, message="Request cancelled"),
        )

    @property
    def in_flight(self) -> bool:  # pragma: no cover
        pass

    @property
    def cancelled(self) -> bool:
        pass


class BaseSession(
    Generic[
        SendRequestT,
        SendNotificationT,
        SendResultT,
        ReceiveRequestT,
        ReceiveNotificationT,
    ],
):
    """Implements an MCP "session" on top of read/write streams, including features
    like request/response linking, notifications, and progress.

    This class is an async context manager that automatically starts processing
    messages when entered.
    """

    _response_streams: dict[RequestId, MemoryObjectSendStream[JSONRPCResponse | JSONRPCError]]
    _request_id: int
    _in_flight: dict[RequestId, RequestResponder[ReceiveRequestT, SendResultT]]
    _progress_callbacks: dict[RequestId, ProgressFnT]
    _response_routers: list[ResponseRouter]

    def __init__(
        self,
        read_stream: ReadStream[SessionMessage | Exception],
        write_stream: WriteStream[SessionMessage],
        # If none, reading will never time out
        read_timeout_seconds: float | None = None,
    ) -> None:
        self._read_stream = read_stream
        self._write_stream = write_stream
        self._response_streams = {}
        self._request_id = 0
        self._session_read_timeout_seconds = read_timeout_seconds
        self._in_flight = {}
        self._progress_callbacks = {}
        self._response_routers = []
        self._exit_stack = AsyncExitStack()

    def add_response_router(self, router: ResponseRouter) -> None:
        """Register a response router to handle responses for non-standard requests.

        Response routers are checked in order before falling back to the default
        response stream mechanism. This is used by TaskResultHandler to route
        responses for queued task requests back to their resolvers.

        !!! warning
            This is an experimental API that may change without notice.

        Args:
            router: A ResponseRouter implementation
        """
        self._response_routers.append(router)

    async def __aenter__(self) -> Self:
        self._task_group = anyio.create_task_group()
        await self._task_group.__aenter__()
        self._task_group.start_soon(self._receive_loop)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        await self._exit_stack.aclose()
        # Using BaseSession as a context manager should not block on exit (this
        # would be very surprising behavior), so make sure to cancel the tasks
        # in the task group.
        self._task_group.cancel_scope.cancel()
        return await self._task_group.__aexit__(exc_type, exc_val, exc_tb)

    async def send_request(
        self,
        request: SendRequestT,
        result_type: type[ReceiveResultT],
        request_read_timeout_seconds: float | None = None,
        metadata: MessageMetadata = None,
        progress_callback: ProgressFnT | None = None,
    ) -> ReceiveResultT:
        """Sends a request and waits for a response.

        Raises an MCPError if the response contains an error. If a request read timeout is provided, it will take
        precedence over the session read timeout.

        Do not use this method to emit notifications! Use send_notification() instead.
        """
        request_id = self._request_id
        self._request_id = request_id + 1

        response_stream, response_stream_reader = anyio.create_memory_object_stream[JSONRPCResponse | JSONRPCError](1)
        self._response_streams[request_id] = response_stream

        # Set up progress token if progress callback is provided
        request_data = request.model_dump(by_alias=True, mode="json", exclude_none=True)
        if progress_callback is not None:
            # Use request_id as progress token
            if "params" not in request_data:  # pragma: lax no cover
                request_data["params"] = {}
            if "_meta" not in request_data["params"]:  # pragma: lax no cover
                request_data["params"]["_meta"] = {}
            request_data["params"]["_meta"]["progressToken"] = request_id
            # Store the callback for this request
            self._progress_callbacks[request_id] = progress_callback

        try:
            target = request_data.get("params", {}).get("name")
            span_name = f"MCP send {request.method} {target}" if target else f"MCP send {request.method}"

            with otel_span(
                span_name,
                kind=SpanKind.CLIENT,
                attributes={"mcp.method.name": request.method, "jsonrpc.request.id": request_id},
            ):
                # Inject W3C trace context into _meta (SEP-414).
                meta: dict[str, Any] = request_data.setdefault("params", {}).setdefault("_meta", {})
                inject_trace_context(meta)

                jsonrpc_request = JSONRPCRequest(jsonrpc="2.0", id=request_id, **request_data)
                await self._write_stream.send(SessionMessage(message=jsonrpc_request, metadata=metadata))

                # request read timeout takes precedence over session read timeout
                timeout = request_read_timeout_seconds or self._session_read_timeout_seconds

                try:
                    with anyio.fail_after(timeout):
                        response_or_error = await response_stream_reader.receive()
                except TimeoutError:
                    class_name = request.__class__.__name__
                    message = f"Timed out while waiting for response to {class_name}. Waited {timeout} seconds."
                    raise MCPError(code=REQUEST_TIMEOUT, message=message)

                if isinstance(response_or_error, JSONRPCError):
                    raise MCPError.from_jsonrpc_error(response_or_error)
                else:
                    return result_type.model_validate(response_or_error.result, by_name=False)

        finally:
            self._response_streams.pop(request_id, None)
            self._progress_callbacks.pop(request_id, None)
            await response_stream.aclose()
            await response_stream_reader.aclose()

    async def send_notification(
        self,
        notification: SendNotificationT,
        related_request_id: RequestId | None = None,
    ) -> None:
        """Emits a notification, which is a one-way message that does not expect a response."""
        # Some transport implementations may need to set the related_request_id
        # to attribute to the notifications to the request that triggered them.
        jsonrpc_notification = JSONRPCNotification(
            jsonrpc="2.0",
            **notification.model_dump(by_alias=True, mode="json", exclude_none=True),
        )
        session_message = SessionMessage(
            message=jsonrpc_notification,
            metadata=ServerMessageMetadata(related_request_id=related_request_id) if related_request_id else None,
        )
        await self._write_stream.send(session_message)

    async def _send_response(self, request_id: RequestId, response: SendResultT | ErrorData) -> None:
        if isinstance(response, ErrorData):
            jsonrpc_error = JSONRPCError(jsonrpc="2.0", id=request_id, error=response)
            session_message = SessionMessage(message=jsonrpc_error)
            await self._write_stream.send(session_message)
        else:
            jsonrpc_response = JSONRPCResponse(
                jsonrpc="2.0",
                id=request_id,
                result=response.model_dump(by_alias=True, mode="json", exclude_none=True),
            )
            session_message = SessionMessage(message=jsonrpc_response)
            await self._write_stream.send(session_message)

    @property
    def _receive_request_adapter(self) -> TypeAdapter[ReceiveRequestT]:
        """Each subclass must provide its own request adapter."""
        raise NotImplementedError

    @property
    def _receive_notification_adapter(self) -> TypeAdapter[ReceiveNotificationT]:
        raise NotImplementedError

    async def _receive_loop(self) -> None:
        pass

    def _normalize_request_id(self, response_id: RequestId) -> RequestId:
        """Normalize a response ID to match how request IDs are stored.

        Since the client always sends integer IDs, we normalize string IDs
        to integers when possible. This matches the TypeScript SDK approach:
        https://github.com/modelcontextprotocol/typescript-sdk/blob/a606fb17909ea454e83aab14c73f14ea45c04448/src/shared/protocol.ts#L861

        Args:
            response_id: The response ID from the incoming message.

        Returns:
            The normalized ID (int if possible, otherwise original value).
        """
        pass

    async def _handle_response(self, message: SessionMessage) -> None:
        """Handle an incoming response or error message.

        Checks response routers first (e.g., for task-related responses),
        then falls back to the normal response stream mechanism.
        """
        pass

    async def _received_request(self, responder: RequestResponder[ReceiveRequestT, SendResultT]) -> None:
        """Can be overridden by subclasses to handle a request without needing to
        listen on the message stream.

        If the request is responded to within this method, it will not be
        forwarded on to the message stream.
        """

    async def _received_notification(self, notification: ReceiveNotificationT) -> None:
        """Can be overridden by subclasses to handle a notification without needing
        to listen on the message stream.
        """

    async def send_progress_notification(
        self,
        progress_token: ProgressToken,
        progress: float,
        total: float | None = None,
        message: str | None = None,
    ) -> None:
        """Sends a progress notification for a request that is currently being processed."""

    async def _handle_incoming(
        self, req: RequestResponder[ReceiveRequestT, SendResultT] | ReceiveNotificationT | Exception
    ) -> None:
        """A generic handler for incoming messages. Overridden by subclasses."""
