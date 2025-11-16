"""Tests for the Telegram notification provider."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone

import pytest

from mover_status.plugins.telegram.config import TelegramConfig
from mover_status.plugins.telegram.provider import TelegramProvider
from mover_status.types.models import NotificationData, Response
from mover_status.types.protocols import HTTPClient


def _make_config(
    *,
    bot_token: str = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
    chat_id: str = "@moverstatus",
) -> TelegramConfig:
    """Create a valid Telegram configuration for tests."""
    return TelegramConfig(
        bot_token=bot_token,
        chat_id=chat_id,
        parse_mode="HTML",
        message_thread_id=None,
        disable_notification=False,
    )


def _make_notification_data(
    *,
    event_type: str = "progress",
    percent: float = 42.5,
    remaining_data: str = "150 GB",
    moved_data: str = "<danger>",
    total_data: str = "300 GB",
    rate: str = "120 MB/s",
    etc_timestamp: datetime | None = None,
    correlation_id: str = "test-correlation",
) -> NotificationData:
    """Create common NotificationData payloads."""
    resolved_timestamp = etc_timestamp or datetime(
        2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc
    )
    return NotificationData(
        event_type=event_type,
        percent=percent,
        remaining_data=remaining_data,
        moved_data=moved_data,
        total_data=total_data,
        rate=rate,
        etc_timestamp=resolved_timestamp,
        correlation_id=correlation_id,
    )


def _success_response() -> Response:
    """Return a successful HTTP response."""
    return Response(
        status=200,
        body={"ok": True},
        headers={},
    )


class RecordingHTTPClient:
    """Minimal HTTP client implementation used for assertions."""

    def __init__(self) -> None:
        self.response: Response = _success_response()
        self.exception: BaseException | None = None
        self.last_payload: Mapping[str, object] | None = None
        self.last_url: str | None = None
        self.last_timeout: float | None = None
        self.post_call_count: int = 0

    async def post(
        self,
        url: str,
        payload: Mapping[str, object],
        *,
        timeout: float,
    ) -> Response:
        self.last_url = url
        self.last_payload = payload
        self.last_timeout = timeout
        self.post_call_count += 1

        if self.exception is not None:
            raise self.exception
        return self.response

    async def post_with_retry(
        self,
        url: str,
        payload: Mapping[str, object],
    ) -> Response:
        return await self.post(url, payload, timeout=10.0)


@pytest.fixture
def telegram_config() -> TelegramConfig:
    """Provide valid Telegram configuration."""
    return _make_config()


@pytest.fixture
def notification_data() -> NotificationData:
    """Provide sample NotificationData."""
    return _make_notification_data()


@pytest.fixture
def http_client_recorder() -> RecordingHTTPClient:
    """Provide HTTP client recorder for assertions."""
    return RecordingHTTPClient()


@pytest.fixture
def http_client(http_client_recorder: RecordingHTTPClient) -> HTTPClient:
    """Expose HTTP client via protocol interface."""
    return http_client_recorder


class TestSendNotification:
    """TelegramProvider.send_notification behavior."""

    async def test_formats_html_message_with_template(
        self,
        telegram_config: TelegramConfig,
        http_client: HTTPClient,
        http_client_recorder: RecordingHTTPClient,
        notification_data: NotificationData,
    ) -> None:
        """Provider builds Telegram-ready HTML payloads with escaping."""
        provider = TelegramProvider(
            config=telegram_config,
            http_client=http_client,
            template="Progress {percent}% - Remaining {remaining_data}",
            footer="Cache -> Array",
        )

        _ = await provider.send_notification(notification_data)

        payload = http_client_recorder.last_payload
        assert payload is not None
        sent_text = payload["text"]
        assert isinstance(sent_text, str)
        assert sent_text.startswith("<b>Mover Progress</b>")
        assert "<b>Progress:</b> 42.5%" in sent_text
        assert "<b>Remaining:</b> 150 GB" in sent_text
        assert "&lt;danger&gt;" in sent_text  # HTML entities escaped
        assert "<b>ETA:</b> 2024-01-01 12:00 UTC" in sent_text
        assert sent_text.endswith("<i>Cache -&gt; Array</i>")

    async def test_successful_delivery_returns_success_result(
        self,
        telegram_config: TelegramConfig,
        http_client: HTTPClient,
        http_client_recorder: RecordingHTTPClient,
        notification_data: NotificationData,
    ) -> None:
        """Successful delivery returns NotificationResult with success metadata."""
        provider = TelegramProvider(
            config=telegram_config,
            http_client=http_client,
            template="Progress {percent}%",
        )

        result = await provider.send_notification(notification_data)

        assert result.success is True
        assert result.provider_name == "Telegram"
        assert result.error_message is None
        assert result.delivery_time_ms > 0.0
        assert http_client_recorder.post_call_count == 1


class TestValidateConfig:
    """TelegramProvider.validate_config behavior."""

    def test_valid_configuration_returns_true(
        self,
        telegram_config: TelegramConfig,
        http_client: HTTPClient,
    ) -> None:
        """Valid configs and templates validate successfully."""
        provider = TelegramProvider(
            config=telegram_config,
            http_client=http_client,
            template="Progress {percent}%",
        )

        assert provider.validate_config() is True

    def test_missing_template_returns_false(
        self,
        telegram_config: TelegramConfig,
        http_client: HTTPClient,
    ) -> None:
        """Empty template strings are rejected."""
        provider = TelegramProvider(
            config=telegram_config,
            http_client=http_client,
            template="",
        )

        assert provider.validate_config() is False


class TestErrorHandling:
    """Failure scenarios and health tracking."""

    async def test_api_error_marks_provider_unhealthy_after_retries(
        self,
        telegram_config: TelegramConfig,
        http_client: HTTPClient,
        http_client_recorder: RecordingHTTPClient,
        notification_data: NotificationData,
    ) -> None:
        """Consecutive API errors produce failure results and unhealthy health status."""
        provider = TelegramProvider(
            config=telegram_config,
            http_client=http_client,
            template="Progress {percent}%",
        )
        http_client_recorder.response = Response(
            status=403,
            body={"description": "Forbidden"},
            headers={},
        )

        for _ in range(3):
            result = await provider.send_notification(notification_data)
            assert result.success is False
            assert "status=403" in (result.error_message or "")
            assert result.should_retry is False

        health = await provider.health_check()
        assert health.is_healthy is False
        assert provider._consecutive_failures == 3  # pyright: ignore[reportPrivateUsage]  # Testing internal state
        assert "consecutive failures" in (health.error_message or "")

    async def test_rate_limit_error_sets_retry_flag(
        self,
        telegram_config: TelegramConfig,
        http_client: HTTPClient,
        http_client_recorder: RecordingHTTPClient,
        notification_data: NotificationData,
    ) -> None:
        """Telegram rate limit responses should be marked retryable."""
        provider = TelegramProvider(
            config=telegram_config,
            http_client=http_client,
            template="Progress {percent}%",
        )
        http_client_recorder.response = Response(
            status=429,
            body={"description": "Too Many Requests", "parameters": {"retry_after": 5}},
            headers={},
        )

        result = await provider.send_notification(notification_data)

        assert result.success is False
        assert result.should_retry is True
        assert "status=429" in (result.error_message or "")
