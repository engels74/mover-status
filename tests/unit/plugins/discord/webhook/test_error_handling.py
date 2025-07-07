"""Tests for Discord webhook error handling and rate limiting."""

from __future__ import annotations

import pytest
import time
from unittest.mock import MagicMock

import httpx

from mover_status.plugins.discord.webhook.error_handling import (
    DiscordApiError,
    DiscordErrorType,
    DiscordErrorClassifier,
    WebhookValidator,
    AdvancedRateLimiter,
    with_discord_error_handling,
)


class TestDiscordApiError:
    """Test cases for Discord API error class."""

    def test_error_creation(self) -> None:
        """Test creating a Discord API error."""
        error = DiscordApiError(
            DiscordErrorType.RATE_LIMITED,
            "Rate limited",
            status_code=429,
            retry_after=5.0
        )
        
        assert error.error_type == DiscordErrorType.RATE_LIMITED
        assert error.message == "Rate limited"
        assert error.status_code == 429
        assert error.retry_after == 5.0
        assert error.original_error is None

    def test_error_with_original_exception(self) -> None:
        """Test creating error with original exception."""
        original = ValueError("Original error")
        error = DiscordApiError(
            DiscordErrorType.NETWORK_ERROR,
            "Network failed",
            original_error=original
        )
        
        assert error.error_type == DiscordErrorType.NETWORK_ERROR
        assert error.message == "Network failed"
        assert error.original_error == original

    def test_error_string_representation(self) -> None:
        """Test string representation of error."""
        error = DiscordApiError(
            DiscordErrorType.INVALID_PAYLOAD,
            "Invalid payload"
        )
        
        assert str(error) == "Invalid payload"


