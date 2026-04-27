"""Shared validation functions for server requests.

This module provides validation logic for sampling and elicitation requests
that is shared across normal and task-augmented code paths.
"""

from mcp.shared.exceptions import MCPError
from mcp.types import INVALID_PARAMS, ClientCapabilities, SamplingMessage, Tool, ToolChoice


def check_sampling_tools_capability(client_caps: ClientCapabilities | None) -> bool:
    """Check if the client supports sampling tools capability.

    Args:
        client_caps: The client's declared capabilities

    Returns:
        True if client supports sampling.tools, False otherwise
    """
    pass


def validate_sampling_tools(
    client_caps: ClientCapabilities | None,
    tools: list[Tool] | None,
    tool_choice: ToolChoice | None,
) -> None:
    """Validate that the client supports sampling tools if tools are being used.

    Args:
        client_caps: The client's declared capabilities
        tools: The tools list, if provided
        tool_choice: The tool choice setting, if provided

    Raises:
        MCPError: If tools/tool_choice are provided but client doesn't support them
    """
    pass


def validate_tool_use_result_messages(messages: list[SamplingMessage]) -> None:
    """Validate tool_use/tool_result message structure per SEP-1577.

    This validation ensures:
    1. Messages with tool_result content contain ONLY tool_result content
    2. tool_result messages are preceded by a message with tool_use
    3. tool_result IDs match the tool_use IDs from the previous message

    See: https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1577

    Args:
        messages: The list of sampling messages to validate

    Raises:
        ValueError: If the message structure is invalid
    """
    pass
