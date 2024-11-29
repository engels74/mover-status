# notifications/providers/discord/validators.py

"""Discord webhook configuration validator."""

from typing import Any, Dict, Optional, Union
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
    DiscordColor,
)
from utils.validators import BaseProviderValidator, ValidationError


class DiscordValidationError(Exception):
    """Raised when Discord webhook validation fails."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Initialize validation error with context.

        Args:
            message: Error description
            context: Optional error context dictionary
        """
        super().__init__(message)
        self.context = context or {}


class DiscordValidator(BaseProviderValidator):
    """Validates Discord webhook configurations and message content."""

    # Use shared constants for domains
    ALLOWED_DOMAINS = WEBHOOK_DOMAINS
    ALLOWED_AVATAR_DOMAINS = ASSET_DOMAINS
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
                context={"url": url, "path": parsed.path}
            )

        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) != 4 or path_parts[0:2] != ["api", "webhooks"]:
            raise DiscordValidationError(
                "Invalid webhook path",
                context={"url": url, "path": parsed.path}
            )

        webhook_id, token = path_parts[2:4]
        if not webhook_id.isdigit():
            raise DiscordValidationError(
                "Invalid webhook ID",
                context={"url": url, "webhook_id": webhook_id}
            )

        if not WEBHOOK_TOKEN_PATTERN.match(token):
            raise DiscordValidationError(
                "Invalid webhook token",
                context={"url": url, "token": token}
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
                context={"url": url}
            )

        if parsed.scheme not in {"http", "https"}:
            raise DiscordValidationError(
                "Webhook URL must use HTTPS",
                context={"url": url, "scheme": parsed.scheme}
            )

        if parsed.netloc not in cls.ALLOWED_DOMAINS:
            raise DiscordValidationError(
                "Invalid webhook domain",
                context={"url": url, "domain": parsed.netloc}
            )

        # Check URL length
        if len(url) > MAX_URL_LENGTH:
            raise DiscordValidationError(
                "Webhook URL exceeds maximum length",
                context={
                    "url": url,
                    "length": len(url),
                    "max_length": MAX_URL_LENGTH
                }
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
                context={"url": url}
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
                context={"url": url}
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
                    context={"url": url}
                )

            if parsed.scheme not in {"http", "https"}:
                raise DiscordValidationError(
                    "Avatar URL must use HTTPS",
                    context={"url": url, "scheme": parsed.scheme}
                )

            if parsed.netloc not in cls.ALLOWED_AVATAR_DOMAINS:
                raise DiscordValidationError(
                    "Invalid avatar domain",
                    context={"url": url, "domain": parsed.netloc}
                )

            # Check URL length
            if len(url) > MAX_URL_LENGTH:
                raise DiscordValidationError(
                    "Avatar URL exceeds maximum length",
                    context={
                        "url": url,
                        "length": len(url),
                        "max_length": MAX_URL_LENGTH
                    }
                )

            # Validate file extension
            if not any(parsed.path.lower().endswith(ext) for ext in ALLOWED_IMAGE_EXTENSIONS):
                raise DiscordValidationError(
                    "Invalid avatar file extension",
                    context={"url": url, "extension": parsed.path.split(".")[-1]}
                )

            return url

        except Exception as err:
            raise DiscordValidationError(
                f"Avatar URL validation failed: {err}",
                context={"url": url}
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
                context={
                    "username": username,
                    "length": len(username),
                    "max_length": ApiLimits.USERNAME_LENGTH
                }
            )

        if not USERNAME_PATTERN.match(username):
            raise DiscordValidationError(
                "Invalid username format",
                context={"username": username}
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
                context={
                    "name": name,
                    "length": len(name),
                    "max_length": ApiLimits.CHANNEL_NAME_LENGTH
                }
            )

        if not name.strip():
            raise DiscordValidationError(
                "Thread name cannot be empty",
                context={"name": name}
            )

        if not THREAD_NAME_PATTERN.match(name):
            raise DiscordValidationError(
                "Invalid thread name format",
                context={"name": name}
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
                context={"color": color}
            )

        if not 0 <= color <= 0xFFFFFF:
            raise DiscordValidationError(
                "Embed color must be a valid hex color (0-0xFFFFFF)",
                context={"color": color}
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
                context={"rate_limit": rate_limit}
            )

        if rate_period < 1:
            raise DiscordValidationError(
                "Rate period must be at least 1 second",
                context={"rate_period": rate_period}
            )

        if rate_limit > ApiLimits.RATE_LIMIT_PER_SEC * rate_period:
            raise DiscordValidationError(
                "Rate limit exceeds Discord's maximum",
                context={
                    "rate_limit": rate_limit,
                    "rate_period": rate_period,
                    "max_rate": ApiLimits.RATE_LIMIT_PER_SEC * rate_period
                }
            )
