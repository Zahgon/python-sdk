"""Tasks capability checking utilities.

This module provides functions for checking and requiring task-related
capabilities. All tasks capability logic is centralized here to keep
the main session code clean.

WARNING: These APIs are experimental and may change without notice.
"""

from mcp.shared.exceptions import MCPError
from mcp.types import INVALID_REQUEST, ClientCapabilities, ClientTasksCapability


def check_tasks_capability(
    required: ClientTasksCapability,
    client: ClientTasksCapability,
) -> bool:
    """Check if client's tasks capability matches the required capability.

    Args:
        required: The capability being checked for
        client: The client's declared capabilities

    Returns:
        True if client has the required capability, False otherwise
    """
    if required.requests is None:
        return True
    if client.requests is None:
        return False

    # Check elicitation.create
    if required.requests.elicitation is not None:
        if client.requests.elicitation is None:
            return False
        if required.requests.elicitation.create is not None:
            if client.requests.elicitation.create is None:
                return False

    # Check sampling.createMessage
    if required.requests.sampling is not None:
        if client.requests.sampling is None:
            return False
        if required.requests.sampling.create_message is not None:
            if client.requests.sampling.create_message is None:
                return False

    return True


def has_task_augmented_elicitation(caps: ClientCapabilities) -> bool:
    """Check if capabilities include task-augmented elicitation support."""
    pass


def has_task_augmented_sampling(caps: ClientCapabilities) -> bool:
    """Check if capabilities include task-augmented sampling support."""
    pass


def require_task_augmented_elicitation(client_caps: ClientCapabilities | None) -> None:
    """Raise MCPError if client doesn't support task-augmented elicitation.

    Args:
        client_caps: The client's declared capabilities, or None if not initialized

    Raises:
        MCPError: If client doesn't support task-augmented elicitation
    """
    pass


def require_task_augmented_sampling(client_caps: ClientCapabilities | None) -> None:
    """Raise MCPError if client doesn't support task-augmented sampling.

    Args:
        client_caps: The client's declared capabilities, or None if not initialized

    Raises:
        MCPError: If client doesn't support task-augmented sampling
    """
    pass
