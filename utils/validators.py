# utils/validators.py

"""
Generic validation utilities for application configuration.
Provides core validation functions for paths, intervals, and common configuration values.
Provider-specific validation should use the validators defined in their respective modules.

Functions:
    validate_paths: Validate cache and excluded paths
    validate_notification_increment: Validate notification percentage
    validate_polling_interval: Validate monitoring interval value
    validate_url: Generic URL validation with domain restrictions
    validate_provider_config: Basic provider configuration validation

Example:
    >>> from pathlib import Path
    >>> from utils.validators import validate_paths
    >>> cache_path = Path("/mnt/cache")
    >>> excluded = [Path("/mnt/cache/downloads")]
    >>> validated_cache, validated_excluded = validate_paths(cache_path, excluded)
"""

from pathlib import Path
from typing import List, Literal, Optional, Tuple
from urllib.parse import urlparse

from pydantic import HttpUrl

from config.constants import (
    MAX_NOTIFICATION_INCREMENT,
    MIN_NOTIFICATION_INCREMENT,
)
from config.providers.discord.schemas import WebhookConfigSchema
from config.providers.telegram.schemas import BotConfigSchema


def validate_url(
    url: Optional[HttpUrl],
    required_domain: str,
    allowed_schemes: Optional[List[str]] = None,
    max_length: int = 2048,
) -> Optional[HttpUrl]:
    """Validate URL format, scheme, and domain.

    Args:
        url: URL to validate
        required_domain: Domain that must be present in URL
        allowed_schemes: List of allowed URL schemes (defaults to ["https"])
        max_length: Maximum allowed URL length

    Returns:
        Optional[HttpUrl]: Validated URL or None

    Raises:
        ValueError: If URL format is invalid
    """
    if not url:
        return None

    if allowed_schemes is None:
        allowed_schemes = ["https"]

    try:
        parsed = urlparse(str(url))
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid URL format")

        if parsed.scheme not in allowed_schemes:
            raise ValueError(f"URL scheme must be one of: {', '.join(allowed_schemes)}")

        if len(str(url)) > max_length:
            raise ValueError(f"URL length exceeds maximum of {max_length} characters")

        if required_domain not in parsed.netloc:
            raise ValueError(f"URL must be from {required_domain} domain")

        return url

    except Exception as err:
        raise ValueError(f"URL validation failed: {err}") from err


def validate_paths(
    cache_path: Path,
    excluded_paths: List[Path],
) -> Tuple[Path, List[Path]]:
    """Validate cache path and excluded paths.

    Args:
        cache_path: Main cache directory path
        excluded_paths: List of paths to exclude from monitoring

    Returns:
        Tuple[Path, List[Path]]: Validated cache path and excluded paths

    Raises:
        ValueError: If paths are invalid or don't exist
    """
    # Validate cache path
    if not isinstance(cache_path, Path):
        raise ValueError("Cache path must be a Path object")

    try:
        cache_path = cache_path.resolve(strict=True)
        if not cache_path.is_dir():
            raise ValueError(f"Cache path must be a directory: {cache_path}")
    except FileNotFoundError as err:
        raise ValueError(f"Cache path does not exist: {cache_path}") from err

    # Validate excluded paths
    validated_excluded: List[Path] = []
    for path in excluded_paths:
        if not isinstance(path, Path):
            raise ValueError(f"Excluded path must be a Path object: {path}")

        try:
            resolved_path = path.resolve(strict=True)
            if not str(resolved_path).startswith(str(cache_path)):
                raise ValueError(
                    f"Excluded path must be within cache path: {resolved_path}"
                )
            validated_excluded.append(resolved_path)
        except FileNotFoundError as err:
            raise ValueError(f"Excluded path does not exist: {path}") from err

    return cache_path, validated_excluded


def validate_notification_increment(value: int) -> int:
    """Validate notification increment percentage.

    Args:
        value: Increment percentage to validate

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
        value: Polling interval in seconds

    Returns:
        float: Validated interval value

    Raises:
        ValueError: If interval is invalid
    """
    if not isinstance(value, (int, float)):
        raise ValueError("Polling interval must be a number")

    if value <= 0:
        raise ValueError("Polling interval must be positive")

    if value < 0.1:
        raise ValueError("Polling interval cannot be less than 0.1 seconds")

    if value > 3600:  # 1 hour max
        raise ValueError("Polling interval cannot exceed 3600 seconds (1 hour)")

    return float(value)


def validate_provider_config(
    config: dict,
    required_fields: Optional[List[str]] = None,
    provider_type: Optional[Literal["discord", "telegram"]] = None,
) -> dict:
    """Validate provider configuration dictionary.

    Args:
        config: Configuration dictionary to validate
        required_fields: List of required field names
        provider_type: Specific provider type for additional validation

    Returns:
        dict: Validated configuration dictionary

    Raises:
        ValueError: If configuration is invalid
    """
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a dictionary")

    if required_fields:
        missing = [field for field in required_fields if field not in config]
        if missing:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing)}")

    try:
        if provider_type == "discord":
            WebhookConfigSchema(**config)
        elif provider_type == "telegram":
            BotConfigSchema(**config)
    except ValueError as err:
        raise ValueError(f"Invalid {provider_type} configuration: {err}") from err

    return config
