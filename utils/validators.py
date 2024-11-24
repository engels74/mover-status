# utils/validators.py

"""
Base validation utilities for provider configurations.
Provides reusable validation classes and functions for common configuration elements.

Example:
    >>> class DiscordValidator(BaseProviderValidator):
    ...     def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
    ...         self.validate_rate_limits(config.get("rate_limit", 30))
    ...         return config
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar, Union
from urllib.parse import urlparse

from pydantic import HttpUrl

from config.constants import (
    MAX_NOTIFICATION_INCREMENT,
    MIN_NOTIFICATION_INCREMENT,
    PathLike,
)

ConfigT = TypeVar("ConfigT", bound=Dict[str, Any])

@dataclass
class ValidationResult:
    """Container for validation results."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    validated_data: Optional[Dict[str, Any]] = None

class ValidationError(Exception):
    """Base exception for validation errors."""
    def __init__(self, message: str, field: Optional[str] = None):
        self.field = field
        super().__init__(message)

class ConfigurationError(ValidationError):
    """Raised when configuration validation fails."""
    pass

class RateLimitError(ValidationError):
    """Raised when rate limit validation fails."""
    pass

class URLValidationError(ValidationError):
    """Raised when URL validation fails."""
    pass

class BaseProviderValidator(ABC):
    """Abstract base class for provider-specific validators."""

    @abstractmethod
    def validate_config(self, config: ConfigT) -> ConfigT:
        """Validate complete provider configuration.

        Args:
            config: Provider configuration dictionary

        Returns:
            ConfigT: Validated configuration dictionary

        Raises:
            ConfigurationError: If configuration is invalid
        """
        pass

    @classmethod
    def validate_rate_limits(
        cls,
        rate_limit: int,
        rate_period: int,
        min_limit: int = 1,
        max_limit: int = 60,
        min_period: int = 1,
        max_period: int = 3600
    ) -> None:
        """Validate rate limiting configuration.

        Args:
            rate_limit: Maximum number of requests per period
            rate_period: Time period in seconds
            min_limit: Minimum allowed rate limit
            max_limit: Maximum allowed rate limit
            min_period: Minimum period in seconds
            max_period: Maximum period in seconds

        Raises:
            RateLimitError: If rate limits are invalid
        """
        if not isinstance(rate_limit, int):
            raise RateLimitError("Rate limit must be an integer")
        if not isinstance(rate_period, int):
            raise RateLimitError("Rate period must be an integer")

        if not min_limit <= rate_limit <= max_limit:
            raise RateLimitError(
                f"Rate limit must be between {min_limit} and {max_limit}"
            )
        if not min_period <= rate_period <= max_period:
            raise RateLimitError(
                f"Rate period must be between {min_period} and {max_period} seconds"
            )

    @classmethod
    def validate_url(
        cls,
        url: Optional[Union[str, HttpUrl]],
        required_domain: Optional[str] = None,
        allowed_schemes: Optional[List[str]] = None,
        required: bool = True,
        max_length: int = 2048
    ) -> Optional[str]:
        """Validate URL format and constraints.

        Args:
            url: URL to validate
            required_domain: Domain that must be present in URL
            allowed_schemes: List of allowed URL schemes
            required: Whether URL is required
            max_length: Maximum allowed URL length

        Returns:
            Optional[str]: Validated URL string or None

        Raises:
            URLValidationError: If URL validation fails
        """
        if not url:
            if required:
                raise URLValidationError("URL is required")
            return None

        url_str = str(url)
        if len(url_str) > max_length:
            raise URLValidationError(f"URL exceeds maximum length of {max_length}")

        try:
            parsed = urlparse(url_str)
            if not all([parsed.scheme, parsed.netloc]):
                raise URLValidationError("Invalid URL format")

            if allowed_schemes and parsed.scheme not in allowed_schemes:
                raise URLValidationError(
                    f"URL scheme must be one of: {', '.join(allowed_schemes)}"
                )

            if required_domain and required_domain not in parsed.netloc:
                raise URLValidationError(f"URL must be from {required_domain} domain")

            return url_str

        except Exception as err:
            raise URLValidationError(f"URL validation failed: {err}") from err

    @classmethod
    def validate_paths(
        cls,
        base_path: PathLike,
        excluded_paths: Optional[List[PathLike]] = None
    ) -> tuple[Path, List[Path]]:
        """Validate base path and excluded paths.

        Args:
            base_path: Main directory path to validate
            excluded_paths: List of paths to exclude

        Returns:
            tuple[Path, List[Path]]: Validated base path and excluded paths

        Raises:
            ValidationError: If path validation fails
        """
        try:
            base = Path(base_path).resolve(strict=True)
            if not base.is_dir():
                raise ValidationError(f"Base path must be a directory: {base}")

            validated_excluded: List[Path] = []
            if excluded_paths:
                for path in excluded_paths:
                    excluded = Path(path).resolve(strict=True)
                    if not str(excluded).startswith(str(base)):
                        raise ValidationError(
                            f"Excluded path must be within base path: {excluded}"
                        )
                    validated_excluded.append(excluded)

            return base, validated_excluded

        except FileNotFoundError as err:
            raise ValidationError(f"Path does not exist: {err.filename}") from err

    @classmethod
    def validate_notification_increment(
        cls,
        value: int,
        min_value: int = MIN_NOTIFICATION_INCREMENT,
        max_value: int = MAX_NOTIFICATION_INCREMENT
    ) -> int:
        """Validate notification increment percentage.

        Args:
            value: Increment percentage to validate
            min_value: Minimum allowed increment
            max_value: Maximum allowed increment

        Returns:
            int: Validated increment value

        Raises:
            ValidationError: If increment is invalid
        """
        if not isinstance(value, int):
            raise ValidationError("Notification increment must be an integer")

        if not min_value <= value <= max_value:
            raise ValidationError(
                f"Notification increment must be between {min_value} and {max_value}"
            )

        return value

    @staticmethod
    def validate_identifier(
        value: str,
        pattern: str = r"^[a-zA-Z0-9_-]+$",
        min_length: int = 1,
        max_length: int = 64
    ) -> str:
        """Validate string identifier format.

        Args:
            value: String to validate
            pattern: Regex pattern for valid format
            min_length: Minimum string length
            max_length: Maximum string length

        Returns:
            str: Validated identifier

        Raises:
            ValidationError: If identifier is invalid
        """
        if not value or not isinstance(value, str):
            raise ValidationError("Identifier must be a non-empty string")

        if not min_length <= len(value) <= max_length:
            raise ValidationError(
                f"Identifier length must be between {min_length} and {max_length}"
            )

        if not re.match(pattern, value):
            raise ValidationError(
                "Identifier can only contain letters, numbers, underscores, and hyphens"
            )

        return value
