"""POSIX-specific functionality for stdio client operations."""

import logging
import os
import signal

import anyio
from anyio.abc import Process

logger = logging.getLogger(__name__)


async def terminate_posix_process_tree(process: Process, timeout_seconds: float = 2.0) -> None:
    """Terminate a process and all its children on POSIX systems.

    Uses os.killpg() for atomic process group termination.

    Args:
        process: The process to terminate
        timeout_seconds: Timeout in seconds before force killing (default: 2.0)
    """
    pass
