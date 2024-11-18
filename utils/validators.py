# utils/validators.py

"""
Validation utilities for configuration settings.
Provides reusable validation functions for settings and configuration values.
"""

from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import HttpUrl

from config.constants import MAX_NOTIFICATION_INCREMENT, MIN_NOTIFICATION_INCREMENT


def validate_webhook_url(url: Optional[HttpUrl], enabled: bool = False) -> Optional[HttpUrl]:
    """Validate Discord webhook URL format and presence.
    Args:
        url: The webhook URL to validate
        enabled: Whether Discord notifications are enabled
    Returns:
        Optional[HttpUrl]: The validated webhook URL
    Raises:
        ValueError: If URL is invalid or missing when enabled
    """
    if enabled and not url:
        raise ValueError("Webhook URL must be provided when Discord is enabled")

    if url:
        parsed = urlparse(str(url))
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid webhook URL format")
        if "discord.com" not in parsed.netloc:
            raise ValueError("Webhook URL must be from discord.com domain")

    return url

def validate_telegram_credentials(
    bot_token: Optional[str],
    chat_id: Optional[str],
    enabled: bool = False
) -> tuple[Optional[str], Optional[str]]:
    """Validate Telegram bot token and chat ID.
    Args:
        bot_token: The Telegram bot token
        chat_id: The Telegram chat ID
        enabled: Whether Telegram notifications are enabled
    Returns:
        tuple[Optional[str], Optional[str]]: Validated bot token and chat ID
    Raises:
        ValueError: If credentials are invalid or missing when enabled
    """
    if enabled:
        if not bot_token:
            raise ValueError("Bot token must be provided when Telegram is enabled")
        if not chat_id:
            raise ValueError("Chat ID must be provided when Telegram is enabled")

        # Basic format validation
        if not bot_token.strip():
            raise ValueError("Bot token cannot be empty")
        if not chat_id.strip():
            raise ValueError("Chat ID cannot be empty")

    return bot_token, chat_id

def validate_paths(
    cache_path: Path,
    excluded_paths: List[Path]
) -> tuple[Path, List[Path]]:
    """Validate cache path and excluded paths.
    Args:
        cache_path: The main cache directory path
        excluded_paths: List of paths to exclude from monitoring
    Returns:
        tuple[Path, List[Path]]: Validated cache path and excluded paths
    Raises:
        ValueError: If paths are invalid or don't exist
    """
    # Validate cache path
    if not cache_path.exists():
        raise ValueError(f"Cache path does not exist: {cache_path}")
    if not cache_path.is_dir():
        raise ValueError(f"Cache path must be a directory: {cache_path}")

    # Validate excluded paths
    validated_excluded = []
    for path in excluded_paths:
        if not path.is_absolute():
            path = cache_path / path
        if not path.exists():
            raise ValueError(f"Excluded path does not exist: {path}")
        if not str(path).startswith(str(cache_path)):
            raise ValueError(f"Excluded path must be within cache path: {path}")
        validated_excluded.append(path)

    return cache_path, validated_excluded

def validate_notification_increment(value: int) -> int:
    """Validate notification increment percentage.
    Args:
        value: The increment percentage to validate
    Returns:
        int: Validated increment value
    Raises:
        ValueError: If value is out of valid range
    """
    if not isinstance(value, int):
        raise ValueError("Notification increment must be an integer")
    if value < MIN_NOTIFICATION_INCREMENT:
        raise ValueError(
            f"Notification increment must be at least {MIN_NOTIFICATION_INCREMENT}%"
        )
    if value > MAX_NOTIFICATION_INCREMENT:
        raise ValueError(
            f"Notification increment cannot exceed {MAX_NOTIFICATION_INCREMENT}%"
        )
    return value

def validate_polling_interval(value: float) -> float:
    """Validate polling interval value.
    Args:
        value: The polling interval in seconds
    Returns:
        float: Validated interval value
    Raises:
        ValueError: If value is invalid
    """
    if value <= 0:
        raise ValueError("Polling interval must be positive")
    if value < 0.1:
        raise ValueError("Polling interval cannot be less than 0.1 seconds")
    return value
