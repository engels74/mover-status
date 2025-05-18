"""
Tests for the data utility module.

This module contains tests for the directory size calculation functionality.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Generator, List, Optional
import pytest
from unittest.mock import patch, MagicMock

# Add the parent directory to the path so we can import the module under test
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


@pytest.fixture
def temp_directory() -> Generator[Path, None, None]:
    """
    Fixture that creates a temporary directory for testing.

    Returns:
        Generator yielding a Path object representing the temporary directory.
    """
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    temp_path = Path(temp_dir)

    try:
        yield temp_path
    finally:
        # Clean up after test
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def populated_directory(temp_directory: Path) -> Generator[Path, None, None]:
    """
    Fixture that creates a temporary directory with files and subdirectories.

    Args:
        temp_directory: Fixture providing a temporary directory.

    Returns:
        Generator yielding a Path object representing the populated directory.
    """
    # Create some files with known sizes
    (temp_directory / "file1.txt").write_bytes(b"X" * 1000)  # 1 KB
    (temp_directory / "file2.txt").write_bytes(b"X" * 2000)  # 2 KB

    # Create a subdirectory with files
    subdir = temp_directory / "subdir"
    subdir.mkdir()
    (subdir / "file3.txt").write_bytes(b"X" * 3000)  # 3 KB

    # Create a subdirectory to be excluded
    exclude_dir = temp_directory / "exclude_me"
    exclude_dir.mkdir()
    (exclude_dir / "file4.txt").write_bytes(b"X" * 4000)  # 4 KB

    yield temp_directory


def test_get_directory_size_with_existing_directory(populated_directory: Path) -> None:
    """
    Test that get_directory_size returns the correct size for an existing directory.

    Args:
        populated_directory: Fixture providing a directory with files.
    """
    from mover_status.utils.data import get_directory_size

    # Calculate expected size: 1KB + 2KB + 3KB + 4KB = 10KB
    expected_size = 1000 + 2000 + 3000 + 4000

    # Test with Path object
    size = get_directory_size(populated_directory)
    assert size == expected_size

    # Test with string path
    size = get_directory_size(str(populated_directory))
    assert size == expected_size


def test_get_directory_size_with_exclusions(populated_directory: Path) -> None:
    """
    Test that get_directory_size correctly handles exclusions.

    Args:
        populated_directory: Fixture providing a directory with files.
    """
    from mover_status.utils.data import get_directory_size

    # Exclude the 'exclude_me' directory (4KB)
    exclusions = [str(populated_directory / "exclude_me")]

    # Expected size: 1KB + 2KB + 3KB = 6KB
    expected_size = 1000 + 2000 + 3000

    size = get_directory_size(populated_directory, exclusions)
    assert size == expected_size

    # Test with multiple exclusions
    exclusions = [
        str(populated_directory / "exclude_me"),
        str(populated_directory / "subdir"),
    ]

    # Expected size: 1KB + 2KB = 3KB
    expected_size = 1000 + 2000

    size = get_directory_size(populated_directory, exclusions)
    assert size == expected_size


def test_get_directory_size_with_nonexistent_directory() -> None:
    """Test that get_directory_size raises an error for a non-existent directory."""
    from mover_status.utils.data import get_directory_size

    with pytest.raises(FileNotFoundError):
        get_directory_size("/path/that/does/not/exist")


def test_get_directory_size_with_nonexistent_exclusion(populated_directory: Path) -> None:
    """
    Test that get_directory_size handles non-existent exclusion paths gracefully.

    Args:
        populated_directory: Fixture providing a directory with files.
    """
    from mover_status.utils.data import get_directory_size

    # Include a non-existent exclusion path
    exclusions = [
        str(populated_directory / "exclude_me"),
        str(populated_directory / "does_not_exist"),
    ]

    # Expected size: 1KB + 2KB + 3KB = 6KB (excluding only the existing exclusion)
    expected_size = 1000 + 2000 + 3000

    # Should log a warning but continue with valid exclusions
    with pytest.warns(UserWarning, match="Exclusion path .* does not exist"):
        size = get_directory_size(populated_directory, exclusions)
        assert size == expected_size


@patch("subprocess.run")
def test_get_directory_size_subprocess_error(mock_run: MagicMock, populated_directory: Path) -> None:
    """
    Test that get_directory_size handles subprocess errors gracefully.

    Args:
        mock_run: Mock for subprocess.run.
        populated_directory: Fixture providing a directory with files.
    """
    from mover_status.utils.data import get_directory_size
    import subprocess

    # Mock subprocess.run to raise an exception
    mock_run.side_effect = subprocess.SubprocessError("Command failed")

    with pytest.raises(RuntimeError, match="Failed to calculate directory size"):
        get_directory_size(populated_directory)


def test_format_exclusions_empty_list() -> None:
    """Test that format_exclusions returns an empty list when given an empty list."""
    from mover_status.utils.data import format_exclusions

    exclusions: List[str] = []
    result = format_exclusions(exclusions)
    assert result == []


def test_format_exclusions_with_valid_paths(populated_directory: Path) -> None:
    """
    Test that format_exclusions correctly formats exclusion paths.

    Args:
        populated_directory: Fixture providing a directory with files.
    """
    from mover_status.utils.data import format_exclusions

    exclusions = [
        str(populated_directory / "exclude_me"),
        str(populated_directory / "subdir"),
    ]

    result = format_exclusions(exclusions)
    assert len(result) == 2
    assert result[0] == f"--exclude={exclusions[0]}"
    assert result[1] == f"--exclude={exclusions[1]}"


def test_format_exclusions_with_nonexistent_paths(populated_directory: Path) -> None:
    """
    Test that format_exclusions handles non-existent paths correctly.

    Args:
        populated_directory: Fixture providing a directory with files.
    """
    from mover_status.utils.data import format_exclusions

    exclusions = [
        str(populated_directory / "exclude_me"),  # Exists
        str(populated_directory / "does_not_exist"),  # Doesn't exist
    ]

    # Should warn about non-existent path and exclude it from result
    with pytest.warns(UserWarning, match="Exclusion path .* does not exist"):
        result = format_exclusions(exclusions)
        assert len(result) == 1
        assert result[0] == f"--exclude={exclusions[0]}"
