"""Pytest configuration and shared fixtures."""

from __future__ import annotations

# TODO: Install pytest when available
# import pytest
import tempfile
import shutil
from pathlib import Path
from collections.abc import Generator


# TODO: Enable when pytest is available
# @pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    temp_path = Path(tempfile.mkdtemp())
    try:
        yield temp_path
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


# TODO: Enable when pytest is available
# @pytest.fixture
def sample_config() -> dict[str, object]:
    """Provide sample configuration for testing."""
    return {
        "monitoring": {
            "interval": 30,
            "detection_timeout": 60,
            "dry_run": False,
        },
        "process": {
            "name": "mover",
            "paths": ["/usr/local/sbin/mover"],
        },
        "progress": {
            "min_change_threshold": 5.0,
            "estimation_window": 10,
            "exclusions": ["/.Trash-*", "/lost+found"],
        },
        "notifications": {
            "enabled_providers": ["telegram"],
            "events": ["started", "progress", "completed"],
            "rate_limits": {"progress": 300, "status": 60},
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file": None,
        },
    }