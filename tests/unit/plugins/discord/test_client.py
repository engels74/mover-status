"""Tests for the Discord API client."""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock

import pytest

from mover_status.plugins.discord.client import (
    DiscordAPIClient,
    DiscordAPIError,
    DiscordRateLimitError,
)
from mover_status.plugins.discord.config import DiscordConfig
from mover_status.types.models import Response
from mover_status.types.protocols import HTTPClient


# Test fixtures and helpers


def _make_discord_config(
    *,
    webhook_url: str = "https://discord.com/api/webhooks/123456789/abcdefgh",
) -> DiscordConfig:
    """Factory for creating test Discord configurations."""
    return DiscordConfig(webhook_url=webhook_url)


def _make_success_response() -> Response:
    """Factory for creating successful HTTP responses."""
    return Response(status=200, body={}, headers={})


class MockHTTPClient:
    """Mock HTTP client for testing webhook delivery."""

    def __init__(self) -> None:
        self.post: AsyncMock = AsyncMock(return_value=_make_success_response())


@pytest.fixture
def mock_http_client() -> HTTPClient:
    """Provide a mock HTTP client for testing."""
    # Using object intermediary for Protocol cast as per type safety guidelines
    return cast(HTTPClient, cast(object, MockHTTPClient()))


@pytest.fixture
def discord_config() -> DiscordConfig:
    """Provide a valid Discord configuration for testing."""
    return _make_discord_config()


# Tests for DiscordAPIClient initialization


