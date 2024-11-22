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
        default=3,
        ge=1,
        le=5,
        description="Number of retry attempts for failed messages"
    )
    retry_delay: int = Field(
        default=5,
        ge=1,
        le=30,
        description="Delay between retry attempts in seconds"
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
    message_template: Optional[str] = Field(
        default=None,
        description="Custom message template for notifications"
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
            return v

        required_placeholders = {"{percent}", "{remaining_data}", "{etc}"}
        template_placeholders = {
            p for p in required_placeholders if p in v
        }

        if not template_placeholders.issuperset(required_placeholders):
            missing = required_placeholders - template_placeholders
            raise ValueError(
                f"Template missing required placeholders: {', '.join(missing)}"
            )

        return v

    def to_provider_config(self) -> Dict:
        """Convert settings to provider configuration dictionary.

        Returns:
            Dict: Provider configuration dictionary

        Note:
            This method should be overridden by provider implementations
            to include provider-specific configuration.
        """
        return {
            "enabled": self.enabled,
            "rate_limit": self.rate_limit.dict(),
            "message_template": self.message_template
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
                    "message_template": "Progress: {percent}% ({remaining_data} remaining, ETC: {etc})"
                }
            ]
        }