class TestWebhookValidator:
    """Test cases for webhook validator."""

    def test_valid_webhook_url(self) -> None:
        """Test validation of valid webhook URL."""
        valid_url = "https://discord.com/api/webhooks/123456789012345678/abcdefghijklmnopqrstuvwxyz"
        
        # Should not raise exception
        WebhookValidator.validate_webhook_url(valid_url)

    def test_valid_webhook_url_discordapp(self) -> None:
        """Test validation of valid discordapp.com webhook URL."""
        valid_url = "https://discordapp.com/api/webhooks/123456789012345678/abcdefghijklmnopqrstuvwxyz"
        
        # Should not raise exception
        WebhookValidator.validate_webhook_url(valid_url)

    def test_invalid_scheme(self) -> None:
        """Test validation with invalid scheme."""
        invalid_url = "ftp://discord.com/api/webhooks/123456789012345678/token"
        
        with pytest.raises(DiscordApiError) as exc_info:
            WebhookValidator.validate_webhook_url(invalid_url)
        
        assert exc_info.value.error_type == DiscordErrorType.INVALID_WEBHOOK
        assert "HTTP or HTTPS" in exc_info.value.message

    def test_invalid_domain(self) -> None:
        """Test validation with invalid domain."""
        invalid_url = "https://example.com/api/webhooks/123456789012345678/token"
        
        with pytest.raises(DiscordApiError) as exc_info:
            WebhookValidator.validate_webhook_url(invalid_url)
        
        assert exc_info.value.error_type == DiscordErrorType.INVALID_WEBHOOK
        assert "Discord webhook" in exc_info.value.message

    def test_invalid_path(self) -> None:
        """Test validation with invalid path."""
        invalid_url = "https://discord.com/invalid/path"
        
        with pytest.raises(DiscordApiError) as exc_info:
            WebhookValidator.validate_webhook_url(invalid_url)
        
        assert exc_info.value.error_type == DiscordErrorType.INVALID_WEBHOOK
        assert "URL path format" in exc_info.value.message

    def test_missing_webhook_id(self) -> None:
        """Test validation with missing webhook ID."""
        invalid_url = "https://discord.com/api/webhooks/"
        
        with pytest.raises(DiscordApiError) as exc_info:
            WebhookValidator.validate_webhook_url(invalid_url)
        
        assert exc_info.value.error_type == DiscordErrorType.INVALID_WEBHOOK
        assert "ID or token" in exc_info.value.message

    def test_invalid_webhook_id_format(self) -> None:
        """Test validation with invalid webhook ID format."""
        invalid_url = "https://discord.com/api/webhooks/invalid-id/token"
        
        with pytest.raises(DiscordApiError) as exc_info:
            WebhookValidator.validate_webhook_url(invalid_url)
        
        assert exc_info.value.error_type == DiscordErrorType.INVALID_WEBHOOK
        assert "Invalid webhook ID" in exc_info.value.message

    def test_empty_webhook_token(self) -> None:
        """Test validation with empty webhook token."""
        invalid_url = "https://discord.com/api/webhooks/123456789012345678/"
        
        with pytest.raises(DiscordApiError) as exc_info:
            WebhookValidator.validate_webhook_url(invalid_url)
        
        assert exc_info.value.error_type == DiscordErrorType.INVALID_WEBHOOK
        assert "Invalid webhook token" in exc_info.value.message

    def test_valid_embed_payload(self) -> None:
        """Test validation of valid embed payload."""
        valid_payload = {
            "content": "Test message",
            "embeds": [
                {
                    "title": "Test Title",
                    "description": "Test description",
                    "fields": [
                        {"name": "Field 1", "value": "Value 1", "inline": True}
                    ]
                }
            ]
        }
        
        # Should not raise exception
        WebhookValidator.validate_embed_payload(valid_payload)

    def test_content_too_long(self) -> None:
        """Test validation with content too long."""
        invalid_payload = {
            "content": "x" * 2001  # Too long
        }
        
        with pytest.raises(DiscordApiError) as exc_info:
            WebhookValidator.validate_embed_payload(invalid_payload)
        
        assert exc_info.value.error_type == DiscordErrorType.INVALID_PAYLOAD
        assert "2000 characters" in exc_info.value.message

    def test_too_many_embeds(self) -> None:
        """Test validation with too many embeds."""
        invalid_payload = {
            "embeds": [{"title": f"Embed {i}"} for i in range(11)]  # Too many
        }
        
        with pytest.raises(DiscordApiError) as exc_info:
            WebhookValidator.validate_embed_payload(invalid_payload)
        
        assert exc_info.value.error_type == DiscordErrorType.INVALID_PAYLOAD
        assert "10 embeds" in exc_info.value.message

    def test_embed_title_too_long(self) -> None:
        """Test validation with embed title too long."""
        invalid_payload = {
            "embeds": [
                {
                    "title": "x" * 257,  # Too long
                    "description": "Test"
                }
            ]
        }
        
        with pytest.raises(DiscordApiError) as exc_info:
            WebhookValidator.validate_embed_payload(invalid_payload)
        
        assert exc_info.value.error_type == DiscordErrorType.INVALID_PAYLOAD
        assert "256 characters" in exc_info.value.message

    def test_embed_description_too_long(self) -> None:
        """Test validation with embed description too long."""
        invalid_payload = {
            "embeds": [
                {
                    "title": "Test",
                    "description": "x" * 4097  # Too long
                }
            ]
        }
        
        with pytest.raises(DiscordApiError) as exc_info:
            WebhookValidator.validate_embed_payload(invalid_payload)
        
        assert exc_info.value.error_type == DiscordErrorType.INVALID_PAYLOAD
        assert "4096 characters" in exc_info.value.message

    def test_too_many_fields(self) -> None:
        """Test validation with too many fields."""
        invalid_payload = {
            "embeds": [
                {
                    "title": "Test",
                    "fields": [
                        {"name": f"Field {i}", "value": f"Value {i}"}
                        for i in range(26)  # Too many
                    ]
                }
            ]
        }
        
        with pytest.raises(DiscordApiError) as exc_info:
            WebhookValidator.validate_embed_payload(invalid_payload)
        
        assert exc_info.value.error_type == DiscordErrorType.INVALID_PAYLOAD
        assert "25 fields" in exc_info.value.message

    def test_field_name_too_long(self) -> None:
        """Test validation with field name too long."""
        invalid_payload = {
            "embeds": [
                {
                    "title": "Test",
                    "fields": [
                        {"name": "x" * 257, "value": "Value"}  # Name too long
                    ]
                }
            ]
        }
        
        with pytest.raises(DiscordApiError) as exc_info:
            WebhookValidator.validate_embed_payload(invalid_payload)
        
        assert exc_info.value.error_type == DiscordErrorType.INVALID_PAYLOAD
        assert "Field name" in exc_info.value.message

    def test_field_value_too_long(self) -> None:
        """Test validation with field value too long."""
        invalid_payload = {
            "embeds": [
                {
                    "title": "Test",
                    "fields": [
                        {"name": "Field", "value": "x" * 1025}  # Value too long
                    ]
                }
            ]
        }
        
        with pytest.raises(DiscordApiError) as exc_info:
            WebhookValidator.validate_embed_payload(invalid_payload)
        
        assert exc_info.value.error_type == DiscordErrorType.INVALID_PAYLOAD
        assert "Field value" in exc_info.value.message

    def test_missing_field_name(self) -> None:
        """Test validation with missing field name."""
        invalid_payload = {
            "embeds": [
                {
                    "title": "Test",
                    "fields": [
                        {"value": "Value"}  # Missing name
                    ]
                }
            ]
        }
        
        with pytest.raises(DiscordApiError) as exc_info:
            WebhookValidator.validate_embed_payload(invalid_payload)
        
        assert exc_info.value.error_type == DiscordErrorType.INVALID_PAYLOAD
        assert "name" in exc_info.value.message and "value" in exc_info.value.message

    def test_no_content_or_embeds(self) -> None:
        """Test validation with no content or embeds."""
        invalid_payload: dict[str, object] = {}
        
        with pytest.raises(DiscordApiError) as exc_info:
            WebhookValidator.validate_embed_payload(invalid_payload)
        
        assert exc_info.value.error_type == DiscordErrorType.INVALID_PAYLOAD
        assert "content or embeds" in exc_info.value.message


