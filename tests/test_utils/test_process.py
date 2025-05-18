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
from unittest.mock import patch, MagicMock

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


@patch('psutil.process_iter')
def test_find_mover_process_by_exact_path(mock_process_iter: MagicMock) -> None:
    """Test finding mover process by exact executable path."""
    from mover_status.utils.process import find_mover_process

    # Create a mock process that matches the mover path
    mock_process = MagicMock()
    mock_process.info = {'pid': 12345, 'name': 'mover', 'exe': '/usr/local/sbin/mover'}
    mock_process.pid = 12345

    # Set up the mock to return our mock process
    mock_process_iter.return_value = [mock_process]

    # Call the function
    processes = find_mover_process()

    # Verify the results
    assert len(processes) == 1
    assert processes[0].pid == 12345


@patch('psutil.process_iter')
def test_find_mover_process_by_name(mock_process_iter: MagicMock) -> None:
    """Test finding mover process by name when exe doesn't match."""
    from mover_status.utils.process import find_mover_process

    # Create a mock process that matches the mover name but has a different exe path
    mock_process = MagicMock()
    mock_process.info = {'pid': 12345, 'name': 'mover', 'exe': '/some/other/path'}
    mock_process.pid = 12345

    # Set up the mock to return our mock process
    mock_process_iter.return_value = [mock_process]

    # Call the function
    processes = find_mover_process()

    # Verify the results
    assert len(processes) == 1
    assert processes[0].pid == 12345


@patch('psutil.process_iter')
@patch('mover_status.utils.process.find_process_by_name')
def test_find_mover_process_fallback(mock_find_by_name: MagicMock, mock_process_iter: MagicMock) -> None:
    """Test fallback to find_process_by_name when no processes found by direct checks."""
    from mover_status.utils.process import find_mover_process

    # Set up process_iter to return no matching processes
    mock_process = MagicMock()
    mock_process.info = {'pid': 12345, 'name': 'not_mover', 'exe': '/not/mover/path'}
    mock_process_iter.return_value = [mock_process]

    # Set up find_process_by_name to return a mock process
    mock_result_process = MagicMock()
    mock_result_process.pid = 54321
    mock_find_by_name.return_value = [mock_result_process]

    # Call the function
    processes = find_mover_process()

    # Verify the results
    assert len(processes) == 1
    assert processes[0].pid == 54321
    mock_find_by_name.assert_called_once_with('mover')


@patch('mover_status.utils.process.find_mover_process')
def test_is_mover_running_true(mock_find_mover: MagicMock) -> None:
    """Test is_mover_running returns True when processes are found."""
    from mover_status.utils.process import is_mover_running

    # Set up find_mover_process to return a mock process
    mock_process = MagicMock()
    mock_find_mover.return_value = [mock_process]

    # Call the function
    result = is_mover_running()

    # Verify the result
    assert result is True
    mock_find_mover.assert_called_once_with('/usr/local/sbin/mover')


@patch('mover_status.utils.process.find_mover_process')
def test_is_mover_running_false(mock_find_mover: MagicMock) -> None:
    """Test is_mover_running returns False when no processes are found."""
    from mover_status.utils.process import is_mover_running

    # Set up find_mover_process to return an empty list
    mock_find_mover.return_value = []

    # Call the function
    result = is_mover_running()

    # Verify the result
    assert result is False
    mock_find_mover.assert_called_once_with('/usr/local/sbin/mover')
