"""
Tests for the process utility module.

This module contains tests for the process detection functionality.
"""

import os
import sys
import subprocess
from typing import Generator
import pytest
import psutil

# Add the parent directory to the path so we can import the module under test
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import the module under test (this will fail until we create the module)
# from mover_status.utils.process import is_process_running, find_process_by_name


@pytest.fixture
def dummy_process() -> Generator[psutil.Process, None, None]:
    """
    Fixture that starts a dummy process for testing.

    Returns:
        Generator yielding a psutil.Process object representing the dummy process.
    """
    # Start a simple process that will run for a while
    if sys.platform == "win32":
        process = subprocess.Popen(["timeout", "/t", "10"], shell=True)
    else:
        process = subprocess.Popen(["sleep", "10"])

    # Get the process name for later use in tests
    proc = psutil.Process(process.pid)

    try:
        yield proc
    finally:
        # Make sure to terminate the process when done
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=1)


def test_is_process_running_with_existing_process(dummy_process: psutil.Process) -> None:
    """
    Test that is_process_running returns True for an existing process.

    Args:
        dummy_process: Fixture providing a running process.
    """
    from mover_status.utils.process import is_process_running

    # Test with PID
    assert is_process_running(dummy_process.pid) is True

    # Test with invalid PID
    assert is_process_running(999999) is False


def test_is_process_running_with_nonexistent_process() -> None:
    """Test that is_process_running returns False for a non-existent process."""
    from mover_status.utils.process import is_process_running

    # Find a PID that's not in use
    max_pid = 32768  # A reasonable upper limit for most systems
    test_pid = max_pid
    while test_pid > 0:
        if not psutil.pid_exists(test_pid):
            break
        test_pid -= 1

    # Test with non-existent PID
    assert is_process_running(test_pid) is False


def test_find_process_by_name_with_existing_process(dummy_process: psutil.Process) -> None:
    """
    Test that find_process_by_name returns a list containing the process when it exists.

    Args:
        dummy_process: Fixture providing a running process.
    """
    from mover_status.utils.process import find_process_by_name

    # Get the process name
    process_name = dummy_process.name()

    # Test finding the process by name
    processes = find_process_by_name(process_name)
    assert len(processes) >= 1

    # Verify our dummy process is in the list
    assert any(p.pid == dummy_process.pid for p in processes)


def test_find_process_by_name_with_nonexistent_process() -> None:
    """Test that find_process_by_name returns an empty list for a non-existent process."""
    from mover_status.utils.process import find_process_by_name

    # Test with a process name that's unlikely to exist
    processes = find_process_by_name("nonexistentprocessname123456789")
    assert len(processes) == 0
    assert isinstance(processes, list)


def test_find_process_by_name_case_insensitive(dummy_process: psutil.Process) -> None:
    """
    Test that find_process_by_name can find processes regardless of case.

    Args:
        dummy_process: Fixture providing a running process.
    """
    from mover_status.utils.process import find_process_by_name

    # Get the process name and convert to uppercase
    process_name = dummy_process.name().upper()

    # Test finding the process by name with case_sensitive=False (default)
    processes = find_process_by_name(process_name)
    assert len(processes) >= 1
    assert any(p.pid == dummy_process.pid for p in processes)

    # Test with case_sensitive=True (should not find the process if name is different case)
    if process_name != dummy_process.name():  # Only test if the name actually has different case
        processes = find_process_by_name(process_name, case_sensitive=True)
        assert not any(p.pid == dummy_process.pid for p in processes)
