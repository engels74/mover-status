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
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar, Union
from urllib.parse import urlparse

from pydantic import HttpUrl

from config.constants import (
    Monitoring,
)

ConfigT = TypeVar("ConfigT", bound=Dict[str, Any])
PathLike = Union[str, Path]  # Define PathLike type alias


@dataclass
class ValidationContext:
    """Container for validation context."""
    provider: str
    field: str
    parent: Optional[str] = None
    details: Dict[str, Any] = dataclass_field(default_factory=dict)


@dataclass
class ValidationResult:
    """Container for validation results."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    context: Optional[ValidationContext] = None
    validated_data: Optional[Dict[str, Any]] = None


class ValidationResultSet:
    """Container for multiple validation results."""
    def __init__(self):
        self.results: List[ValidationResult] = []

    def add_result(self, result: ValidationResult) -> None:
        """Add a validation result to the set."""
        self.results.append(result)

    @property
    def is_valid(self) -> bool:
        """Check if all results are valid."""
        return all(r.is_valid for r in self.results)

    @property
    def errors(self) -> List[str]:
        """Get all errors from all results."""
        return [err for r in self.results if not r.is_valid for err in r.errors]

    @property
    def warnings(self) -> List[str]:
        """Get all warnings from all results."""
        return [warn for r in self.results for warn in r.warnings]


class ValidationError(Exception):
    """Base exception for validation errors."""
    def __init__(self, message: str, field: Optional[str] = None, context: Optional[ValidationContext] = None):
        self.field = field
        self.context = context
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


class MessageValidationError(ValidationError):
    """Raised when message validation fails."""
    pass


class TimeoutError(ValidationError):
    """Raised when timeout validation fails."""
    pass


class RetryError(ValidationError):
    """Raised when retry configuration validation fails."""
    pass


class MessageValidator(ABC):
    """Base class for message content validation."""

    @abstractmethod
    def validate_content(
        self,
        content: str,
        context: Optional[ValidationContext] = None
    ) -> str:
        """Validate message content.

        Args:
            content: Message content to validate
            context: Optional validation context

        Returns:
            str: Validated content

        Raises:
            MessageValidationError: If content is invalid
        """
        pass

    @abstractmethod
    def validate_format(
        self,
        format_type: str,
        context: Optional[ValidationContext] = None
    ) -> str:
        """Validate message format type.

        Args:
            format_type: Format type to validate
            context: Optional validation context

        Returns:
            str: Validated format type

        Raises:
            MessageValidationError: If format type is invalid
        """
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
        max_period: int = 3600,
        context: Optional[ValidationContext] = None
    ) -> None:
        """Validate rate limiting configuration.

        Args:
            rate_limit: Maximum number of requests per period
            rate_period: Time period in seconds
            min_limit: Minimum allowed rate limit
            max_limit: Maximum allowed rate limit
            min_period: Minimum period in seconds
            max_period: Maximum period in seconds
            context: Optional validation context

        Raises:
            RateLimitError: If rate limits are invalid
        """
        if not isinstance(rate_limit, int):
            raise RateLimitError("Rate limit must be an integer", context=context)
        if not isinstance(rate_period, int):
            raise RateLimitError("Rate period must be an integer", context=context)

        if not min_limit <= rate_limit <= max_limit:
            raise RateLimitError(
                f"Rate limit must be between {min_limit} and {max_limit}",
                context=context
            )
        if not min_period <= rate_period <= max_period:
            raise RateLimitError(
                f"Rate period must be between {min_period} and {max_period} seconds",
                context=context
            )

    @classmethod
    def validate_timeouts(
        cls,
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
        write_timeout: Optional[float] = None,
        pool_timeout: Optional[float] = None,
        min_timeout: float = 0.1,
        max_timeout: float = 300.0,
        context: Optional[ValidationContext] = None
    ) -> Dict[str, Optional[float]]:
        """Validate timeout configuration.

        Args:
            connect_timeout: Connection timeout in seconds
            read_timeout: Read timeout in seconds
            write_timeout: Write timeout in seconds
            pool_timeout: Connection pool timeout in seconds
            min_timeout: Minimum allowed timeout
            max_timeout: Maximum allowed timeout
            context: Optional validation context

        Returns:
            Dict[str, Optional[float]]: Validated timeout configuration

        Raises:
            TimeoutError: If timeouts are invalid
        """
        timeouts = {
            "connect": connect_timeout,
            "read": read_timeout,
            "write": write_timeout,
            "pool": pool_timeout
        }

        for name, value in timeouts.items():
            if value is not None:
                if not isinstance(value, (int, float)):
                    raise TimeoutError(
                        f"{name.title()} timeout must be a number",
                        field=name,
                        context=context
                    )
                if not min_timeout <= value <= max_timeout:
                    raise TimeoutError(
                        f"{name.title()} timeout must be between {min_timeout} and {max_timeout} seconds",
                        field=name,
                        context=context
                    )

        return timeouts

    @classmethod
    def validate_retry_config(
        cls,
        max_retries: int,
        retry_delay: float,
        max_delay: float,
        backoff_factor: float = 2.0,
        min_retries: int = 0,
        max_retries_limit: int = 10,
        min_delay: float = 0.1,
        context: Optional[ValidationContext] = None
    ) -> None:
        """Validate retry configuration.

        Args:
            max_retries: Maximum number of retries
            retry_delay: Initial retry delay in seconds
            max_delay: Maximum retry delay in seconds
            backoff_factor: Exponential backoff factor
            min_retries: Minimum allowed retries
            max_retries_limit: Maximum allowed retries
            min_delay: Minimum allowed delay
            context: Optional validation context

        Raises:
            RetryError: If retry configuration is invalid
        """
        if not isinstance(max_retries, int):
            raise RetryError("Max retries must be an integer", context=context)
        if not min_retries <= max_retries <= max_retries_limit:
            raise RetryError(
                f"Max retries must be between {min_retries} and {max_retries_limit}",
                context=context
            )

        if not isinstance(retry_delay, (int, float)):
            raise RetryError("Retry delay must be a number", context=context)
        if not min_delay <= retry_delay <= max_delay:
            raise RetryError(
                f"Retry delay must be between {min_delay} and {max_delay} seconds",
                context=context
            )

        if not isinstance(backoff_factor, (int, float)) or backoff_factor < 1:
            raise RetryError(
                "Backoff factor must be a number greater than or equal to 1",
                context=context
            )

    @classmethod
    def validate_url(
        cls,
        url: Optional[Union[str, HttpUrl]],
        required_domain: Optional[str] = None,
        allowed_schemes: Optional[List[str]] = None,
        required: bool = True,
        max_length: int = 2048,
        context: Optional[ValidationContext] = None
    ) -> Optional[str]:
        """Validate URL format and constraints.

        Args:
            url: URL to validate
            required_domain: Domain that must be present in URL
            allowed_schemes: List of allowed URL schemes
            required: Whether URL is required
            max_length: Maximum allowed URL length
            context: Optional validation context

        Returns:
            Optional[str]: Validated URL string or None

        Raises:
            URLValidationError: If URL validation fails
        """
        if not url:
            if required:
                raise URLValidationError("URL is required", context=context)
            return None

        url_str = str(url)
        if len(url_str) > max_length:
            raise URLValidationError(
                f"URL exceeds maximum length of {max_length}",
                context=context
            )

        try:
            parsed = urlparse(url_str)
            if not all([parsed.scheme, parsed.netloc]):
                raise URLValidationError("Invalid URL format", context=context)

            if allowed_schemes and parsed.scheme not in allowed_schemes:
                raise URLValidationError(
                    f"URL scheme must be one of: {', '.join(allowed_schemes)}",
                    context=context
                )

            if required_domain and required_domain not in parsed.netloc:
                raise URLValidationError(
                    f"URL must be from {required_domain} domain",
                    context=context
                )

            return url_str

        except Exception as err:
            raise URLValidationError(
                f"URL validation failed: {err}",
                context=context
            ) from err

    @classmethod
    def validate_paths(
        cls,
        base_path: PathLike,
        excluded_paths: Optional[List[PathLike]] = None,
        context: Optional[ValidationContext] = None
    ) -> tuple[Path, List[Path]]:
        """Validate base path and excluded paths.

        Args:
            base_path: Main directory path to validate
            excluded_paths: List of paths to exclude
            context: Optional validation context

        Returns:
            tuple[Path, List[Path]]: Validated base path and excluded paths

        Raises:
            ValidationError: If path validation fails
        """
        try:
            base = Path(base_path).resolve(strict=True)
            if not base.is_dir():
                raise ValidationError(
                    f"Base path must be a directory: {base}",
                    context=context
                )

            validated_excluded: List[Path] = []
            if excluded_paths:
                for path in excluded_paths:
                    excluded = Path(path).resolve(strict=True)
                    if not str(excluded).startswith(str(base)):
                        raise ValidationError(
                            f"Excluded path must be within base path: {excluded}",
                            context=context
                        )
                    validated_excluded.append(excluded)

            return base, validated_excluded

        except FileNotFoundError as err:
            raise ValidationError(
                f"Path does not exist: {err.filename}",
                context=context
            ) from err

    @classmethod
    def validate_notification_increment(
        cls,
        value: int,
        min_value: int = Monitoring.MIN_INCREMENT,
        max_value: int = Monitoring.MAX_INCREMENT,
        context: Optional[ValidationContext] = None
    ) -> int:
        """Validate notification increment percentage.

        Args:
            value: Increment percentage to validate
            min_value: Minimum allowed increment
            max_value: Maximum allowed increment
            context: Optional validation context

        Returns:
            int: Validated increment value

        Raises:
            ValidationError: If increment is invalid
        """
        if not isinstance(value, int):
            raise ValidationError(
                "Notification increment must be an integer",
                context=context
            )

        if not min_value <= value <= max_value:
            raise ValidationError(
                f"Notification increment must be between {min_value} and {max_value}",
                context=context
            )

        return value

    @staticmethod
    def validate_identifier(
        value: str,
        pattern: str = r"^[a-zA-Z0-9_-]+$",
        min_length: int = 1,
        max_length: int = 64,
        context: Optional[ValidationContext] = None
    ) -> str:
        """Validate string identifier format.

        Args:
            value: String to validate
            pattern: Regex pattern for valid format
            min_length: Minimum string length
            max_length: Maximum string length
            context: Optional validation context

        Returns:
            str: Validated identifier

        Raises:
            ValidationError: If identifier is invalid
        """
        if not value or not isinstance(value, str):
            raise ValidationError(
                "Identifier must be a non-empty string",
                context=context
            )

        if not min_length <= len(value) <= max_length:
            raise ValidationError(
                f"Identifier length must be between {min_length} and {max_length}",
                context=context
            )

        if not re.match(pattern, value):
            raise ValidationError(
                "Identifier can only contain letters, numbers, underscores, and hyphens",
                context=context
            )

        return value
