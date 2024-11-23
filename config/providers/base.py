# config/providers/base.py

"""
Base configuration models for notification providers.
Defines abstract base classes and common functionality for provider settings.

Example:
    >>> from config.providers.base import BaseProviderSettings
    >>> class DiscordSettings(BaseProviderSettings):
    ...     webhook_url: str
    ...     username: str = "Mover Bot"
"""

from abc import ABC
from typing import Dict, Optional

from pydantic import BaseModel, Field, field_validator

from config.constants import (
    DEFAULT_API_RETRIES,
    DEFAULT_API_RETRY_DELAY,
    DEFAULT_API_TIMEOUT,
    DEFAULT_MESSAGE_TEMPLATE,
    DEFAULT_NOTIFICATION_INCREMENT,
    TEMPLATE_PLACEHOLDERS,
    JsonDict,
    MessagePriority,
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
        default=DEFAULT_API_RETRIES,
        ge=1,
        le=5,
        description="Number of retry attempts for failed messages"
    )
    retry_delay: int = Field(
        default=DEFAULT_API_RETRY_DELAY,
        ge=1,
        le=30,
        description="Delay between retry attempts in seconds"
    )

    class Config:
        """Pydantic model configuration."""
        frozen = True
        validate_assignment = True
        extra = "forbid"


class ApiSettings(BaseModel):
    """Common API settings for providers."""
    timeout: int = Field(
        default=DEFAULT_API_TIMEOUT,
        ge=1,
        le=300,
        description="API request timeout in seconds"
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Base URL for API requests"
    )
    headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional HTTP headers for API requests"
    )

    class Config:
        """Pydantic model configuration."""
        frozen = True
        validate_assignment = True
        extra = "forbid"


class BaseProviderSettings(BaseModel, ABC):
    """
    Abstract base class for provider settings.
    Defines common configuration options and validation patterns.
    """
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
        default=DEFAULT_MESSAGE_TEMPLATE,
        description="Custom message template for notifications"
    )
    message_priority: MessagePriority = Field(
        default=MessagePriority.NORMAL,
        description="Default message priority level"
    )
    notification_increment: int = Field(
        default=DEFAULT_NOTIFICATION_INCREMENT,
        description="Progress percentage increment for notifications"
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
            return DEFAULT_MESSAGE_TEMPLATE

        # Check if template contains at least one valid placeholder
        template_placeholders = TEMPLATE_PLACEHOLDERS.values()
        if not any(placeholder in v for placeholder in template_placeholders):
            valid_placeholders = ", ".join(template_placeholders)
            raise ValueError(
                f"Template must contain at least one valid placeholder. "
                f"Valid placeholders are: {valid_placeholders}"
            )

        return v

    def to_provider_config(self) -> JsonDict:
        """Convert settings to provider configuration dictionary.

        Returns:
            JsonDict: Provider configuration dictionary

        Note:
            This method should be overridden by provider implementations
            to include provider-specific configuration.
        """
        return {
            "enabled": self.enabled,
            "rate_limit": self.rate_limit.model_dump(),
            "api_settings": self.api_settings.model_dump(),
            "message_template": self.message_template,
            "message_priority": self.message_priority,
            "notification_increment": self.notification_increment
        }

    class Config:
        """Pydantic model configuration."""
        validate_assignment = True
        extra = "forbid"
        json_schema_extra = {
            "examples": [
                {
                    "enabled": True,
                    "rate_limit": {
                        "rate_limit": 30,
                        "rate_period": 60,
                        "retry_attempts": 3,
                        "retry_delay": 5
                    },
                    "api_settings": {
                        "timeout": 30,
                        "base_url": None,
                        "headers": {}
                    },
                    "message_template": DEFAULT_MESSAGE_TEMPLATE,
                    "message_priority": "normal",
                    "notification_increment": 25
                }
            ]
        }
