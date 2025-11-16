"""Unit tests for HTTP client abstraction.

Tests cover:
- Basic POST requests
- Timeout handling
- Retry logic for various error conditions
- Exponential backoff with jitter
- Circuit breaker state transitions
- Retry-After header parsing
- Resource cleanup
"""

import asyncio
import logging
from collections.abc import Mapping
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

from mover_status.utils.http_client import AIOHTTPClient, CircuitState, DryRunHTTPClient


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create mock aiohttp ClientSession."""
    session = AsyncMock(spec=aiohttp.ClientSession)
    return session


@pytest.fixture
def mock_response() -> AsyncMock:
    """Create mock aiohttp ClientResponse."""
    response = AsyncMock()
    response.status = 200
    response.json = AsyncMock(return_value={"success": True})
    response.headers = {"Content-Type": "application/json"}
    return response


@pytest.fixture
async def client() -> AIOHTTPClient:
    """Create AIOHTTPClient instance for testing."""
    return AIOHTTPClient(
        max_retries=3,
        max_backoff_seconds=10.0,
        default_timeout_seconds=5.0,
        jitter_percent=20.0,
        circuit_breaker_threshold=5,
        circuit_breaker_cooldown_seconds=30.0,
    )


class TestAIOHTTPClientBasics:
    """Test basic HTTP client functionality."""

    async def test_context_manager_creates_session(self) -> None:
        """Test that async context manager creates aiohttp session."""
        client = AIOHTTPClient()

        async with client:
            assert client._session is not None  # pyright: ignore[reportPrivateUsage]  # testing internal state
            assert isinstance(client._session, aiohttp.ClientSession)  # pyright: ignore[reportPrivateUsage]  # testing internal state

        # Session should be closed after context exit
        assert client._session is None  # pyright: ignore[reportPrivateUsage]  # testing internal state

    async def test_context_manager_closes_session_on_error(self) -> None:
        """Test that session is closed even when exception occurs."""
        client = AIOHTTPClient()

        try:
            async with client:
                assert client._session is not None  # pyright: ignore[reportPrivateUsage]  # testing internal state
                raise ValueError("Test error")
        except ValueError:
            pass

        # Session should still be closed
        assert client._session is None  # pyright: ignore[reportPrivateUsage]  # testing internal state

    async def test_post_without_session_raises_error(self, client: AIOHTTPClient) -> None:
        """Test that post() raises error if session not initialized."""
        with pytest.raises(RuntimeError, match="session not initialized"):
            _ = await client.post("https://example.com", {}, timeout=5.0)


class TestPostMethod:
    """Test basic POST method functionality."""

    async def test_post_success(self, client: AIOHTTPClient, mock_session: AsyncMock, mock_response: AsyncMock) -> None:
        """Test successful POST request."""
        # Setup mock
        mock_session.post.return_value.__aenter__.return_value = mock_response  # pyright: ignore[reportAny]  # mock object
        client._session = mock_session  # pyright: ignore[reportPrivateUsage]  # testing internal state

        # Execute
        response = await client.post(
            "https://example.com/webhook",
            {"message": "test"},
            timeout=5.0,
        )

        # Verify
        assert response.status == 200
        assert response.body == {"success": True}
        mock_session.post.assert_called_once()  # pyright: ignore[reportAny]  # mock method

    async def test_post_timeout(self, client: AIOHTTPClient, mock_session: AsyncMock) -> None:
        """Test POST request timeout handling."""
        # Setup mock to simulate timeout
        async def slow_request(*args: object, **kwargs: object) -> None:  # pyright: ignore[reportUnusedParameter]
            await asyncio.sleep(10)  # Longer than timeout

        mock_session.post.return_value.__aenter__.side_effect = slow_request  # pyright: ignore[reportAny]  # mock object
        client._session = mock_session  # pyright: ignore[reportPrivateUsage]  # testing internal state

        # Execute and verify timeout
        with pytest.raises(TimeoutError):
            _ = await client.post("https://example.com/webhook", {}, timeout=0.1)

    async def test_post_invalid_url(self, client: AIOHTTPClient, mock_session: AsyncMock) -> None:
        """Test POST with invalid URL raises ValueError."""
        # Setup mock to raise InvalidURL
        mock_session.post.side_effect = aiohttp.InvalidURL("invalid")  # pyright: ignore[reportAny]  # mock object
        client._session = mock_session  # pyright: ignore[reportPrivateUsage]  # testing internal state

        # Execute and verify
        with pytest.raises(ValueError, match="Malformed URL"):
            _ = await client.post("invalid-url", {}, timeout=5.0)

    async def test_post_connection_error(self, client: AIOHTTPClient, mock_session: AsyncMock) -> None:
        """Test POST with connection error propagates exception."""
        # Setup mock to raise connection error
        mock_session.post.side_effect = aiohttp.ClientConnectionError("Connection refused")  # pyright: ignore[reportAny]  # mock object
        client._session = mock_session  # pyright: ignore[reportPrivateUsage]  # testing internal state

        # Execute and verify
        with pytest.raises(aiohttp.ClientConnectionError):
            _ = await client.post("https://example.com/webhook", {}, timeout=5.0)

    async def test_post_non_json_response(
        self, client: AIOHTTPClient, mock_session: AsyncMock, mock_response: AsyncMock
    ) -> None:
        """Test POST with non-JSON response returns empty body."""
        # Setup mock to raise ContentTypeError on json()
        mock_response.json.side_effect = aiohttp.ContentTypeError(Mock(), Mock())  # pyright: ignore[reportAny]  # mock object
        mock_response.status = 200
        mock_session.post.return_value.__aenter__.return_value = mock_response  # pyright: ignore[reportAny]  # mock object
        client._session = mock_session  # pyright: ignore[reportPrivateUsage]  # testing internal state

        # Execute
        response = await client.post("https://example.com/webhook", {}, timeout=5.0)

        # Verify empty body returned
        assert response.status == 200
        assert response.body == {}


class TestRetryLogic:
    """Test retry logic with exponential backoff."""

    async def test_retry_on_timeout(self, client: AIOHTTPClient, mock_session: AsyncMock) -> None:
        """Test that timeouts are retried with exponential backoff."""
        # Setup mock to timeout twice, then succeed
        call_count = 0

        async def timeout_then_succeed(*args: object, **kwargs: object) -> AsyncMock:  # pyright: ignore[reportUnusedParameter]
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise TimeoutError("Simulated timeout")

            response = AsyncMock()
            response.status = 200
            response.json = AsyncMock(return_value={})
            response.headers = {}
            return response

        mock_session.post.return_value.__aenter__.side_effect = timeout_then_succeed  # pyright: ignore[reportAny]  # mock object
        client._session = mock_session  # pyright: ignore[reportPrivateUsage]  # testing internal state

        # Execute with retry
        with patch("asyncio.sleep") as mock_sleep:
            response = await client.post_with_retry("https://example.com/webhook", {})

        # Verify retries occurred
        assert call_count == 3
        assert response.status == 200
        assert mock_sleep.call_count == 2  # Two retries with sleep

    async def test_retry_on_5xx_error(self, client: AIOHTTPClient, mock_session: AsyncMock) -> None:
        """Test that 5xx errors are retried."""
        # Setup mock to return 500 twice, then 200
        call_count = 0

        async def error_then_succeed(*args: object, **kwargs: object) -> AsyncMock:  # pyright: ignore[reportUnusedParameter]
            nonlocal call_count
            call_count += 1

            response = AsyncMock()
            response.status = 500 if call_count <= 2 else 200
            response.json = AsyncMock(return_value={})
            response.headers = {}
            return response

        mock_session.post.return_value.__aenter__.side_effect = error_then_succeed  # pyright: ignore[reportAny]  # mock object
        client._session = mock_session  # pyright: ignore[reportPrivateUsage]  # testing internal state

        # Execute with retry
        with patch("asyncio.sleep") as mock_sleep:
            response = await client.post_with_retry("https://example.com/webhook", {})

        # Verify retries occurred
        assert call_count == 3
        assert response.status == 200
        assert mock_sleep.call_count == 2

    async def test_no_retry_on_4xx_error(self, client: AIOHTTPClient, mock_session: AsyncMock) -> None:
        """Test that 4xx errors (except 429) are not retried."""
        # Setup mock to return 404
        response = AsyncMock()
        response.status = 404
        response.json = AsyncMock(return_value={})
        response.headers = {}
        mock_session.post.return_value.__aenter__.return_value = response  # pyright: ignore[reportAny]  # mock object
        client._session = mock_session  # pyright: ignore[reportPrivateUsage]  # testing internal state

        # Execute and verify no retry
        with pytest.raises(RuntimeError, match="Client error 404"):
            _ = await client.post_with_retry("https://example.com/webhook", {})

        # Should only be called once (no retries)
        assert mock_session.post.call_count == 1  # pyright: ignore[reportAny]  # mock object

    async def test_retry_429_with_retry_after(self, client: AIOHTTPClient, mock_session: AsyncMock) -> None:
        """Test that 429 errors respect Retry-After header."""
        # Setup mock to return 429 with Retry-After, then 200
        call_count = 0

        async def rate_limit_then_succeed(*args: object, **kwargs: object) -> AsyncMock:  # pyright: ignore[reportUnusedParameter]
            nonlocal call_count
            call_count += 1

            response = AsyncMock()
            if call_count == 1:
                response.status = 429
                response.headers = {"Retry-After": "2"}
            else:
                response.status = 200
                response.headers = {}
            response.json = AsyncMock(return_value={})
            return response

        mock_session.post.return_value.__aenter__.side_effect = rate_limit_then_succeed  # pyright: ignore[reportAny]  # mock object
        client._session = mock_session  # pyright: ignore[reportPrivateUsage]  # testing internal state

        # Execute with retry
        with patch("asyncio.sleep") as mock_sleep:
            response = await client.post_with_retry("https://example.com/webhook", {})

        # Verify Retry-After was respected
        assert call_count == 2
        assert response.status == 200
        mock_sleep.assert_called_once_with(2.0)  # Retry-After value

    async def test_max_retries_exhausted(self, client: AIOHTTPClient, mock_session: AsyncMock) -> None:
        """Test that max retries are enforced."""
        # Setup mock to always timeout
        mock_session.post.return_value.__aenter__.side_effect = TimeoutError("Timeout")  # pyright: ignore[reportAny]  # mock object
        client._session = mock_session  # pyright: ignore[reportPrivateUsage]  # testing internal state

        # Execute and verify exception after max retries
        with patch("asyncio.sleep"):
            with pytest.raises(TimeoutError):
                _ = await client.post_with_retry("https://example.com/webhook", {})

        # Should attempt initial + 3 retries = 4 total
        assert mock_session.post.call_count == 4  # pyright: ignore[reportAny]  # mock object


class TestExponentialBackoff:
    """Test exponential backoff calculation."""

    def test_backoff_calculation(self, client: AIOHTTPClient) -> None:
        """Test exponential backoff increases correctly."""
        # Test multiple attempts
        delays = [client.calculate_backoff_delay(i) for i in range(5)]

        # Verify exponential growth (with jitter tolerance)
        assert 0.8 <= delays[0] <= 1.2  # ~1s with jitter
        assert 1.6 <= delays[1] <= 2.4  # ~2s with jitter
        assert 3.2 <= delays[2] <= 4.8  # ~4s with jitter
        assert 6.4 <= delays[3] <= 9.6  # ~8s with jitter

    def test_backoff_respects_max(self, client: AIOHTTPClient) -> None:
        """Test that backoff respects max_backoff_seconds."""
        # Large attempt number should be capped
        delay = client.calculate_backoff_delay(100)
        assert delay <= client._max_backoff_seconds  # pyright: ignore[reportPrivateUsage]  # testing internal state

    def test_backoff_jitter_applied(self, client: AIOHTTPClient) -> None:
        """Test that jitter is applied to backoff delays."""
        # Generate multiple delays for same attempt
        delays = [client.calculate_backoff_delay(3) for _ in range(50)]

        # Verify variance (not all identical due to jitter)
        assert len(set(delays)) > 1
        # All should be within jitter range of base (8s ± 20%)
        assert all(6.4 <= d <= 9.6 for d in delays)


class TestCircuitBreaker:
    """Test circuit breaker pattern."""

    async def test_circuit_breaker_opens_after_failures(self, client: AIOHTTPClient, mock_session: AsyncMock) -> None:
        """Test that circuit opens after threshold failures."""
        # Setup mock to always fail
        mock_session.post.return_value.__aenter__.side_effect = TimeoutError("Timeout")  # pyright: ignore[reportAny]  # mock object
        client._session = mock_session  # pyright: ignore[reportPrivateUsage]  # testing internal state

        url = "https://example.com/webhook"

        # Exhaust retries multiple times to trigger circuit breaker
        # Need 5 failures to reach threshold, each cycle records 1 failure
        with patch("asyncio.sleep"):
            for _ in range(5):  # Five full retry cycles to reach threshold
                try:
                    _ = await client.post_with_retry(url, {})
                except TimeoutError:
                    pass

        # Circuit should now be open (5 failures threshold)
        assert not client.should_attempt_request(url)
        breaker = client._circuit_breakers[url]  # pyright: ignore[reportPrivateUsage]  # testing internal state
        assert breaker.circuit_state == CircuitState.OPEN
        assert breaker.consecutive_failures >= client._circuit_breaker_threshold  # pyright: ignore[reportPrivateUsage]  # testing internal state

    async def test_circuit_breaker_prevents_requests_when_open(
        self, client: AIOHTTPClient, mock_session: AsyncMock
    ) -> None:
        """Test that open circuit prevents requests."""
        client._session = mock_session  # pyright: ignore[reportPrivateUsage]  # testing internal state
        url = "https://example.com/webhook"

        # Manually open circuit
        from mover_status.utils.http_client import CircuitBreakerState

        client._circuit_breakers[url] = CircuitBreakerState(  # pyright: ignore[reportPrivateUsage]  # testing internal state
            consecutive_failures=10,
            last_failure_time=datetime.now(),
            circuit_state=CircuitState.OPEN,
        )

        # Attempt should be rejected
        with pytest.raises(RuntimeError, match="Circuit breaker is OPEN"):
            _ = await client.post_with_retry(url, {})

    async def test_circuit_breaker_transitions_to_half_open(self, client: AIOHTTPClient) -> None:
        """Test that circuit transitions to half-open after cooldown."""
        url = "https://example.com/webhook"

        # Manually set circuit to OPEN with old failure time
        from mover_status.utils.http_client import CircuitBreakerState

        client._circuit_breakers[url] = CircuitBreakerState(  # pyright: ignore[reportPrivateUsage]  # testing internal state
            consecutive_failures=10,
            last_failure_time=datetime.now() - timedelta(seconds=35),  # Past cooldown
            circuit_state=CircuitState.OPEN,
        )

        # Should allow request (transitions to HALF_OPEN)
        assert client.should_attempt_request(url)
        assert client._circuit_breakers[url].circuit_state == CircuitState.HALF_OPEN  # pyright: ignore[reportPrivateUsage]  # testing internal state

    async def test_circuit_breaker_closes_on_success(self, client: AIOHTTPClient, mock_session: AsyncMock) -> None:
        """Test that circuit closes after successful request."""
        # Setup mock to succeed
        response = AsyncMock()
        response.status = 200
        response.json = AsyncMock(return_value={})
        response.headers = {}
        mock_session.post.return_value.__aenter__.return_value = response  # pyright: ignore[reportAny]  # mock object
        client._session = mock_session  # pyright: ignore[reportPrivateUsage]  # testing internal state

        url = "https://example.com/webhook"

        # Manually set circuit to HALF_OPEN
        from mover_status.utils.http_client import CircuitBreakerState

        client._circuit_breakers[url] = CircuitBreakerState(  # pyright: ignore[reportPrivateUsage]  # testing internal state
            consecutive_failures=10,
            last_failure_time=datetime.now(),
            circuit_state=CircuitState.HALF_OPEN,
        )

        # Successful request should close circuit
        _ = await client.post_with_retry(url, {})

        breaker = client._circuit_breakers[url]  # pyright: ignore[reportPrivateUsage]  # testing internal state
        assert breaker.circuit_state == CircuitState.CLOSED
        assert breaker.consecutive_failures == 0


class TestRetryAfterParsing:
    """Test Retry-After header parsing."""

    def test_parse_retry_after_seconds(self, client: AIOHTTPClient) -> None:
        """Test parsing Retry-After header with seconds."""
        headers = {"Retry-After": "30"}
        delay = client.parse_retry_after(headers)
        assert delay == 30.0

    def test_parse_retry_after_lowercase(self, client: AIOHTTPClient) -> None:
        """Test parsing lowercase retry-after header."""
        headers = {"retry-after": "15"}
        delay = client.parse_retry_after(headers)
        assert delay == 15.0

    def test_parse_retry_after_missing(self, client: AIOHTTPClient) -> None:
        """Test parsing missing Retry-After header."""
        headers: Mapping[str, str] = {}
        delay = client.parse_retry_after(headers)
        assert delay is None

    def test_parse_retry_after_invalid(self, client: AIOHTTPClient) -> None:
        """Test parsing invalid Retry-After header."""
        headers = {"Retry-After": "invalid"}
        delay = client.parse_retry_after(headers)
        assert delay is None


class TestRetryableStatus:
    """Test status code retry determination."""

    def test_429_is_retryable(self, client: AIOHTTPClient) -> None:
        """Test that 429 (rate limit) is retryable."""
        assert client.is_retryable_status(429)

    def test_5xx_is_retryable(self, client: AIOHTTPClient) -> None:
        """Test that 5xx server errors are retryable."""
        assert client.is_retryable_status(500)
        assert client.is_retryable_status(502)
        assert client.is_retryable_status(503)

    def test_2xx_not_retryable(self, client: AIOHTTPClient) -> None:
        """Test that 2xx success codes are not retryable."""
        assert not client.is_retryable_status(200)
        assert not client.is_retryable_status(201)

    def test_4xx_not_retryable(self, client: AIOHTTPClient) -> None:
        """Test that 4xx client errors (except 429) are not retryable."""
        assert not client.is_retryable_status(400)
        assert not client.is_retryable_status(401)
        assert not client.is_retryable_status(404)


class TestDryRunHTTPClient:
    """Dry-run HTTP client behavior."""

    @pytest.mark.asyncio
    async def test_post_logs_payload_and_returns_success(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        client = DryRunHTTPClient()
        caplog.set_level(logging.INFO)

        response = await client.post("https://example.com/hook", {"value": 1}, timeout=1.0)

        assert response.status == 204
        assert response.body == {}
        assert any("Dry-run HTTP POST" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_post_with_retry_delegates_to_post(self) -> None:
        client = DryRunHTTPClient()

        response = await client.post_with_retry("https://example.com/hook", {"value": 2})

        assert response.status == 204
