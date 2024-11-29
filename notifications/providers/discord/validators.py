# notifications/providers/discord/validators.py

"""Discord webhook configuration validator."""

from typing import Any, Dict, Final, Optional, Union
from urllib.parse import ParseResult, urlparse

from pydantic import HttpUrl

from config.constants import JsonDict
from shared.providers.discord import (
    ALLOWED_IMAGE_EXTENSIONS,
    ASSET_DOMAINS,
    MAX_URL_LENGTH,
    THREAD_NAME_PATTERN,
    USERNAME_PATTERN,
    WEBHOOK_DOMAINS,
    WEBHOOK_PATH_PREFIX,
    WEBHOOK_TOKEN_PATTERN,
    ApiLimits,
    AssetDomains,
    DiscordColor,
    WebhookDomains,
    validate_url,
)
from utils.validators import BaseProviderValidator, ValidationError


class DiscordValidationError(Exception):
    """Raised when Discord webhook validation fails."""

    def __init__(self, message: str, field: Optional[str] = None):
        """Initialize Discord validation error.

        Args:
            message: Error message
            field: Field that caused the error
        """
        super().__init__(message)
        self.field = field


class DiscordValidator(BaseProviderValidator):
    """Validates Discord webhook configurations and message content."""

    # Use shared constants for domains
    ALLOWED_DOMAINS: Final[WebhookDomains] = WEBHOOK_DOMAINS
    ALLOWED_AVATAR_DOMAINS: Final[AssetDomains] = ASSET_DOMAINS
    DEFAULT_COLOR = DiscordColor.INFO

    @classmethod
    def _validate_webhook_path(
        cls,
        url: str,
        parsed: ParseResult
    ) -> None:
        """Validate webhook path format.

        Args:
            url: Full webhook URL
            parsed: Parsed URL components

        Raises:
            DiscordValidationError: If path format is invalid
        """
        if not parsed.path.startswith(WEBHOOK_PATH_PREFIX):
            raise DiscordValidationError(
                "Invalid webhook path",
                field="webhook_url"
            )

        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) != 4 or path_parts[0:2] != ["api", "webhooks"]:
            raise DiscordValidationError(
                "Invalid webhook path",
                field="webhook_url"
            )

        webhook_id, token = path_parts[2:4]
        if not webhook_id.isdigit():
            raise DiscordValidationError(
                "Invalid webhook ID",
                field="webhook_url"
            )

        if not WEBHOOK_TOKEN_PATTERN.match(token):
            raise DiscordValidationError(
                "Invalid webhook token",
                field="webhook_url"
            )

    @classmethod
    def _validate_webhook_url_format(
        cls,
        url: str,
        parsed: ParseResult
    ) -> None:
        """Validate webhook URL format.

        Args:
            url: Full webhook URL
            parsed: Parsed URL components

        Raises:
            DiscordValidationError: If URL format is invalid
        """
        if not all([parsed.scheme, parsed.netloc, parsed.path]):
            raise DiscordValidationError(
                "Invalid webhook URL format",
                field="webhook_url"
            )

        if parsed.scheme not in {"http", "https"}:
            raise DiscordValidationError(
                "Webhook URL must use HTTPS",
                field="webhook_url"
            )

        if parsed.netloc not in cls.ALLOWED_DOMAINS:
            raise DiscordValidationError(
                "Invalid webhook domain",
                field="webhook_url"
            )

        # Check URL length
        if len(url) > MAX_URL_LENGTH:
            raise DiscordValidationError(
                "Webhook URL exceeds maximum length",
                field="webhook_url"
            )

    @classmethod
    def validate_webhook_url(
        cls,
        url: Optional[str],
        required: bool = True
    ) -> Optional[str]:
        """Validate Discord webhook URL.

        Args:
            url: Webhook URL to validate
            required: If True, URL is required

        Returns:
            Optional[str]: Validated webhook URL or None

        Raises:
            DiscordValidationError: If webhook URL is invalid
        """
        if not url and required:
            raise DiscordValidationError(
                "Webhook URL is required",
                field="webhook_url"
            )
        elif not url:
            return None

        try:
            parsed = urlparse(url)
            # Validate basic URL format
            cls._validate_webhook_url_format(url, parsed)
            # Validate webhook path components
            cls._validate_webhook_path(url, parsed)

            return url

        except Exception as err:
            raise DiscordValidationError(
                f"Webhook URL validation failed: {err}",
                field="webhook_url"
            ) from err

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
            DiscordValidationError: If avatar URL is invalid
        """
        if not url:
            return None

        try:
            parsed = urlparse(url)
            if not all([parsed.scheme, parsed.netloc, parsed.path]):
                raise DiscordValidationError(
                    "Invalid avatar URL format",
                    field="avatar_url"
                )

            if parsed.scheme not in {"http", "https"}:
                raise DiscordValidationError(
                    "Avatar URL must use HTTPS",
                    field="avatar_url"
                )

            if parsed.netloc not in cls.ALLOWED_AVATAR_DOMAINS:
                raise DiscordValidationError(
                    "Invalid avatar domain",
                    field="avatar_url"
                )

            # Check URL length
            if len(url) > MAX_URL_LENGTH:
                raise DiscordValidationError(
                    "Avatar URL exceeds maximum length",
                    field="avatar_url"
                )

            # Validate file extension
            if not any(parsed.path.lower().endswith(ext) for ext in ALLOWED_IMAGE_EXTENSIONS):
                raise DiscordValidationError(
                    "Invalid avatar file extension",
                    field="avatar_url"
                )

            return url

        except Exception as err:
            raise DiscordValidationError(
                f"Avatar URL validation failed: {err}",
                field="avatar_url"
            ) from err

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
            DiscordValidationError: If username is invalid
        """
        if not username:
            return default

        if len(username) > ApiLimits.USERNAME_LENGTH:
            raise DiscordValidationError(
                "Username exceeds maximum length",
                field="username"
            )

        if not USERNAME_PATTERN.match(username):
            raise DiscordValidationError(
                "Invalid username format",
                field="username"
            )

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
            DiscordValidationError: If thread name is invalid
        """
        if not name:
            return None

        if len(name) > ApiLimits.CHANNEL_NAME_LENGTH:
            raise DiscordValidationError(
                "Thread name exceeds maximum length",
                field="thread_name"
            )

        if not name.strip():
            raise DiscordValidationError(
                "Thread name cannot be empty",
                field="thread_name"
            )

        if not THREAD_NAME_PATTERN.match(name):
            raise DiscordValidationError(
                "Invalid thread name format",
                field="thread_name"
            )

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
            DiscordValidationError: If color is invalid
        """
        if color is None:
            return cls.DEFAULT_COLOR

        if not isinstance(color, int):
            raise DiscordValidationError(
                "Embed color must be an integer",
                field="embed_color"
            )

        if not 0 <= color <= 0xFFFFFF:
            raise DiscordValidationError(
                "Embed color must be a valid hex color (0-0xFFFFFF)",
                field="embed_color"
            )

        return color

    def validate_config(self, config: Dict[str, Any]) -> JsonDict:
        """Validate complete Discord webhook configuration.

        Args:
            config: Configuration dictionary to validate

        Returns:
            JsonDict: Validated configuration dictionary

        Raises:
            DiscordValidationError: If configuration is invalid
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

    @classmethod
    def validate_rate_limits(
        cls,
        rate_limit: int,
        rate_period: int
    ) -> None:
        """Validate rate limit configuration.

        Args:
            rate_limit: Maximum requests per period
            rate_period: Time period in seconds

        Raises:
            DiscordValidationError: If rate limits are invalid
        """
        if rate_limit < 1:
            raise DiscordValidationError(
                "Rate limit must be at least 1",
                field="rate_limit"
            )

        if rate_period < 1:
            raise DiscordValidationError(
                "Rate period must be at least 1 second",
                field="rate_period"
            )

        if rate_limit > ApiLimits.RATE_LIMIT_PER_SEC * rate_period:
            raise DiscordValidationError(
                "Rate limit exceeds Discord's maximum",
                field="rate_limit"
            )

class WebhookValidator:
    """Discord webhook URL and payload validator."""

    ALLOWED_DOMAINS: Final[WebhookDomains] = WEBHOOK_DOMAINS
    ALLOWED_ASSET_DOMAINS: Final[AssetDomains] = ASSET_DOMAINS

    @classmethod
    def validate_webhook_url(cls, url: str) -> bool:
        """Validate Discord webhook URL.

        Args:
            url: Discord webhook URL to validate

        Returns:
            bool: True if URL is valid Discord webhook URL
        """
        return validate_url(url, cls.ALLOWED_DOMAINS)

    @classmethod
    def validate_avatar_url(cls, url: Optional[str]) -> bool:
        """Validate avatar URL.

        Args:
            url: Avatar URL to validate

        Returns:
            bool: True if URL is valid avatar URL or None
        """
        if url is None:
            return True
        return validate_url(url, cls.ALLOWED_ASSET_DOMAINS)
