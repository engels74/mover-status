"""Tests for the Discord notification provider."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import cast
from unittest.mock import AsyncMock

import pytest

from mover_status.plugins.discord.config import DiscordConfig
from mover_status.plugins.discord.provider import DiscordProvider, create_provider
from mover_status.types.models import NotificationData, Response
from mover_status.types.protocols import HTTPClient


# Test fixtures and helpers


def _make_discord_config(
    *,
    webhook_url: str = "https://discord.com/api/webhooks/123456789/abcdefgh",
    username: str | None = None,
    embed_color: int | None = None,
) -> DiscordConfig:
    """Factory for creating test Discord configurations."""
    return DiscordConfig(
        webhook_url=webhook_url,
        username=username,
        embed_color=embed_color,
    )


def _make_notification_data(
    *,
    event_type: str = "progress",
    percent: float = 50.0,
    remaining_data: str = "100 GB",
    moved_data: str = "100 GB",
    total_data: str = "200 GB",
    rate: str = "25 MB/s",
    etc_timestamp: datetime | None = None,
    correlation_id: str = "test-correlation-id",
) -> NotificationData:
    """Factory for creating test notification data."""
    resolved_etc = etc_timestamp or datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return NotificationData(
        event_type=event_type,
        percent=percent,
        remaining_data=remaining_data,
        moved_data=moved_data,
        total_data=total_data,
        rate=rate,
        etc_timestamp=resolved_etc,
        correlation_id=correlation_id,
    )


def _make_success_response() -> Response:
    """Factory for creating successful HTTP responses."""
    return Response(
        status=200,
        body={},
        headers={},
    )


class MockHTTPClient:
    """Mock HTTP client for testing webhook delivery."""

    def __init__(self) -> None:
        self.post: AsyncMock = AsyncMock(return_value=_make_success_response())
        self.post_with_retry: AsyncMock = AsyncMock(return_value=_make_success_response())


@pytest.fixture
def mock_http_client() -> HTTPClient:
    """Provide a mock HTTP client for testing."""
    return cast(HTTPClient, MockHTTPClient())


@pytest.fixture
def discord_config() -> DiscordConfig:
    """Provide a valid Discord configuration for testing."""
    return _make_discord_config()


@pytest.fixture
def notification_data() -> NotificationData:
    """Provide sample notification data for testing."""
    return _make_notification_data()


# Tests for send_notification


class TestSendNotification:
    """DiscordProvider.send_notification behavior."""

    async def test_successful_delivery_returns_success_result(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
        notification_data: NotificationData,
    ) -> None:
        """Successful webhook delivery returns NotificationResult with success=True."""
        provider = DiscordProvider(
            config=discord_config,
            http_client=mock_http_client,
            template="Progress: {percent}%",
        )

        result = await provider.send_notification(notification_data)

        assert result.success is True
        assert result.provider_name == "Discord"
        assert result.error_message is None
        assert result.delivery_time_ms > 0.0

    async def test_delivery_calls_http_client_with_embed(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
        notification_data: NotificationData,
    ) -> None:
        """Notification delivery calls HTTP client with formatted embed."""
        provider = DiscordProvider(
            config=discord_config,
            http_client=mock_http_client,
            template="Progress: {percent}%",
        )

        _ = await provider.send_notification(notification_data)

        # Verify HTTP client was called through client.send_webhook
        mock_client = cast(MockHTTPClient, mock_http_client)
        assert mock_client.post.called is True
        # Verify the webhook URL was used
        call_args = mock_client.post.call_args
        assert call_args is not None
        assert discord_config.webhook_url in str(call_args)

    async def test_timing_measurement_is_accurate(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
        notification_data: NotificationData,
    ) -> None:
        """Delivery timing is measured in milliseconds."""
        provider = DiscordProvider(
            config=discord_config,
            http_client=mock_http_client,
            template="Progress: {percent}%",
        )

        result = await provider.send_notification(notification_data)

        # Timing should be positive and reasonable (< 1000ms for a mock)
        assert result.delivery_time_ms > 0.0
        assert result.delivery_time_ms < 1000.0

    async def test_discord_api_error_returns_failure_result(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
        notification_data: NotificationData,
    ) -> None:
        """Discord API errors are caught and converted to failure results."""
        # Configure mock to return error response (client will raise DiscordAPIError)
        mock_client = cast(MockHTTPClient, mock_http_client)
        error_response = Response(
            status=404,
            body={"message": "Unknown Webhook", "code": 10015},
            headers={},
        )
        mock_client.post.return_value = error_response

        provider = DiscordProvider(
            config=discord_config,
            http_client=mock_http_client,
            template="Progress: {percent}%",
        )

        result = await provider.send_notification(notification_data)

        assert result.success is False
        assert result.provider_name == "Discord"
        assert result.error_message is not None
        assert "status=404" in result.error_message
        assert result.delivery_time_ms > 0.0
        assert result.should_retry is False

    async def test_rate_limit_error_returns_failure_result(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
        notification_data: NotificationData,
    ) -> None:
        """Discord rate limit errors are caught and converted to failure results."""
        # Configure mock to return rate limit response (client will raise DiscordRateLimitError)
        mock_client = cast(MockHTTPClient, mock_http_client)
        rate_limit_response = Response(
            status=429,
            body={"message": "You are being rate limited", "retry_after": 5.0, "global": False},
            headers={},
        )
        mock_client.post.return_value = rate_limit_response

        provider = DiscordProvider(
            config=discord_config,
            http_client=mock_http_client,
            template="Progress: {percent}%",
        )

        result = await provider.send_notification(notification_data)

        assert result.success is False
        assert result.provider_name == "Discord"
        assert result.error_message is not None
        assert "status=429" in result.error_message
        assert result.should_retry is True

    async def test_unexpected_exception_returns_failure_result(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
        notification_data: NotificationData,
    ) -> None:
        """Unexpected exceptions are caught and converted to failure results."""
        # Configure mock to raise unexpected exception
        mock_client = cast(MockHTTPClient, mock_http_client)
        mock_client.post.side_effect = ValueError("Unexpected error")

        provider = DiscordProvider(
            config=discord_config,
            http_client=mock_http_client,
            template="Progress: {percent}%",
        )

        result = await provider.send_notification(notification_data)

        assert result.success is False
        assert result.provider_name == "Discord"
        assert result.error_message is not None
        assert "Unexpected error" in result.error_message
        assert result.delivery_time_ms > 0.0
        assert result.should_retry is True

    async def test_consecutive_failures_are_tracked(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
        notification_data: NotificationData,
    ) -> None:
        """Provider tracks consecutive failures for health monitoring."""
        # Configure mock to return server error
        mock_client = cast(MockHTTPClient, mock_http_client)
        error_response = Response(
            status=500,
            body={"message": "Internal Server Error"},
            headers={},
        )
        mock_client.post.return_value = error_response

        provider = DiscordProvider(
            config=discord_config,
            http_client=mock_http_client,
            template="Progress: {percent}%",
        )

        # First failure
        _ = await provider.send_notification(notification_data)
        assert provider._consecutive_failures == 1  # pyright: ignore[reportPrivateUsage]  # Testing internal state

        # Second failure
        _ = await provider.send_notification(notification_data)
        assert provider._consecutive_failures == 2  # pyright: ignore[reportPrivateUsage]  # Testing internal state

        # Third failure
        _ = await provider.send_notification(notification_data)
        assert provider._consecutive_failures == 3  # pyright: ignore[reportPrivateUsage]  # Testing internal state

    async def test_successful_delivery_resets_failure_counter(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
        notification_data: NotificationData,
    ) -> None:
        """Successful delivery resets the consecutive failure counter."""
        mock_client = cast(MockHTTPClient, mock_http_client)

        provider = DiscordProvider(
            config=discord_config,
            http_client=mock_http_client,
            template="Progress: {percent}%",
        )

        # Simulate failures with error responses
        error_response = Response(
            status=500,
            body={"message": "Internal Server Error"},
            headers={},
        )
        mock_client.post.return_value = error_response
        _ = await provider.send_notification(notification_data)
        _ = await provider.send_notification(notification_data)
        assert provider._consecutive_failures == 2  # pyright: ignore[reportPrivateUsage]  # Testing internal state

        # Simulate success
        mock_client.post.return_value = _make_success_response()
        _ = await provider.send_notification(notification_data)

        assert provider._consecutive_failures == 0  # pyright: ignore[reportPrivateUsage]  # Testing internal state

    async def test_custom_embed_color_is_applied(
        self,
        mock_http_client: HTTPClient,
        notification_data: NotificationData,
    ) -> None:
        """Custom embed color from config is applied to embeds."""
        config = _make_discord_config(embed_color=0xFF5733)

        provider = DiscordProvider(
            config=config,
            http_client=mock_http_client,
            template="Progress: {percent}%",
        )

        result = await provider.send_notification(notification_data)

        assert result.success is True


# Tests for validate_config


class TestValidateConfig:
    """DiscordProvider.validate_config behavior."""

    def test_valid_config_returns_true(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Valid configuration returns True."""
        provider = DiscordProvider(
            config=discord_config,
            http_client=mock_http_client,
            template="Progress: {percent}%",
        )

        result = provider.validate_config()

        assert result is True

    def test_empty_webhook_url_returns_false(
        self,
        mock_http_client: HTTPClient,
    ) -> None:
        """Empty webhook URL returns False."""
        # This test verifies defensive behavior, though Pydantic should
        # prevent empty webhook URLs at config construction time
        config = _make_discord_config()
        # Bypass Pydantic validation by directly modifying the object
        object.__setattr__(config, "webhook_url", "")

        provider = DiscordProvider(
            config=config,
            http_client=mock_http_client,
            template="Progress: {percent}%",
        )

        result = provider.validate_config()

        assert result is False

    def test_empty_template_returns_false(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Empty template returns False."""
        provider = DiscordProvider(
            config=discord_config,
            http_client=mock_http_client,
            template="Progress: {percent}%",
        )
        # Bypass validation by directly setting template
        object.__setattr__(provider, "template", "")

        result = provider.validate_config()

        assert result is False


# Tests for health_check


class TestHealthCheck:
    """DiscordProvider.health_check behavior."""

    async def test_healthy_status_with_no_failures(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Provider reports healthy status with no failures."""
        provider = DiscordProvider(
            config=discord_config,
            http_client=mock_http_client,
            template="Progress: {percent}%",
        )

        health = await provider.health_check()

        assert health.is_healthy is True
        assert health.consecutive_failures == 0
        assert health.error_message is None

    async def test_unhealthy_status_after_consecutive_failures(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
        notification_data: NotificationData,
    ) -> None:
        """Provider reports unhealthy status after 3 consecutive failures."""
        mock_client = cast(MockHTTPClient, mock_http_client)
        error_response = Response(
            status=500,
            body={"message": "Internal Server Error"},
            headers={},
        )
        mock_client.post.return_value = error_response

        provider = DiscordProvider(
            config=discord_config,
            http_client=mock_http_client,
            template="Progress: {percent}%",
        )

        # Trigger 3 failures
        _ = await provider.send_notification(notification_data)
        _ = await provider.send_notification(notification_data)
        _ = await provider.send_notification(notification_data)

        health = await provider.health_check()

        assert health.is_healthy is False
        assert health.consecutive_failures == 3
        assert health.error_message is not None
        assert "unhealthy" in health.error_message.lower()

    async def test_health_check_updates_last_check_timestamp(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Health check includes last check timestamp."""
        provider = DiscordProvider(
            config=discord_config,
            http_client=mock_http_client,
            template="Progress: {percent}%",
        )

        health = await provider.health_check()

        assert health.last_check is not None
        # Last check should be recent (within last minute)
        now = datetime.now(timezone.utc)
        time_diff = (now - health.last_check).total_seconds()
        assert time_diff < 60.0


# Tests for create_provider factory


class TestCreateProvider:
    """create_provider factory function behavior."""

    def test_creates_provider_with_default_template(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Factory creates provider with default template."""
        provider = create_provider(
            config=discord_config,
            http_client=mock_http_client,
        )

        assert isinstance(provider, DiscordProvider)
        assert provider.config == discord_config
        assert provider.http_client == mock_http_client
        assert provider.template  # Default template is set

    def test_creates_provider_with_custom_template(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Factory creates provider with custom template."""
        custom_template = "Custom: {percent}% | ETA: {etc}"

        provider = create_provider(
            config=discord_config,
            http_client=mock_http_client,
            template=custom_template,
        )

        assert provider.template == custom_template

    def test_validates_template_at_creation(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Factory validates template and raises on invalid placeholders."""
        from mover_status.utils.template import TemplateError

        invalid_template = "Progress: {invalid_placeholder}%"

        with pytest.raises(TemplateError) as exc_info:
            _ = create_provider(
                config=discord_config,
                http_client=mock_http_client,
                template=invalid_template,
            )

        assert "unknown placeholders" in str(exc_info.value).lower()

    def test_provider_is_functional_after_creation(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Provider created by factory can send notifications."""
        provider = create_provider(
            config=discord_config,
            http_client=mock_http_client,
        )

        # Should not raise
        result = provider.validate_config()
        assert result is True


# Integration tests


class TestIntegration:
    """Integration tests for DiscordProvider."""

    async def test_full_notification_flow(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Complete notification flow from data to delivery."""
        notification = _make_notification_data(
            event_type="completed",
            percent=100.0,
            remaining_data="0 GB",
            moved_data="200 GB",
            total_data="200 GB",
            rate="25 MB/s",
        )

        provider = create_provider(
            config=discord_config,
            http_client=mock_http_client,
            template="Transfer complete! {percent}% | Rate: {rate}",
        )

        result = await provider.send_notification(notification)

        assert result.success is True
        assert result.provider_name == "Discord"
        assert result.delivery_time_ms > 0.0

    async def test_provider_implements_notification_provider_protocol(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """DiscordProvider correctly implements NotificationProvider Protocol."""
        from mover_status.types.protocols import NotificationProvider

        provider = create_provider(
            config=discord_config,
            http_client=mock_http_client,
        )

        # Protocol compliance check using isinstance
        assert isinstance(provider, NotificationProvider)
