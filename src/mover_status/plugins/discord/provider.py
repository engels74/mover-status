"""Discord notification provider implementation.

This module implements the NotificationProvider Protocol for Discord webhooks,
wiring together the Discord-specific configuration, formatter, and API client
components to deliver mover status notifications.

Responsibilities (Requirement 9.4):
- Implement send_notification with timing measurement and error handling
- Implement validate_config for configuration validation
- Implement health_check for connectivity monitoring
- Wire together DiscordConfig, DiscordFormatter, and DiscordAPIClient
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Final

from mover_status.plugins.discord.client import DiscordAPIClient, DiscordAPIError
from mover_status.plugins.discord.config import DiscordConfig
from mover_status.plugins.discord.formatter import DiscordFormatter
from mover_status.types.models import HealthStatus, NotificationData, NotificationResult
from mover_status.types.protocols import HTTPClient
from mover_status.utils.template import load_template

__all__ = ["DiscordProvider", "create_provider"]

_DEFAULT_TEMPLATE: Final[str] = (
    "Progress: {percent}% | Remaining: {remaining_data} | Rate: {rate} | ETA: {etc}"
)
_PROVIDER_NAME: Final[str] = "Discord"


@dataclass(slots=True)
class DiscordProvider:
    """Discord notification provider implementing the NotificationProvider Protocol.

    This class wires together the Discord plugin components to deliver
    notifications to Discord webhooks with comprehensive error handling,
    timing measurement, and health monitoring.

    Attributes:
        config: Discord-specific configuration including webhook URL
        http_client: HTTP client for webhook delivery (injected dependency)
        template: Message template for embed descriptions
        formatter: Discord message formatter for building embeds
        client: Discord API client for webhook delivery
        _consecutive_failures: Counter for health monitoring
        _last_check: Timestamp of last health check
        _logger: Logger instance for diagnostic output
    """

    config: DiscordConfig
    http_client: HTTPClient
    template: str
    formatter: DiscordFormatter = field(init=False, repr=False)
    client: DiscordAPIClient = field(init=False, repr=False)
    _consecutive_failures: int = field(default=0, init=False, repr=False)
    _last_check: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc), init=False, repr=False
    )
    _logger: logging.Logger = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize formatter, client, and logger after dataclass construction."""
        self.formatter = DiscordFormatter()
        self.client = DiscordAPIClient(
            config=self.config,
            http_client=self.http_client,
        )
        self._logger = logging.getLogger(__name__)

    async def send_notification(self, data: NotificationData) -> NotificationResult:
        """Deliver notification to Discord webhook.

        Orchestrates the notification delivery flow:
        1. Build Discord embed using formatter
        2. Send webhook using API client
        3. Measure delivery timing
        4. Track success/failure for health monitoring

        Args:
            data: Notification payload containing transfer progress information

        Returns:
            Result of the delivery attempt including timing and error details
        """
        start_time = time.perf_counter()

        try:
            # Build Discord embed from notification data
            embed = self.formatter.build_embed(
                data,
                template=self.template,
                color_override=self.config.embed_color,
            )

            # Send webhook with embed
            _ = await self.client.send_webhook(embeds=[embed])

            # Measure delivery time in milliseconds
            delivery_time_ms = (time.perf_counter() - start_time) * 1000.0

            # Reset failure counter on success
            self._consecutive_failures = 0
            self._last_check = datetime.now(timezone.utc)

            self._logger.info(
                "Discord notification delivered successfully (correlation_id=%s, delivery_time=%.2fms)",
                data.correlation_id,
                delivery_time_ms,
            )

            return NotificationResult(
                success=True,
                provider_name=_PROVIDER_NAME,
                error_message=None,
                delivery_time_ms=delivery_time_ms,
            )

        except DiscordAPIError as exc:
            # Discord-specific API errors
            delivery_time_ms = (time.perf_counter() - start_time) * 1000.0
            self._consecutive_failures += 1
            self._last_check = datetime.now(timezone.utc)

            error_msg = f"Discord API error (status={exc.status}): {exc}"
            self._logger.error(
                "Discord notification failed: %s (correlation_id=%s, consecutive_failures=%d)",
                error_msg,
                data.correlation_id,
                self._consecutive_failures,
            )

            return NotificationResult(
                success=False,
                provider_name=_PROVIDER_NAME,
                error_message=error_msg,
                delivery_time_ms=delivery_time_ms,
            )

        except Exception as exc:  # pragma: no cover - defensive catch-all
            # Unexpected errors (network issues, JSON serialization, etc.)
            delivery_time_ms = (time.perf_counter() - start_time) * 1000.0
            self._consecutive_failures += 1
            self._last_check = datetime.now(timezone.utc)

            error_msg = f"Unexpected error during Discord notification: {type(exc).__name__}: {exc}"
            self._logger.error(
                "Discord notification failed with unexpected error: %s (correlation_id=%s)",
                error_msg,
                data.correlation_id,
                exc_info=True,
            )

            return NotificationResult(
                success=False,
                provider_name=_PROVIDER_NAME,
                error_message=error_msg,
                delivery_time_ms=delivery_time_ms,
            )

    def validate_config(self) -> bool:
        """Validate provider configuration.

        Verifies that the Discord configuration is valid and the provider
        can be initialized. Pydantic performs the majority of validation
        when the DiscordConfig is constructed, so this primarily serves
        as a double-check.

        Returns:
            True if configuration is valid and provider can be initialized
        """
        # Pydantic validation already ensures webhook_url is present and valid
        # This method exists to satisfy the NotificationProvider Protocol
        # and provide a hook for future validation logic
        try:
            # Check that webhook URL is present
            if not self.config.webhook_url:
                self._logger.error("Discord webhook_url is missing")
                return False

            # Check that template is valid
            if not self.template:
                self._logger.error("Discord template is empty")
                return False

            return True

        except Exception as exc:  # pragma: no cover - defensive
            self._logger.error("Discord config validation failed: %s", exc, exc_info=True)
            return False

    async def health_check(self) -> HealthStatus:
        """Verify provider connectivity and health.

        Returns the current health status based on recent delivery attempts.
        This implementation uses passive health monitoring (tracking failures
        from actual notification deliveries) rather than active probing
        (sending test webhooks) to avoid unnecessary Discord API calls.

        Returns:
            Current health status including failure tracking information
        """
        # Consider provider unhealthy after 3 consecutive failures
        is_healthy = self._consecutive_failures < 3

        error_message = None
        if not is_healthy:
            error_message = (
                f"Discord provider unhealthy after {self._consecutive_failures} "
                f"consecutive failures"
            )

        return HealthStatus(
            is_healthy=is_healthy,
            last_check=self._last_check,
            consecutive_failures=self._consecutive_failures,
            error_message=error_message,
        )


def create_provider(
    *,
    config: DiscordConfig,
    http_client: HTTPClient,
    template: str = _DEFAULT_TEMPLATE,
) -> DiscordProvider:
    """Factory function for creating DiscordProvider instances.

    This factory is called by the plugin loader with the necessary
    dependencies injected. The template can be customized per deployment.

    Args:
        config: Discord-specific configuration (keyword-only)
        http_client: HTTP client for webhook delivery (keyword-only)
        template: Message template for embed descriptions (default provided)

    Returns:
        Fully initialized DiscordProvider instance

    Raises:
        ValueError: If template validation fails

    Example:
        >>> config = DiscordConfig(webhook_url="https://discord.com/api/webhooks/123/abc")
        >>> http_client = SomeHTTPClient()
        >>> provider = create_provider(config=config, http_client=http_client)
    """
    # Validate template before creating provider
    validated_template = load_template(template)

    return DiscordProvider(
        config=config,
        http_client=http_client,
        template=validated_template,
    )
