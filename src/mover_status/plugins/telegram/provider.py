"""Telegram notification provider implementation.

This module implements the NotificationProvider Protocol for Telegram by
connecting the Telegram-specific configuration schema, formatter, and API
client components. Responsibilities (Requirements 9.1–9.4) include:
- Validating provider configuration (Requirement 3.5)
- Formatting notification payloads using TelegramFormatter
- Delivering messages via TelegramAPIClient with error handling
- Tracking provider health for the plugin registry
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Final

from mover_status.plugins.telegram.client import (
    TelegramAPIClient,
    TelegramAPIError,
    TelegramBotBlockedError,
    TelegramChatNotFoundError,
)
from mover_status.plugins.telegram.config import TelegramConfig
from mover_status.plugins.telegram.formatter import TelegramFormatter
from mover_status.types.models import HealthStatus, NotificationData, NotificationResult
from mover_status.types.protocols import HTTPClient
from mover_status.utils.template import load_template

__all__ = ["TelegramProvider", "create_provider"]

_DEFAULT_TEMPLATE: Final[str] = "Progress {percent}% | Remaining {remaining_data} | Rate {rate} | ETA {etc}"
_PROVIDER_NAME: Final[str] = "Telegram"


def _should_retry_telegram_error(error: TelegramAPIError) -> bool:
    """Return True if the Telegram error should trigger a retry."""
    if isinstance(error, (TelegramChatNotFoundError, TelegramBotBlockedError)):
        return False
    if error.retry_after is not None:
        return True
    if error.status in (408, 429):
        return True
    if error.status == 0:
        return True
    return error.status >= 500


@dataclass(slots=True)
class TelegramProvider:
    """Telegram notification provider implementation."""

    config: TelegramConfig
    http_client: HTTPClient
    template: str
    footer: str | None = None
    formatter: TelegramFormatter = field(init=False, repr=False)
    client: TelegramAPIClient = field(init=False, repr=False)
    _consecutive_failures: int = field(default=0, init=False, repr=False)
    _last_check: datetime = field(
        default_factory=lambda: datetime.now(UTC),
        init=False,
        repr=False,
    )
    _logger: logging.Logger = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize formatter, API client, and logger."""
        self.formatter = TelegramFormatter()
        self.client = TelegramAPIClient(
            config=self.config,
            http_client=self.http_client,
        )
        self._logger = logging.getLogger(__name__)

    async def send_notification(self, data: NotificationData) -> NotificationResult:
        """Deliver a notification to Telegram."""
        start_time = time.perf_counter()

        try:
            message = self.formatter.build_message(
                data,
                template=self.template,
                footer=self.footer,
            )
            _ = await self.client.send_message(text=message)

            delivery_time_ms = (time.perf_counter() - start_time) * 1000.0
            self._consecutive_failures = 0
            self._last_check = datetime.now(UTC)

            self._logger.info(
                "Telegram notification delivered successfully (correlation_id=%s, delivery_time=%.2fms)",
                data.correlation_id,
                delivery_time_ms,
            )

            return NotificationResult(
                success=True,
                provider_name=_PROVIDER_NAME,
                error_message=None,
                delivery_time_ms=delivery_time_ms,
            )

        except TelegramAPIError as exc:
            delivery_time_ms = (time.perf_counter() - start_time) * 1000.0
            self._consecutive_failures += 1
            self._last_check = datetime.now(UTC)

            error_msg = f"Telegram API error (status={exc.status}): {exc}"
            should_retry = _should_retry_telegram_error(exc)
            self._logger.error(
                "Telegram notification failed: %s (correlation_id=%s, consecutive_failures=%d)",
                error_msg,
                data.correlation_id,
                self._consecutive_failures,
            )

            return NotificationResult(
                success=False,
                provider_name=_PROVIDER_NAME,
                error_message=error_msg,
                delivery_time_ms=delivery_time_ms,
                should_retry=should_retry,
            )

        except Exception as exc:  # pragma: no cover - defensive catch-all
            delivery_time_ms = (time.perf_counter() - start_time) * 1000.0
            self._consecutive_failures += 1
            self._last_check = datetime.now(UTC)

            error_msg = f"Unexpected error during Telegram notification: {type(exc).__name__}: {exc}"
            self._logger.error(
                "Telegram notification failed with unexpected error: %s (correlation_id=%s)",
                error_msg,
                data.correlation_id,
                exc_info=True,
            )

            return NotificationResult(
                success=False,
                provider_name=_PROVIDER_NAME,
                error_message=error_msg,
                delivery_time_ms=delivery_time_ms,
                should_retry=True,
            )

    def validate_config(self) -> bool:
        """Validate Telegram configuration and template."""
        try:
            if not self.config.bot_token:
                self._logger.error("Telegram bot_token is missing")
                return False
            if not self.config.chat_id:
                self._logger.error("Telegram chat_id is missing")
                return False
            if not self.template:
                self._logger.error("Telegram template is empty")
                return False

            # Ensure template uses known placeholders
            _ = load_template(self.template)
            return True

        except Exception as exc:  # pragma: no cover - defensive
            self._logger.error("Telegram config validation failed: %s", exc, exc_info=True)
            return False

    async def health_check(self) -> HealthStatus:
        """Return passive health status derived from delivery attempts."""
        is_healthy = self._consecutive_failures < 3
        error_message = None
        if not is_healthy:
            error_message = f"Telegram provider unhealthy after {self._consecutive_failures} consecutive failures"

        return HealthStatus(
            is_healthy=is_healthy,
            last_check=self._last_check,
            consecutive_failures=self._consecutive_failures,
            error_message=error_message,
        )


def create_provider(
    *,
    config: TelegramConfig,
    http_client: HTTPClient,
    template: str = _DEFAULT_TEMPLATE,
    footer: str | None = None,
) -> TelegramProvider:
    """Factory for creating TelegramProvider instances."""
    validated_template = load_template(template)

    return TelegramProvider(
        config=config,
        http_client=http_client,
        template=validated_template,
        footer=footer,
    )