class TestDiscordErrorClassifier:
    """Test cases for Discord error classifier."""

    def test_classify_rate_limit_error(self) -> None:
        """Test classification of rate limit error."""
        response = MagicMock()
        response.status_code = 429
        response.headers = {"Retry-After": "5.0"}
        
        error = DiscordErrorClassifier.classify_http_error(response)
        
        assert error.error_type == DiscordErrorType.RATE_LIMITED
        assert error.status_code == 429
        assert error.retry_after == 5.0

    def test_classify_rate_limit_error_no_header(self) -> None:
        """Test classification of rate limit error without Retry-After header."""
        response = MagicMock()
        response.status_code = 429
        response.headers = {}
        
        error = DiscordErrorClassifier.classify_http_error(response)
        
        assert error.error_type == DiscordErrorType.RATE_LIMITED
        assert error.retry_after == 1.0  # Default

    def test_classify_bad_request_error(self) -> None:
        """Test classification of bad request error."""
        response = MagicMock()
        response.status_code = 400
        
        error = DiscordErrorClassifier.classify_http_error(response)
        
        assert error.error_type == DiscordErrorType.INVALID_PAYLOAD
        assert error.status_code == 400

    def test_classify_unauthorized_error(self) -> None:
        """Test classification of unauthorized error."""
        response = MagicMock()
        response.status_code = 401
        
        error = DiscordErrorClassifier.classify_http_error(response)
        
        assert error.error_type == DiscordErrorType.MISSING_PERMISSIONS
        assert error.status_code == 401

    def test_classify_forbidden_error(self) -> None:
        """Test classification of forbidden error."""
        response = MagicMock()
        response.status_code = 403
        
        error = DiscordErrorClassifier.classify_http_error(response)
        
        assert error.error_type == DiscordErrorType.MISSING_PERMISSIONS
        assert error.status_code == 403

    def test_classify_not_found_error(self) -> None:
        """Test classification of not found error."""
        response = MagicMock()
        response.status_code = 404
        
        error = DiscordErrorClassifier.classify_http_error(response)
        
        assert error.error_type == DiscordErrorType.INVALID_WEBHOOK
        assert error.status_code == 404

    def test_classify_server_error(self) -> None:
        """Test classification of server error."""
        response = MagicMock()
        response.status_code = 500
        
        error = DiscordErrorClassifier.classify_http_error(response)
        
        assert error.error_type == DiscordErrorType.SERVER_ERROR
        assert error.status_code == 500

    def test_classify_unknown_error(self) -> None:
        """Test classification of unknown HTTP error."""
        response = MagicMock()
        response.status_code = 418  # I'm a teapot
        
        error = DiscordErrorClassifier.classify_http_error(response)
        
        assert error.error_type == DiscordErrorType.UNKNOWN_ERROR
        assert error.status_code == 418

    def test_classify_timeout_error(self) -> None:
        """Test classification of timeout error."""
        original_error = httpx.TimeoutException("Request timed out")
        
        error = DiscordErrorClassifier.classify_network_error(original_error)
        
        assert error.error_type == DiscordErrorType.TIMEOUT_ERROR
        assert error.original_error == original_error

    def test_classify_connection_error(self) -> None:
        """Test classification of connection error."""
        original_error = httpx.ConnectError("Connection failed")
        
        error = DiscordErrorClassifier.classify_network_error(original_error)
        
        assert error.error_type == DiscordErrorType.NETWORK_ERROR
        assert error.original_error == original_error

    def test_classify_network_error(self) -> None:
        """Test classification of network error."""
        original_error = httpx.NetworkError("Network failed")
        
        error = DiscordErrorClassifier.classify_network_error(original_error)
        
        assert error.error_type == DiscordErrorType.NETWORK_ERROR
        assert error.original_error == original_error

    def test_classify_unknown_network_error(self) -> None:
        """Test classification of unknown network error."""
        original_error = ValueError("Unknown error")
        
        error = DiscordErrorClassifier.classify_network_error(original_error)
        
        assert error.error_type == DiscordErrorType.UNKNOWN_ERROR
        assert error.original_error == original_error


