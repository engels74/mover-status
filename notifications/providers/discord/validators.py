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

from typing import Any, Dict, Optional, Union
from urllib.parse import urlparse

from pydantic import HttpUrl

from config.constants import JsonDict
from shared.providers.discord import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_SCHEMES,
    ASSET_DOMAINS,
    MAX_URL_LENGTH,
    MESSAGES,
    THREAD_NAME_PATTERN,
    USERNAME_PATTERN,
    WEBHOOK_DOMAINS,
    WEBHOOK_PATH_PREFIX,
    WEBHOOK_TOKEN_PATTERN,
    ApiLimits,
    DiscordColor,
)
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

    # Use shared constants for domains
    ALLOWED_DOMAINS = WEBHOOK_DOMAINS
    ALLOWED_AVATAR_DOMAINS = ASSET_DOMAINS
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
            allowed_schemes=list(ALLOWED_SCHEMES),
            required=required
        )
        if not url_str:
            return None

        try:
            parsed = urlparse(url_str)

            # Check URL length
            if len(url_str) > MAX_URL_LENGTH:
                raise URLValidationError(MESSAGES["url_length"].format(
                    field_name="Webhook URL",
                    max_length=MAX_URL_LENGTH
                ))

            # Validate against allowed Discord domains
            if not any(domain in parsed.netloc for domain in cls.ALLOWED_DOMAINS):
                domains_str = ", ".join(sorted(cls.ALLOWED_DOMAINS))
                raise URLValidationError(MESSAGES["domain"].format(
                    field_name="Webhook URL",
                    domains=domains_str
                ))

            # Validate webhook path format
            if not parsed.path.startswith(WEBHOOK_PATH_PREFIX):
                raise URLValidationError(MESSAGES["webhook_path"])

            path_parts = parsed.path.strip("/").split("/")
            if len(path_parts) != 4 or path_parts[0:2] != ["api", "webhooks"]:
                raise URLValidationError(MESSAGES["webhook_path"])

            webhook_id, token = path_parts[2:4]
            if not webhook_id.isdigit():
                raise URLValidationError(MESSAGES["webhook_id"])

            if not WEBHOOK_TOKEN_PATTERN.match(token):
                raise URLValidationError(MESSAGES["webhook_token"])

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
            allowed_schemes=list(ALLOWED_SCHEMES),
            required=False
        )
        if not url_str:
            return None

        # Check URL length
        if len(url_str) > MAX_URL_LENGTH:
            raise URLValidationError(MESSAGES["url_length"].format(
                field_name="Avatar URL",
                max_length=MAX_URL_LENGTH
            ))

        parsed = urlparse(url_str)
        if not any(domain in parsed.netloc for domain in cls.ALLOWED_AVATAR_DOMAINS):
            domains_str = ", ".join(sorted(cls.ALLOWED_AVATAR_DOMAINS))
            raise URLValidationError(MESSAGES["domain"].format(
                field_name="Avatar URL",
                domains=domains_str
            ))

        # Validate file extension
        if not any(parsed.path.lower().endswith(ext) for ext in ALLOWED_IMAGE_EXTENSIONS):
            raise URLValidationError(MESSAGES["image_format"].format(
                field_name="Avatar URL"
            ))

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
            raise ValidationError(MESSAGES["url_length"].format(
                field_name="Username",
                max_length=ApiLimits.USERNAME_LENGTH
            ))

        if not USERNAME_PATTERN.match(username):
            raise ValidationError(MESSAGES["username_format"])

        return username

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
            raise ValidationError(MESSAGES["url_length"].format(
                field_name="Thread name",
                max_length=ApiLimits.CHANNEL_NAME_LENGTH
            ))

        if not name.strip():
            raise ValidationError(MESSAGES["empty_content"].format(
                field_name="Thread name"
            ))

        if not THREAD_NAME_PATTERN.match(name):
            raise ValidationError(MESSAGES["thread_name_format"])

        return name

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
