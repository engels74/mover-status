# config/providers/base.py

"""
Base configuration models for notification providers.
Defines abstract base classes and common functionality for provider settings.

Example:
    >>> class MyProviderSettings(BaseProviderSettings):
    ...     api_key: str
    ...     username: str = "Default User"
"""

from typing import Dict, List, Optional, Set

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.json_schema import JsonSchemaValue

from config.constants import (
    API,
    MessagePriority,
    JsonDict,
    Templates,
)


class RateLimitSettings(BaseModel):
    """Rate limiting configuration shared across providers."""

    rate_limit: int = Field(
        default=30,
        ge=1,
        le=60,
        description="Maximum number of messages per period"
    )

    rate_period: int = Field(
        default=60,
        ge=30,
        le=3600,
        description="Rate limit period in seconds"
    )

    retry_attempts: int = Field(
        default=API.DEFAULT_RETRIES,
        ge=1,
        le=5,
        description="Number of retry attempts for failed messages"
    )

    retry_delay: int = Field(
        default=API.DEFAULT_RETRY_DELAY,
        ge=1,
        le=30,
        description="Delay between retry attempts in seconds"
    )

    model_config = ConfigDict(
        frozen=True,
        validate_assignment=True,
        extra="forbid",
        json_schema_extra={
            "examples": [{
                "rate_limit": 30,
                "rate_period": 60,
                "retry_attempts": 3,
                "retry_delay": 5
            }]
        }
    )


class ApiSettings(BaseModel):
    """Common API settings for providers."""

    timeout: int = Field(
        default=API.DEFAULT_TIMEOUT,
        ge=1,
        le=300,
        description="API request timeout in seconds"
    )

    base_url: Optional[str] = Field(
        default=None,
        description="Base URL for API requests",
        pattern=r"^https?://.+"
    )

    headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional HTTP headers for API requests"
    )

    model_config = ConfigDict(
        frozen=True,
        validate_assignment=True,
        extra="forbid"
    )

    @field_validator("headers")
    @classmethod
    def validate_headers(cls, v: Dict[str, str]) -> Dict[str, str]:
        """Validate HTTP headers.

        Args:
            v: Headers dictionary to validate

        Returns:
            Dict[str, str]: Validated headers

        Raises:
            ValueError: If headers are invalid
        """
        invalid_headers = set()
        for key in v.keys():
            if not cls._is_valid_header_name(key):
                invalid_headers.add(key)

        if invalid_headers:
            raise ValueError(
                f"Invalid header names: {', '.join(sorted(invalid_headers))}"
            )
        return v

    @staticmethod
    def _is_valid_header_name(name: str) -> bool:
        """Check if header name is valid.

        Args:
            name: Header name to validate

        Returns:
            bool: True if header name is valid
        """
        return bool(name and name.strip() and all(c.isprintable() for c in name))


class BaseProviderSettings(BaseModel):
    """Abstract base class for provider settings."""

    enabled: bool = Field(
        default=False,
        description="Enable this notification provider"
    )

    rate_limit: RateLimitSettings = Field(
        default_factory=RateLimitSettings,
        description="Rate limiting configuration"
    )

    api_settings: ApiSettings = Field(
        default_factory=ApiSettings,
        description="API configuration"
    )

    message_template: Optional[str] = Field(
        default=Templates.DEFAULT_MESSAGE,
        min_length=1,
        description="Custom message template for notifications"
    )

    message_priority: MessagePriority = Field(
        default=MessagePriority.NORMAL,
        description="Default message priority level"
    )

    notification_increment: int = Field(
        default=API.DEFAULT_NOTIFICATION_INCREMENT,
        ge=API.MIN_NOTIFICATION_INCREMENT,
        le=API.MAX_NOTIFICATION_INCREMENT,
        description="Progress percentage increment for notifications"
    )

    tags: Set[str] = Field(
        default_factory=set,
        description="Optional tags for message categorization"
    )

    @field_validator("message_template")
    @classmethod
    def validate_message_template(cls, v: Optional[str]) -> Optional[str]:
        """Validate message template format.

        Args:
            v: Template string to validate

        Returns:
            Optional[str]: Validated template string

        Raises:
            ValueError: If template format is invalid
        """
        if v is None:
            return Templates.DEFAULT_MESSAGE

        required_placeholders = {"{percent}", "{remaining_data}", "{etc}"}
        found_placeholders = set(cls._extract_placeholders(v))

        if not found_placeholders.intersection(required_placeholders):
            raise ValueError(
                "Template must contain at least one of: "
                "{percent}, {remaining_data}, {etc}"
            )

        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Set[str]) -> Set[str]:
        """Validate message tags.

        Args:
            v: Set of tags to validate

        Returns:
            Set[str]: Validated tags

        Raises:
            ValueError: If tags are invalid
        """
        return {tag.strip().lower() for tag in v if tag.strip()}

    def to_provider_config(self) -> JsonDict:
        """Convert settings to provider configuration dictionary.

        Returns:
            JsonDict: Provider configuration dictionary
        """
        return {
            "enabled": self.enabled,
            "rate_limit": self.rate_limit.model_dump(),
            "api_settings": self.api_settings.model_dump(),
            "message_template": self.message_template,
            "message_priority": self.message_priority,
            "notification_increment": self.notification_increment,
            "tags": sorted(self.tags)  # Sort for consistent output
        }

    @staticmethod
    def _extract_placeholders(template: str) -> List[str]:
        """Extract placeholder variables from template string.

        Args:
            template: Template string to parse

        Returns:
            List[str]: List of found placeholders
        """
        import re
        pattern = r"\{([^}]+)\}"
        return re.findall(pattern, template)

    def model_json_schema(self) -> JsonSchemaValue:
        """Generate JSON schema with examples.

        Returns:
            JsonSchemaValue: JSON schema with examples
        """
        schema = super().model_json_schema()
        schema["examples"] = [{
            "enabled": True,
            "rate_limit": {
                "rate_limit": 30,
                "rate_period": 60,
                "retry_attempts": 3,
                "retry_delay": 5
            },
            "api_settings": {
                "timeout": 30,
                "headers": {
                    "User-Agent": "MoverStatus/1.0"
                }
            },
            "message_template": Templates.DEFAULT_MESSAGE,
            "message_priority": "normal",
            "notification_increment": 25,
            "tags": ["status", "mover"]
        }]
        return schema

    model_config = ConfigDict(
        validate_assignment=True,
        extra="forbid"
    )