class TestAdvancedRateLimiter:
    """Test cases for advanced rate limiter."""

    def test_init_with_defaults(self) -> None:
        """Test initialization with default values."""
        limiter = AdvancedRateLimiter()
        
        assert limiter.max_requests == 30
        assert limiter.time_window == 60.0
        assert limiter.burst_limit == 5
        assert limiter.adaptive_delay is True

    def test_init_with_custom_values(self) -> None:
        """Test initialization with custom values."""
        limiter = AdvancedRateLimiter(
            max_requests=10,
            time_window=30.0,
            burst_limit=3,
            adaptive_delay=False
        )
        
        assert limiter.max_requests == 10
        assert limiter.time_window == 30.0
        assert limiter.burst_limit == 3
        assert limiter.adaptive_delay is False

    @pytest.mark.asyncio
    async def test_acquire_within_limits(self) -> None:
        """Test acquiring when within limits."""
        limiter = AdvancedRateLimiter(max_requests=5, time_window=10.0)
        
        # Should acquire immediately
        start_time = time.time()
        await limiter.acquire()
        elapsed = time.time() - start_time
        
        assert elapsed < 0.1  # Should be very fast

    @pytest.mark.asyncio
    async def test_acquire_rate_limited(self) -> None:
        """Test acquiring when rate limited."""
        limiter = AdvancedRateLimiter(max_requests=1, time_window=1.0)
        
        # First request should be fast
        start_time = time.time()
        await limiter.acquire()
        first_elapsed = time.time() - start_time
        assert first_elapsed < 0.1
        
        # Second request should be delayed
        start_time = time.time()
        await limiter.acquire()
        second_elapsed = time.time() - start_time
        assert second_elapsed >= 0.9  # Should wait close to 1 second

    @pytest.mark.asyncio
    async def test_acquire_burst_limited(self) -> None:
        """Test acquiring when burst limited."""
        limiter = AdvancedRateLimiter(max_requests=100, burst_limit=2)
        
        # First two requests should be fast
        await limiter.acquire()
        await limiter.acquire()
        
        # Third request should be delayed due to burst limit
        start_time = time.time()
        await limiter.acquire()
        elapsed = time.time() - start_time
        assert elapsed >= 4.9  # Should wait close to 5 seconds

    @pytest.mark.asyncio
    async def test_adaptive_delay(self) -> None:
        """Test adaptive delay on consecutive rate limits."""
        limiter = AdvancedRateLimiter(max_requests=1, time_window=0.5, adaptive_delay=True)
        
        # Fill up the rate limit
        await limiter.acquire()
        
        # Next request should have adaptive delay
        start_time = time.time()
        await limiter.acquire()
        first_delay = time.time() - start_time
        
        # Next request should have even longer adaptive delay
        start_time = time.time()
        await limiter.acquire()
        second_delay = time.time() - start_time
        
        # Second delay should be longer due to adaptive mechanism
        assert second_delay > first_delay

    @pytest.mark.asyncio
    async def test_no_adaptive_delay(self) -> None:
        """Test disabled adaptive delay."""
        limiter = AdvancedRateLimiter(max_requests=1, time_window=0.5, adaptive_delay=False)
        
        # Fill up the rate limit
        await limiter.acquire()
        
        # Next two requests should have consistent delays
        start_time = time.time()
        await limiter.acquire()
        first_delay = time.time() - start_time
        
        start_time = time.time()
        await limiter.acquire()
        second_delay = time.time() - start_time
        
        # Delays should be similar (within 20% tolerance)
        assert abs(second_delay - first_delay) / first_delay < 0.2

    def test_get_stats(self) -> None:
        """Test getting rate limiter statistics."""
        limiter = AdvancedRateLimiter(max_requests=10, burst_limit=3)
        
        stats = limiter.get_stats()
        
        assert "requests_in_window" in stats
        assert "max_requests" in stats
        assert "burst_requests" in stats
        assert "burst_limit" in stats
        assert "consecutive_rate_limits" in stats
        assert "time_since_last_rate_limit" in stats
        
        assert stats["max_requests"] == 10
        assert stats["burst_limit"] == 3

    @pytest.mark.asyncio
    async def test_get_stats_with_requests(self) -> None:
        """Test getting statistics after making requests."""
        limiter = AdvancedRateLimiter(max_requests=10, burst_limit=3)
        
        # Make some requests
        await limiter.acquire()
        await limiter.acquire()
        
        stats = limiter.get_stats()
        
        assert stats["requests_in_window"] == 2
        assert stats["burst_requests"] == 2


