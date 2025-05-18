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


def test_find_process_by_name_case_sensitive() -> None:
    """Test the case-sensitive branch of find_process_by_name."""
    from mover_status.utils.process import find_process_by_name

    # Mock a process with an exact name match
    mock_process = MagicMock()
    mock_process.info = {'name': 'ExactName', 'pid': 12345}

    with patch('psutil.process_iter', return_value=[mock_process]):
        # Test with case_sensitive=True and exact match
        processes = find_process_by_name('ExactName', case_sensitive=True)
        assert len(processes) == 1

        # Test with case_sensitive=True and different case (should not match)
        processes = find_process_by_name('exactname', case_sensitive=True)
        assert len(processes) == 0


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


def test_find_process_by_name_exception_handling() -> None:
    """Test that find_process_by_name handles exceptions during process iteration."""
    from mover_status.utils.process import find_process_by_name

    # Create a mock process that raises exceptions
    mock_process = MagicMock()
    mock_process.info = {'name': 'test_process'}

    # First process raises NoSuchProcess
    mock_process_no_such = MagicMock()
    mock_process_no_such.info.__getitem__.side_effect = psutil.NoSuchProcess(pid=1234)

    # Second process raises AccessDenied
    mock_process_access_denied = MagicMock()
    mock_process_access_denied.info.__getitem__.side_effect = psutil.AccessDenied()

    # Third process raises ZombieProcess
    mock_process_zombie = MagicMock()
    mock_process_zombie.info.__getitem__.side_effect = psutil.ZombieProcess(pid=5678)

    # Set up process_iter to return our mock processes
    with patch('psutil.process_iter', return_value=[
            mock_process_no_such,
            mock_process_access_denied,
            mock_process_zombie,
            mock_process
        ]):

        # Call the function - it should handle the exceptions and return the valid process
        processes = find_process_by_name('test_process')

        # Verify the results
        assert len(processes) == 1
        assert processes[0] == mock_process


@patch('mover_status.utils.process.logger')
def test_find_process_by_name_with_exception(_: MagicMock) -> None:
    """Test that find_process_by_name handles exceptions during process iteration."""
    from mover_status.utils.process import find_process_by_name

    # Create a mock process that raises an exception
    mock_process = MagicMock()
    mock_process.info.__getitem__.side_effect = psutil.NoSuchProcess(pid=1234)

    # Set up process_iter to return our mock process
    with patch('psutil.process_iter', return_value=[mock_process]):
        # Call the function - it should handle the exception
        processes = find_process_by_name("test_process")

        # Verify the results - should be an empty list since all processes failed
        assert len(processes) == 0


@patch('mover_status.utils.process.logger')
def test_find_mover_process_with_exception(mock_logger: MagicMock) -> None:
    """Test that find_mover_process handles exceptions during process iteration."""
    from mover_status.utils.process import find_mover_process
    from typing import Any

    # Create a mock process that raises an exception when accessing 'exe'
    mock_process = MagicMock()

    # Set up the mock to raise an exception when accessing 'exe' but return a valid name
    def mock_getitem(key: str) -> Any:
        if key == 'exe':
            raise psutil.NoSuchProcess(pid=1234)
        elif key == 'name':
            return 'mover'  # This will make the name check pass
        return None

    mock_process.info.__getitem__.side_effect = mock_getitem

    # Define a proper __contains__ method
    def mock_contains(_: Any, key: str) -> bool:  # pyright:ignore
        return key in ('name', 'exe')

    # Assign the method
    mock_process.info.__contains__ = mock_contains
    mock_process.pid = 1234

    # Set up process_iter to return our mock process
    with patch('psutil.process_iter', return_value=[mock_process]):
        # Mock find_process_by_name to return an empty list (to ensure we're testing the exception path)
        with patch('mover_status.utils.process.find_process_by_name', return_value=[]):
            # Call the function - it should handle the exception
            processes = find_mover_process()

            # Verify the results - should be an empty list since all processes failed
            assert len(processes) == 0

            # Verify that the logger was called with the error message
            mock_logger.debug.assert_any_call(f"Error accessing process: {psutil.NoSuchProcess(pid=1234)}")

            # Verify that the fallback message was logged
            mock_logger.debug.assert_any_call("No mover processes found by direct checks, falling back to name search")
