"""
Process utility module.

This module provides utilities for detecting and interacting with system processes.
It is used primarily for monitoring the mover process in Unraid systems.
"""

from typing import List
import psutil


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


def find_process_by_name(name: str, case_sensitive: bool = False) -> List[psutil.Process]:
    """
    Find all processes with the given name.

    Args:
        name: The name of the process to find.
        case_sensitive: Whether to perform a case-sensitive search. Defaults to False.

    Returns:
        List[psutil.Process]: A list of Process objects matching the name.
        Returns an empty list if no matching processes are found.
    """
    matching_processes: List[psutil.Process] = []

    for process in psutil.process_iter(['pid', 'name']):
        try:
            process_name = process.info['name']

            # Compare names based on case sensitivity setting
            if case_sensitive:
                if process_name == name:
                    matching_processes.append(process)
            else:
                if process_name.lower() == name.lower():
                    matching_processes.append(process)

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # Skip processes that can't be accessed or no longer exist
            continue

    return matching_processes
