# notifications/providers/discord/validators.py

"""
Discord-specific configuration validation.
Handles validation of webhook URLs, message content, and Discord-specific constraints.

Example:
    >>> validator = DiscordValidator()
    >>> config = {
    ...     "webhook_url": "https://discord.com/api/webhooks/123/abc",
    ...     "username": "Mover Bot"
    ... }
    >>> validated = validator.validate_config(config)
"""

import re
from typing import Any, Dict, Optional, Union
from urllib.parse import urlparse

from pydantic import HttpUrl

from config.constants import JsonDict
from shared.types.discord import ApiLimits, DiscordColor
from utils.validators import (
    BaseProviderValidator,
    URLValidationError,
    ValidationError,
)


class DiscordValidationError(ValidationError):
    """Discord-specific validation error."""
    pass


class DiscordValidator(BaseProviderValidator):
    """Validates Discord webhook configurations and message content."""

    ALLOWED_DOMAINS = {"discord.com", "ptb.discord.com", "canary.discord.com"}
    ALLOWED_AVATAR_DOMAINS = {
        "cdn.discordapp.com",
        "media.discordapp.net",
        "i.imgur.com"
    }
    DEFAULT_COLOR = DiscordColor.INFO

    @classmethod
    def validate_webhook_url(
        cls,
        url: Optional[Union[str, HttpUrl]],
        required: bool = True
    ) -> Optional[str]:
        """Validate Discord webhook URL format.

        Args:
            url: Webhook URL to validate
            required: Whether URL is required

        Returns:
            Optional[str]: Validated webhook URL or None

        Raises:
            URLValidationError: If webhook URL is invalid

        Example:
            >>> url = "https://discord.com/api/webhooks/123/abc"
            >>> validated = DiscordValidator.validate_webhook_url(url)
        """
        # First validate basic URL format
        url_str = cls.validate_url(
            url,
            required_domain=None,  # We'll check domains separately
            allowed_schemes=["https"],
            required=required
        )
        if not url_str:
            return None

        try:
            parsed = urlparse(url_str)

            # Validate against allowed Discord domains
            if not any(domain in parsed.netloc for domain in cls.ALLOWED_DOMAINS):
                domains_str = ", ".join(cls.ALLOWED_DOMAINS)
                raise URLValidationError(f"Webhook URL must be from: {domains_str}")

            # Validate webhook path format
            path_parts = parsed.path.strip("/").split("/")
            if len(path_parts) != 4 or path_parts[0:2] != ["api", "webhooks"]:
                raise URLValidationError("Invalid webhook URL path format")

            # Validate webhook ID and token
            webhook_id, token = path_parts[2:4]
            if not webhook_id.isdigit():
                raise URLValidationError("Invalid webhook ID format")

            if not re.match(r"^[A-Za-z0-9_-]{60,80}$", token):
                raise URLValidationError("Invalid webhook token format")

            return url_str

        except URLValidationError:
            raise
        except Exception as err:
            raise URLValidationError("Webhook URL validation failed") from err

    @classmethod
    def validate_avatar_url(
        cls,
        url: Optional[Union[str, HttpUrl]]
    ) -> Optional[str]:
        """Validate Discord avatar URL.

        Args:
            url: Avatar URL to validate

        Returns:
            Optional[str]: Validated avatar URL or None

        Raises:
            URLValidationError: If avatar URL is invalid

        Example:
            >>> url = "https://cdn.discordapp.com/avatars/123/abc.png"
            >>> validated = DiscordValidator.validate_avatar_url(url)
        """
        if not url:
            return None

        url_str = cls.validate_url(
            url,
            required_domain=None,  # We'll check domains separately
            allowed_schemes=["https"],
            required=False
        )
        if not url_str:
            return None

        parsed = urlparse(url_str)
        if not any(domain in parsed.netloc for domain in cls.ALLOWED_AVATAR_DOMAINS):
            domains_str = ", ".join(cls.ALLOWED_AVATAR_DOMAINS)
            raise URLValidationError(f"Avatar URL must be from: {domains_str}")

        return url_str

    @classmethod
    def validate_username(
        cls,
        username: Optional[str],
        default: str = "Mover Bot"
    ) -> str:
        """Validate Discord webhook username.

        Args:
            username: Username to validate
            default: Default username if none provided

        Returns:
            str: Validated username

        Raises:
            ValidationError: If username is invalid

        Example:
            >>> username = "Status Bot"
            >>> validated = DiscordValidator.validate_username(username)
        """
        if not username:
            return default

        if len(username) > ApiLimits.USERNAME_LENGTH:
            raise ValidationError(
                f"Username exceeds maximum length of {ApiLimits.USERNAME_LENGTH}"
            )

        # Discord allows most characters in usernames, but let's be conservative
        if not re.match(r"^[\w\-\s]{1,32}$", username):
            raise ValidationError(
                "Username can only contain letters, numbers, underscores, hyphens, and spaces"
            )

        return username

    @classmethod
    def validate_embed_color(
        cls,
        color: Optional[int]
    ) -> int:
        """Validate Discord embed color.

        Args:
            color: Color integer to validate

        Returns:
            int: Validated color value

        Raises:
            ValidationError: If color is invalid

        Example:
            >>> color = 0x2ECC71
            >>> validated = DiscordValidator.validate_embed_color(color)
        """
        if color is None:
            return cls.DEFAULT_COLOR

        if not isinstance(color, int):
            raise ValidationError("Embed color must be an integer")

        if not 0 <= color <= 0xFFFFFF:
            raise ValidationError("Embed color must be a valid hex color (0-0xFFFFFF)")

        return color

    @classmethod
    def validate_thread_name(
        cls,
        name: Optional[str]
    ) -> Optional[str]:
        """Validate Discord thread name.

        Args:
            name: Thread name to validate

        Returns:
            Optional[str]: Validated thread name or None

        Raises:
            ValidationError: If thread name is invalid

        Example:
            >>> name = "Status Updates"
            >>> validated = DiscordValidator.validate_thread_name(name)
        """
        if not name:
            return None

        if len(name) > ApiLimits.CHANNEL_NAME_LENGTH:
            raise ValidationError(
                f"Thread name exceeds maximum length of {ApiLimits.CHANNEL_NAME_LENGTH}"
            )

        # Discord thread name validation rules
        if not re.match(r"^[\w\-\s]{1,100}$", name):
            raise ValidationError(
                "Thread name can only contain letters, numbers, underscores, hyphens, and spaces"
            )

        return name

    def validate_config(self, config: Dict[str, Any]) -> JsonDict:
        """Validate complete Discord webhook configuration.

        Args:
            config: Configuration dictionary to validate

        Returns:
            JsonDict: Validated configuration dictionary

        Raises:
            DiscordValidationError: If configuration is invalid

        Example:
            >>> config = {
            ...     "webhook_url": "https://discord.com/api/webhooks/123/abc",
            ...     "username": "Mover Bot",
            ...     "rate_limit": 30
            ... }
            >>> validated = validator.validate_config(config)
        """
        try:
            # Validate required webhook URL
            webhook_url = self.validate_webhook_url(
                config.get("webhook_url"),
                required=True
            )

            # Validate optional settings
            username = self.validate_username(config.get("username"))
            avatar_url = self.validate_avatar_url(config.get("avatar_url"))
            embed_color = self.validate_embed_color(config.get("embed_color"))
            thread_name = self.validate_thread_name(config.get("thread_name"))

            # Validate rate limits
            rate_limit = config.get("rate_limit", 30)
            rate_period = config.get("rate_period", 60)
            self.validate_rate_limits(rate_limit, rate_period)

            # Return validated configuration
            return {
                "webhook_url": webhook_url,
                "username": username,
                "avatar_url": avatar_url,
                "embed_color": embed_color,
                "thread_name": thread_name,
                "rate_limit": rate_limit,
                "rate_period": rate_period
            }

        except ValidationError as err:
            raise DiscordValidationError(str(err)) from err
        except Exception as err:
            raise DiscordValidationError("Configuration validation failed") from err