class TestWithDiscordErrorHandling:
    """Test cases for Discord error handling decorator."""

    @pytest.mark.asyncio
    async def test_successful_operation(self) -> None:
        """Test decorator with successful operation."""
        @with_discord_error_handling(max_attempts=3)
        async def test_func() -> str:
            return "success"
        
        result = await test_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_non_retryable_error(self) -> None:
        """Test decorator with non-retryable error."""
        @with_discord_error_handling(max_attempts=3)
        async def test_func() -> str:
            raise DiscordApiError(
                DiscordErrorType.INVALID_WEBHOOK,
                "Invalid webhook"
            )
        
        with pytest.raises(DiscordApiError) as exc_info:
            _ = await test_func()
        
        assert exc_info.value.error_type == DiscordErrorType.INVALID_WEBHOOK

    @pytest.mark.asyncio
    async def test_retryable_error_with_success(self) -> None:
        """Test decorator with retryable error followed by success."""
        call_count = 0
        
        @with_discord_error_handling(max_attempts=3, backoff_factor=0.1)
        async def test_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise DiscordApiError(
                    DiscordErrorType.SERVER_ERROR,
                    "Server error"
                )
            return "success"
        
        result = await test_func()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_max_attempts_exceeded(self) -> None:
        """Test decorator when max attempts are exceeded."""
        @with_discord_error_handling(max_attempts=2, backoff_factor=0.1)
        async def test_func() -> str:
            raise DiscordApiError(
                DiscordErrorType.SERVER_ERROR,
                "Server error"
            )
        
        with pytest.raises(DiscordApiError) as exc_info:
            _ = await test_func()
        
        assert exc_info.value.error_type == DiscordErrorType.SERVER_ERROR

    @pytest.mark.asyncio
    async def test_rate_limit_with_retry_after(self) -> None:
        """Test decorator with rate limit and retry-after."""
        call_count = 0
        
        @with_discord_error_handling(max_attempts=3, respect_retry_after=True)
        async def test_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise DiscordApiError(
                    DiscordErrorType.RATE_LIMITED,
                    "Rate limited",
                    retry_after=0.1
                )
            return "success"
        
        start_time = time.time()
        result = await test_func()
        elapsed = time.time() - start_time
        
        assert result == "success"
        assert call_count == 2
        assert elapsed >= 0.1  # Should wait for retry-after

    @pytest.mark.asyncio
    async def test_http_error_conversion(self) -> None:
        """Test conversion of HTTP errors to Discord errors."""
        @with_discord_error_handling(max_attempts=2, backoff_factor=0.1)
        async def test_func() -> str:
            response = MagicMock()
            response.status_code = 404
            raise httpx.HTTPStatusError("Not found", request=MagicMock(), response=response)
        
        with pytest.raises(DiscordApiError) as exc_info:
            _ = await test_func()
        
        assert exc_info.value.error_type == DiscordErrorType.INVALID_WEBHOOK

    @pytest.mark.asyncio
    async def test_network_error_conversion(self) -> None:
        """Test conversion of network errors to Discord errors."""
        @with_discord_error_handling(max_attempts=2, backoff_factor=0.1)
        async def test_func() -> str:
            raise httpx.TimeoutException("Request timed out")
        
        with pytest.raises(DiscordApiError) as exc_info:
            _ = await test_func()
        
        assert exc_info.value.error_type == DiscordErrorType.TIMEOUT_ERROR

    @pytest.mark.asyncio
    async def test_unknown_error_retry(self) -> None:
        """Test retry behavior with unknown errors."""
        call_count = 0
        
        @with_discord_error_handling(max_attempts=3, backoff_factor=0.1)
        async def test_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Unknown error")
            return "success"
        
        result = await test_func()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_jitter_disabled(self) -> None:
        """Test decorator with jitter disabled."""
        call_count = 0
        
        @with_discord_error_handling(max_attempts=3, backoff_factor=0.1, jitter=False)
        async def test_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise DiscordApiError(
                    DiscordErrorType.SERVER_ERROR,
                    "Server error"
                )
            return "success"
        
        result = await test_func()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_backoff_limit(self) -> None:
        """Test that backoff respects maximum limit."""
        call_count = 0
        
        @with_discord_error_handling(max_attempts=10, backoff_factor=10.0, max_backoff=0.1)
        async def test_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise DiscordApiError(
                    DiscordErrorType.SERVER_ERROR,
                    "Server error"
                )
            return "success"
        
        start_time = time.time()
        result = await test_func()
        elapsed = time.time() - start_time
        
        assert result == "success"
        # Even with high backoff factor, should be limited by max_backoff
        assert elapsed < 1.0  # Should be much less than what exponential backoff would give