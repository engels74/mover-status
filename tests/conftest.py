"""
Test fixtures for the mover_status package.
"""

import os
import tempfile
from typing import Generator, Dict, Any

import pytest


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """
    Create a temporary directory for testing.
    
    Returns:
        Generator[str, None, None]: Path to the temporary directory.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def temp_file() -> Generator[str, None, None]:
    """
    Create a temporary file for testing.
    
    Returns:
        Generator[str, None, None]: Path to the temporary file.
    """
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        file_path = temp_file.name
        yield file_path
        if os.path.exists(file_path):
            os.unlink(file_path)


@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """
    Provide a sample configuration for testing.
    
    Returns:
        Dict[str, Any]: Sample configuration dictionary.
    """
    return {
        "notification": {
            "telegram": {
                "enabled": True,
                "bot_token": "test_bot_token",
                "chat_id": "test_chat_id"
            },
            "discord": {
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/test_webhook",
                "name_override": "Test Bot"
            },
            "increment": 25
        },
        "monitoring": {
            "mover_executable": "/usr/local/sbin/mover",
            "exclusions": [
                "/mnt/cache/excluded_folder1",
                "/mnt/cache/excluded_folder2"
            ]
        },
        "debug": {
            "enabled": False
        }
    }
