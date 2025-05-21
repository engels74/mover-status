"""
Process utility module.

This module provides utilities for detecting and interacting with system processes.
It is used primarily for monitoring the mover process in Unraid systems.
"""

import os
import psutil
import logging
from typing import cast

# Get logger for this module
logger = logging.getLogger(__name__)


def is_process_running(pid: int) -> bool:
    """
    Check if a process with the given PID is running.

    Args:
        pid: The process ID to check.

    Returns:
        bool: True if the process is running, False otherwise.
    """
    try:
        # Check if the process exists and is running
        process = psutil.Process(pid)
        return process.is_running()
    except psutil.NoSuchProcess:
        return False


def find_process_by_name(name: str, case_sensitive: bool = False) -> list[psutil.Process]:
    """
    Find all processes with the given name.

    Args:
        name: The name of the process to find.
        case_sensitive: Whether to perform a case-sensitive search. Defaults to False.

    Returns:
        list[psutil.Process]: A list of Process objects matching the name.
        Returns an empty list if no matching processes are found.
    """
    matching_processes: list[psutil.Process] = []

    for process in psutil.process_iter(['pid', 'name'], ad_value=None):  # pyright: ignore[reportUnknownMemberType]
        try:
            process_name = cast(str, process.info['name'])

            # Compare names based on case sensitivity setting
            if case_sensitive:
                if process_name == name:
                    matching_processes.append(process)
            else:
                lower_process_name = process_name.lower()
                if lower_process_name == name.lower():
                    matching_processes.append(process)

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # Skip processes that can't be accessed or no longer exist
            continue

    return matching_processes


def find_mover_process(mover_path: str = "/usr/local/sbin/mover") -> list[psutil.Process]:
    """
    Find the mover process based on the executable path.

    This function is specifically designed to detect the Unraid mover process,
    with special handling for containerized environments where process paths
    might be different between host and container.

    Args:
        mover_path: Path to the mover executable. Defaults to "/usr/local/sbin/mover".

    Returns:
        list[psutil.Process]: A list of Process objects representing mover processes.
        Returns an empty list if no mover processes are found.
    """
    # Extract just the executable name from the path
    mover_name = os.path.basename(mover_path)

    # Try to find by exact executable path first (more reliable in container with --pid=host)
    processes: list[psutil.Process] = []

    for proc in psutil.process_iter(['pid', 'name', 'exe'], ad_value=None):  # pyright: ignore[reportUnknownMemberType]
        try:
            # Check if the process executable matches the mover path
            if 'exe' in proc.info and proc.info['exe'] == mover_path:
                processes.append(proc)
                logger.debug(f"Found mover process by exact path: PID {proc.pid}")
            # Also check by name as a fallback
            elif 'name' in proc.info and proc.info['name'] == mover_name:
                processes.append(proc)
                logger.debug(f"Found mover process by name: PID {proc.pid}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            logger.debug(f"Error accessing process: {e}")
            continue

    # If no processes found by direct checks, fall back to name-based search
    if not processes:
        logger.debug("No mover processes found by direct checks, falling back to name search")
        processes = find_process_by_name(mover_name)

    return processes


def is_mover_running(mover_path: str = "/usr/local/sbin/mover") -> bool:
    """
    Check if the mover process is running.

    Args:
        mover_path: Path to the mover executable. Defaults to "/usr/local/sbin/mover".

    Returns:
        bool: True if at least one mover process is running, False otherwise.
    """
    processes = find_mover_process(mover_path)
    return len(processes) > 0
