"""
Basic test to verify that the testing setup works.
"""

import os
import sys


def test_python_version() -> None:
    """Test that we're running on Python 3.13 or higher."""
    major, minor = sys.version_info[:2]
    assert major == 3
    assert minor >= 13, "Python version should be 3.13 or higher"


def test_package_structure() -> None:
    """Test that the package structure is correct."""
    # Check that the main package directory exists
    assert os.path.isdir("mover_status"), "Main package directory should exist"

    # Check that the main package __init__.py exists
    assert os.path.isfile("mover_status/__init__.py"), "Main package __init__.py should exist"

    # Check that the main package subdirectories exist
    subdirs = ["config", "core", "notification", "utils"]
    for subdir in subdirs:
        assert os.path.isdir(f"mover_status/{subdir}"), f"Subdirectory {subdir} should exist"
        assert os.path.isfile(f"mover_status/{subdir}/__init__.py"), f"Subdirectory {subdir}/__init__.py should exist"


def test_fixtures(temp_dir: str, temp_file: str, sample_config: dict[str, object]) -> None:
    """Test that the fixtures work."""
    # Test temp_dir fixture
    assert os.path.isdir(temp_dir), "Temporary directory should exist"

    # Test temp_file fixture
    assert os.path.isfile(temp_file), "Temporary file should exist"

    # Test sample_config fixture
    assert isinstance(sample_config, dict), "Sample config should be a dictionary"
    assert "notification" in sample_config, "Sample config should have notification key"
    assert "monitoring" in sample_config, "Sample config should have monitoring key"
    assert "debug" in sample_config, "Sample config should have debug key"
