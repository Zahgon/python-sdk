"""Logging utilities for MCPServer."""

import logging
from typing import Literal


def get_logger(name: str) -> logging.Logger:
    """Get a logger nested under MCP namespace.

    Args:
        name: The name of the logger.

    Returns:
        A configured logger instance.
    """
    return logging.getLogger(name)


def configure_logging(
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
) -> None:
    """Configure logging for MCP.

    Args:
        level: The log level to use.
    """
    pass
