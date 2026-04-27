"""Claude app integration utilities."""

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from mcp.server.mcpserver.utilities.logging import get_logger

logger = get_logger(__name__)

MCP_PACKAGE = "mcp[cli]"


def get_claude_config_path() -> Path | None:  # pragma: no cover
    """Get the Claude config directory based on platform."""
    pass


def get_uv_path() -> str:
    """Get the full path to the uv executable."""
    pass


def update_claude_config(
    file_spec: str,
    server_name: str,
    *,
    with_editable: Path | None = None,
    with_packages: list[str] | None = None,
    env_vars: dict[str, str] | None = None,
) -> bool:
    """Add or update an MCP server in Claude's configuration.

    Args:
        file_spec: Path to the server file, optionally with :object suffix
        server_name: Name for the server in Claude's config
        with_editable: Optional directory to install in editable mode
        with_packages: Optional list of additional packages to install
        env_vars: Optional dictionary of environment variables. These are merged with
            any existing variables, with new values taking precedence.

    Raises:
        RuntimeError: If Claude Desktop's config directory is not found, indicating
            Claude Desktop may not be installed or properly set up.
    """
    pass