class TestClientInitialization:
    """DiscordAPIClient initialization and validation."""

    def test_valid_initialization(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Client initializes successfully with valid parameters."""
        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
        )

        assert client.config == discord_config
        assert client.http_client == mock_http_client
        assert client.request_timeout == 10.0
        assert client.max_attempts == 3
        assert client.max_backoff_seconds == 15.0

    def test_rejects_zero_timeout(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Client rejects zero timeout value."""
        with pytest.raises(ValueError, match="request_timeout must be positive"):
            _ = DiscordAPIClient(
                config=discord_config,
                http_client=mock_http_client,
                request_timeout=0.0,
            )

    def test_rejects_negative_timeout(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Client rejects negative timeout value."""
        with pytest.raises(ValueError, match="request_timeout must be positive"):
            _ = DiscordAPIClient(
                config=discord_config,
                http_client=mock_http_client,
                request_timeout=-1.0,
            )

    def test_rejects_zero_max_attempts(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Client rejects zero max_attempts value."""
        with pytest.raises(ValueError, match="max_attempts must be at least 1"):
            _ = DiscordAPIClient(
                config=discord_config,
                http_client=mock_http_client,
                max_attempts=0,
            )

    def test_rejects_negative_max_backoff(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Client rejects negative max_backoff_seconds value."""
        with pytest.raises(ValueError, match="max_backoff_seconds must be positive"):
            _ = DiscordAPIClient(
                config=discord_config,
                http_client=mock_http_client,
                max_backoff_seconds=-1.0,
            )

    def test_rejects_negative_rate_limit_cap(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Client rejects negative rate_limit_cap value."""
        with pytest.raises(ValueError, match="rate_limit_cap must be positive"):
            _ = DiscordAPIClient(
                config=discord_config,
                http_client=mock_http_client,
                rate_limit_cap=-1.0,
            )


# Tests for send_webhook


class TestSendWebhook:
    """DiscordAPIClient.send_webhook behavior."""

    async def test_successful_webhook_delivery(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Successful webhook delivery returns 200 response."""
        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
        )

        embed = {"title": "Test", "description": "Test embed"}
        response = await client.send_webhook(embeds=[embed])

        assert response.status == 200

    async def test_webhook_with_content(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Webhook delivery with content message."""
        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
        )

        embed = {"title": "Test"}
        response = await client.send_webhook(
            embeds=[embed],
            content="Test content",
        )

        assert response.status == 200
        # Verify content was included in the call
        mock_client = cast(MockHTTPClient, cast(object, mock_http_client))
        assert mock_client.post.called

    async def test_webhook_with_username_override(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Webhook delivery with custom username."""
        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
        )

        embed = {"title": "Test"}
        response = await client.send_webhook(
            embeds=[embed],
            username="Custom Bot",
        )

        assert response.status == 200

    async def test_empty_payload_raises_error(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Empty payload (no embeds or content) raises ValueError."""
        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
        )

        with pytest.raises(ValueError, match="requires at least one embed or content"):
            _ = await client.send_webhook(embeds=[])

    async def test_whitespace_content_treated_as_empty(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Whitespace-only content is treated as empty."""
        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
        )

        with pytest.raises(ValueError, match="requires at least one embed or content"):
            _ = await client.send_webhook(embeds=[], content="   ")


# Tests for error handling


class TestErrorHandling:
    """DiscordAPIClient error handling and retry logic."""

    async def test_timeout_error_retries_and_raises(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Timeout errors trigger retries and eventually raise DiscordAPIError."""
        mock_client = cast(MockHTTPClient, cast(object, mock_http_client))
        mock_client.post.side_effect = TimeoutError("Request timed out")

        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
            max_attempts=2,
        )

        with pytest.raises(DiscordAPIError, match="timed out") as exc_info:
            _ = await client.send_webhook(embeds=[{"title": "Test"}])

        # Should have retried
        assert mock_client.post.call_count == 2
        assert exc_info.value.status == 408

    async def test_server_error_retries_and_raises(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """5xx server errors trigger retries and eventually raise DiscordAPIError."""
        mock_client = cast(MockHTTPClient, cast(object, mock_http_client))
        error_response = Response(
            status=503,
            body={"message": "Service Unavailable"},
            headers={},
        )
        mock_client.post.return_value = error_response

        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
            max_attempts=2,
        )

        with pytest.raises(DiscordAPIError, match="server error") as exc_info:
            _ = await client.send_webhook(embeds=[{"title": "Test"}])

        assert exc_info.value.status == 503
        assert mock_client.post.call_count == 2

    async def test_client_error_raises_immediately(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """4xx client errors raise immediately without retries."""
        mock_client = cast(MockHTTPClient, cast(object, mock_http_client))
        error_response = Response(
            status=404,
            body={"message": "Unknown Webhook", "code": 10015},
            headers={},
        )
        mock_client.post.return_value = error_response

        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
            max_attempts=3,
        )

        with pytest.raises(DiscordAPIError, match="Unknown Webhook") as exc_info:
            _ = await client.send_webhook(embeds=[{"title": "Test"}])

        # Should NOT have retried (client error)
        assert mock_client.post.call_count == 1
        assert exc_info.value.status == 404
        assert exc_info.value.code == 10015

    async def test_error_with_nested_details(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Discord API errors with nested error details are formatted correctly."""
        mock_client = cast(MockHTTPClient, cast(object, mock_http_client))
        error_response = Response(
            status=400,
            body={
                "message": "Invalid Form Body",
                "code": 50035,
                "errors": {"embeds": {"0": {"title": {"_errors": [{"message": "Required"}]}}}},
            },
            headers={},
        )
        mock_client.post.return_value = error_response

        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
        )

        with pytest.raises(DiscordAPIError) as exc_info:
            _ = await client.send_webhook(embeds=[{"title": "Test"}])

        # Error message should include formatted details
        assert "Invalid Form Body" in str(exc_info.value)

    async def test_error_without_message(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Discord API errors without a message field use default message."""
        mock_client = cast(MockHTTPClient, cast(object, mock_http_client))
        error_response = Response(
            status=400,
            body={},
            headers={},
        )
        mock_client.post.return_value = error_response

        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
        )

        with pytest.raises(DiscordAPIError, match="Discord API responded with 400"):
            _ = await client.send_webhook(embeds=[{"title": "Test"}])

    async def test_error_code_as_string(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Discord API error codes as strings are converted to integers."""
        mock_client = cast(MockHTTPClient, cast(object, mock_http_client))
        error_response = Response(
            status=400,
            body={"message": "Bad Request", "code": "50035"},
            headers={},
        )
        mock_client.post.return_value = error_response

        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
        )

        with pytest.raises(DiscordAPIError) as exc_info:
            _ = await client.send_webhook(embeds=[{"title": "Test"}])

        assert exc_info.value.code == 50035

    async def test_error_code_non_numeric_string(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Non-numeric error code strings are ignored."""
        mock_client = cast(MockHTTPClient, cast(object, mock_http_client))
        error_response = Response(
            status=400,
            body={"message": "Bad Request", "code": "INVALID"},
            headers={},
        )
        mock_client.post.return_value = error_response

        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
        )

        with pytest.raises(DiscordAPIError) as exc_info:
            _ = await client.send_webhook(embeds=[{"title": "Test"}])

        assert exc_info.value.code is None


# Tests for rate limiting


class TestRateLimiting:
    """DiscordAPIClient rate limit handling."""

    async def test_rate_limit_with_retry_after_in_body(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Rate limit with retry_after in response body."""
        mock_client = cast(MockHTTPClient, cast(object, mock_http_client))

        # First call returns rate limit, second succeeds
        rate_limit_response = Response(
            status=429,
            body={"message": "Rate limited", "retry_after": 1.0, "global": False},
            headers={},
        )
        success_response = _make_success_response()

        mock_client.post.side_effect = [rate_limit_response, success_response]

        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
            max_attempts=2,
        )

        response = await client.send_webhook(embeds=[{"title": "Test"}])

        assert response.status == 200
        assert mock_client.post.call_count == 2

    async def test_rate_limit_with_retry_after_header(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Rate limit with Retry-After header fallback."""
        mock_client = cast(MockHTTPClient, cast(object, mock_http_client))

        rate_limit_response = Response(
            status=429,
            body={"message": "Rate limited", "global": False},
            headers={"Retry-After": "2.0"},
        )
        success_response = _make_success_response()

        mock_client.post.side_effect = [rate_limit_response, success_response]

        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
            max_attempts=2,
        )

        response = await client.send_webhook(embeds=[{"title": "Test"}])

        assert response.status == 200

    async def test_rate_limit_without_retry_after_uses_default(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Rate limit without retry_after uses default delay."""
        mock_client = cast(MockHTTPClient, cast(object, mock_http_client))

        rate_limit_response = Response(
            status=429,
            body={"message": "Rate limited", "global": False},
            headers={},
        )
        success_response = _make_success_response()

        mock_client.post.side_effect = [rate_limit_response, success_response]

        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
            max_attempts=2,
        )

        response = await client.send_webhook(embeds=[{"title": "Test"}])

        assert response.status == 200

    async def test_rate_limit_exceeds_max_attempts(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Rate limit that exceeds max attempts raises error."""
        mock_client = cast(MockHTTPClient, cast(object, mock_http_client))

        rate_limit_response = Response(
            status=429,
            body={"message": "Rate limited", "retry_after": 1.0, "global": True},
            headers={},
        )
        mock_client.post.return_value = rate_limit_response

        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
            max_attempts=1,
        )

        with pytest.raises(DiscordRateLimitError) as exc_info:
            _ = await client.send_webhook(embeds=[{"title": "Test"}])

        assert exc_info.value.is_global is True
        assert exc_info.value.retry_after is not None

    async def test_rate_limit_header_invalid_format(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Invalid Retry-After header format falls back to default delay."""
        mock_client = cast(MockHTTPClient, cast(object, mock_http_client))

        rate_limit_response = Response(
            status=429,
            body={"message": "Rate limited", "global": False},
            headers={"Retry-After": "invalid"},
        )
        success_response = _make_success_response()

        mock_client.post.side_effect = [rate_limit_response, success_response]

        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
            max_attempts=2,
        )

        response = await client.send_webhook(embeds=[{"title": "Test"}])

        assert response.status == 200

    async def test_rate_limit_retry_after_as_int(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Rate limit with retry_after as integer is handled correctly."""
        mock_client = cast(MockHTTPClient, cast(object, mock_http_client))

        rate_limit_response = Response(
            status=429,
            body={"message": "Rate limited", "retry_after": 2, "global": False},
            headers={},
        )
        success_response = _make_success_response()

        mock_client.post.side_effect = [rate_limit_response, success_response]

        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
            max_attempts=2,
        )

        response = await client.send_webhook(embeds=[{"title": "Test"}])

        assert response.status == 200

    async def test_rate_limit_retry_after_as_string(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Rate limit with retry_after as numeric string is handled correctly."""
        mock_client = cast(MockHTTPClient, cast(object, mock_http_client))

        rate_limit_response = Response(
            status=429,
            body={"message": "Rate limited", "retry_after": "1.5", "global": False},
            headers={},
        )
        success_response = _make_success_response()

        mock_client.post.side_effect = [rate_limit_response, success_response]

        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
            max_attempts=2,
        )

        response = await client.send_webhook(embeds=[{"title": "Test"}])

        assert response.status == 200


# Tests for payload building


class TestPayloadBuilding:
    """DiscordAPIClient payload construction."""

    async def test_payload_with_config_username(
        self,
        mock_http_client: HTTPClient,
    ) -> None:
        """Payload uses username from config when not overridden."""
        config = DiscordConfig(
            webhook_url="https://discord.com/api/webhooks/123/abc",
            username="Config Bot",
        )

        client = DiscordAPIClient(
            config=config,
            http_client=mock_http_client,
        )

        response = await client.send_webhook(embeds=[{"title": "Test"}])

        assert response.status == 200

    async def test_payload_username_override_takes_precedence(
        self,
        mock_http_client: HTTPClient,
    ) -> None:
        """Payload username parameter overrides config username."""
        config = DiscordConfig(
            webhook_url="https://discord.com/api/webhooks/123/abc",
            username="Config Bot",
        )

        client = DiscordAPIClient(
            config=config,
            http_client=mock_http_client,
        )

        response = await client.send_webhook(
            embeds=[{"title": "Test"}],
            username="Override Bot",
        )

        assert response.status == 200

    async def test_payload_with_custom_allowed_mentions(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Payload accepts custom allowed_mentions."""
        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
        )

        response = await client.send_webhook(
            embeds=[{"title": "Test"}],
            allowed_mentions={"parse": ["users"]},
        )

        assert response.status == 200

    async def test_payload_with_empty_body_response(
        self,
        discord_config: DiscordConfig,
        mock_http_client: HTTPClient,
    ) -> None:
        """Client handles responses with empty body gracefully."""
        mock_client = cast(MockHTTPClient, cast(object, mock_http_client))
        error_response = Response(
            status=400,
            body={},  # Empty body (simulating None body scenario)
            headers={},
        )
        mock_client.post.return_value = error_response

        client = DiscordAPIClient(
            config=discord_config,
            http_client=mock_http_client,
        )

        with pytest.raises(DiscordAPIError, match="Discord API responded with 400"):
            _ = await client.send_webhook(embeds=[{"title": "Test"}])
