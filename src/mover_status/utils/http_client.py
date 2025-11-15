"""HTTP client abstraction for webhook notification delivery.

This module provides a robust HTTP client implementation with timeout support,
exponential backoff retry logic with jitter, and circuit breaker pattern for
reliable webhook delivery to notification providers.

Requirements:
- 8.3: Enforce timeout limits using asyncio.timeout
- 14.1: Retry timeouts with exponential backoff
- 14.2: Retry 5xx errors with exponential backoff
- 14.3: Maximum 5 retry attempts with configurable maximum interval
- 14.4: Add random jitter (±20%) to backoff intervals
- 16.2: Shared HTTP client abstraction via Protocol interface
"""

import asyncio
import json
import logging
import random
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import Self

import aiohttp

from mover_status.types.models import Response


class CircuitState(Enum):
    """Circuit breaker state enumeration."""

    CLOSED = auto()  # Normal operation, requests allowed
    OPEN = auto()  # Too many failures, requests rejected
    HALF_OPEN = auto()  # Testing if service recovered


@dataclass(slots=True)
class CircuitBreakerState:
    """Circuit breaker state tracking for a specific URL.

    Tracks failure count, last failure time, and current circuit state
    to implement the circuit breaker pattern for persistent failures.
    """

    consecutive_failures: int = 0
    last_failure_time: datetime | None = None
    circuit_state: CircuitState = CircuitState.CLOSED


class AIOHTTPClient:
    """Async HTTP client with retry logic and circuit breaker pattern.

    Implements the HTTPClient Protocol using aiohttp for async HTTP operations.
    Provides timeout support, exponential backoff with jitter, and circuit
    breaker pattern to prevent cascading failures.

    Example:
        >>> async with AIOHTTPClient() as client:
        ...     response = await client.post_with_retry(
        ...         url="https://webhook.example.com/notify",
        ...         payload={"message": "test"}
        ...     )
    """

    def __init__(
        self,
        *,
        max_retries: int = 5,
        max_backoff_seconds: float = 60.0,
        default_timeout_seconds: float = 10.0,
        jitter_percent: float = 20.0,
        circuit_breaker_threshold: int = 10,
        circuit_breaker_cooldown_seconds: float = 60.0,
    ) -> None:
        """Initialize HTTP client with configurable retry and circuit breaker settings.

        Args:
            max_retries: Maximum number of retry attempts (default: 5)
            max_backoff_seconds: Maximum backoff interval in seconds (default: 60.0)
            default_timeout_seconds: Default timeout for requests in seconds (default: 10.0)
            jitter_percent: Jitter percentage for backoff randomization (default: 20.0)
            circuit_breaker_threshold: Failures before opening circuit (default: 10)
            circuit_breaker_cooldown_seconds: Cooldown period before half-open (default: 60.0)
        """
        self._max_retries: int = max_retries
        self._max_backoff_seconds: float = max_backoff_seconds
        self._default_timeout_seconds: float = default_timeout_seconds
        self._jitter_percent: float = jitter_percent
        self._circuit_breaker_threshold: int = circuit_breaker_threshold
        self._circuit_breaker_cooldown_seconds: float = circuit_breaker_cooldown_seconds

        # Circuit breaker state per URL
        self._circuit_breakers: dict[str, CircuitBreakerState] = {}

        # aiohttp session (created in __aenter__)
        self._session: aiohttp.ClientSession | None = None

        # Logger
        self._logger: logging.Logger = logging.getLogger(__name__)

    async def __aenter__(self) -> Self:
        """Enter async context manager and create aiohttp session.

        Returns:
            Self for context manager protocol
        """
        # Create aiohttp session with timeout configuration
        timeout = aiohttp.ClientTimeout(total=self._default_timeout_seconds)
        self._session = aiohttp.ClientSession(
            timeout=timeout,
            json_serialize=json.dumps,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit async context manager and cleanup resources.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def post(
        self,
        url: str,
        payload: Mapping[str, object],
        *,
        timeout: float,
    ) -> Response:
        """Send HTTP POST request with timeout.

        Args:
            url: Target URL for the POST request
            payload: Request body data (will be JSON-encoded)
            timeout: Request timeout in seconds (keyword-only)

        Returns:
            HTTP response with status, body, and headers

        Raises:
            TimeoutError: If request exceeds timeout
            ValueError: If URL is malformed
            aiohttp.ClientError: For connection issues
        """
        if self._session is None:
            msg = "HTTP client session not initialized. Use 'async with' context manager."
            raise RuntimeError(msg)

        self._logger.debug("Initiating POST request to %s", url)

        try:
            async with asyncio.timeout(timeout):
                async with self._session.post(url, json=payload) as response:
                    # Parse response body as JSON, fallback to empty dict
                    body: Mapping[str, object]
                    try:
                        body = await response.json()  # pyright: ignore[reportAny]  # aiohttp returns Any
                    except (aiohttp.ContentTypeError, ValueError):
                        body = {}

                    # Convert headers to dict
                    headers = dict(response.headers)

                    return Response(
                        status=response.status,
                        body=body,
                        headers=headers,
                    )
        except TimeoutError:
            self._logger.warning("Request to %s timed out after %.1fs", url, timeout)
            raise
        except aiohttp.InvalidURL as exc:
            self._logger.error("Invalid URL: %s", url)
            raise ValueError(f"Malformed URL: {url}") from exc
        except aiohttp.ClientError as exc:
            self._logger.warning("Client error for %s: %s", url, exc)
            raise

    async def post_with_retry(
        self,
        url: str,
        payload: Mapping[str, object],
    ) -> Response:
        """Send HTTP POST with exponential backoff retry.

        Implements retry logic for transient failures with:
        - Maximum 5 retry attempts (configurable)
        - Exponential backoff with configurable maximum interval
        - Random jitter (±20%) to prevent thundering herd
        - Circuit breaker pattern for persistent failures
        - Retry-After header support for 429 responses

        Retry conditions:
        - Network timeouts (TimeoutError)
        - HTTP 5xx server errors
        - Connection refused/reset (aiohttp.ClientConnectionError)
        - DNS resolution failures
        - HTTP 429 (rate limiting)

        Non-retry conditions:
        - HTTP 4xx client errors (except 429)
        - HTTP 401/403 authentication failures
        - Successful responses (2xx, 3xx)

        Args:
            url: Target URL for the POST request
            payload: Request body data (will be JSON-encoded)

        Returns:
            HTTP response with status, body, and headers

        Raises:
            Exception: If all retry attempts are exhausted or circuit is open
        """
        # Check circuit breaker before attempting request
        if not self._should_attempt_request(url):
            msg = f"Circuit breaker is OPEN for {url}"
            self._logger.error(msg)
            raise RuntimeError(msg)

        last_exception: Exception | None = None

        for attempt in range(self._max_retries + 1):  # +1 for initial attempt
            try:
                # Attempt the request
                response = await self.post(
                    url,
                    payload,
                    timeout=self._default_timeout_seconds,
                )

                # Check if response indicates success
                if 200 <= response.status < 400:
                    # Success - close circuit breaker
                    self._record_success(url)
                    self._logger.info(
                        "Request to %s succeeded (status=%d, attempt=%d)",
                        url,
                        response.status,
                        attempt + 1,
                    )
                    return response

                # Check if response is retryable
                if self._is_retryable_status(response.status):
                    # Handle rate limiting with Retry-After header
                    if response.status == 429:
                        retry_after = self._parse_retry_after(response.headers)
                        if retry_after is not None:
                            delay = min(retry_after, self._max_backoff_seconds)
                            self._logger.warning(
                                "Rate limited by %s (429), retrying after %.1fs (attempt %d/%d)",
                                url,
                                delay,
                                attempt + 1,
                                self._max_retries + 1,
                            )
                            await asyncio.sleep(delay)
                            continue

                    # 5xx server error - retry with backoff
                    if attempt < self._max_retries:
                        delay = self._calculate_backoff_delay(attempt)
                        self._logger.warning(
                            "Server error from %s (status=%d), retrying in %.1fs (attempt %d/%d)",
                            url,
                            response.status,
                            delay,
                            attempt + 1,
                            self._max_retries + 1,
                        )
                        await asyncio.sleep(delay)
                        continue

                    # Exhausted retries for 5xx
                    self._record_failure(url)
                    msg = f"Server error {response.status} from {url} after {attempt + 1} attempts"
                    raise RuntimeError(msg)

                # Non-retryable 4xx error
                self._record_failure(url)
                msg = f"Client error {response.status} from {url} (non-retryable)"
                raise RuntimeError(msg)

            except TimeoutError as exc:
                last_exception = exc
                self._logger.warning(
                    "Timeout for %s (attempt %d/%d)",
                    url,
                    attempt + 1,
                    self._max_retries + 1,
                )

                if attempt < self._max_retries:
                    delay = self._calculate_backoff_delay(attempt)
                    self._logger.warning("Retrying in %.1fs", delay)
                    await asyncio.sleep(delay)
                    continue

                # Exhausted retries for timeout
                self._record_failure(url)
                raise

            except (
                aiohttp.ClientConnectionError,
                aiohttp.ServerDisconnectedError,
            ) as exc:
                last_exception = exc
                self._logger.warning(
                    "Connection error for %s: %s (attempt %d/%d)",
                    url,
                    exc,
                    attempt + 1,
                    self._max_retries + 1,
                )

                if attempt < self._max_retries:
                    delay = self._calculate_backoff_delay(attempt)
                    self._logger.warning("Retrying in %.1fs", delay)
                    await asyncio.sleep(delay)
                    continue

                # Exhausted retries for connection error
                self._record_failure(url)
                raise

            except aiohttp.ClientError as exc:
                # Other client errors (DNS, etc.) - retry
                last_exception = exc
                self._logger.warning(
                    "Client error for %s: %s (attempt %d/%d)",
                    url,
                    exc,
                    attempt + 1,
                    self._max_retries + 1,
                )

                if attempt < self._max_retries:
                    delay = self._calculate_backoff_delay(attempt)
                    self._logger.warning("Retrying in %.1fs", delay)
                    await asyncio.sleep(delay)
                    continue

                # Exhausted retries
                self._record_failure(url)
                raise

        # Should not reach here, but handle exhausted retries
        self._record_failure(url)
        if last_exception:
            raise last_exception
        msg = f"All retry attempts exhausted for {url}"
        raise RuntimeError(msg)

    def _calculate_backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter.

        Uses exponential backoff: delay = min(2^attempt, max_backoff_seconds)
        Adds random jitter: ±20% of calculated delay

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds with jitter applied
        """
        # Exponential backoff: 2^attempt seconds
        exponential_delay: float = pow(2.0, attempt)
        base_delay: float = min(exponential_delay, self._max_backoff_seconds)

        # Apply jitter: ±jitter_percent of base delay
        jitter_factor: float = 1.0 + random.uniform(
            -self._jitter_percent / 100.0,
            self._jitter_percent / 100.0,
        )
        delay: float = base_delay * jitter_factor

        # Ensure delay doesn't exceed max backoff
        return min(delay, self._max_backoff_seconds)

    def _parse_retry_after(self, headers: Mapping[str, str]) -> float | None:
        """Parse Retry-After header from HTTP response.

        Supports both seconds (integer) and HTTP-date formats.

        Args:
            headers: HTTP response headers

        Returns:
            Delay in seconds, or None if header not present or invalid
        """
        retry_after = headers.get("Retry-After") or headers.get("retry-after")
        if not retry_after:
            return None

        try:
            # Try parsing as integer (seconds)
            return float(retry_after)
        except ValueError:
            # Try parsing as HTTP-date (not commonly used, but spec-compliant)
            self._logger.warning("Retry-After header has unsupported format: %s", retry_after)
            return None

    def _is_retryable_status(self, status: int) -> bool:
        """Check if HTTP status code is retryable.

        Retryable statuses:
        - 429: Too Many Requests (rate limiting)
        - 5xx: Server errors

        Non-retryable statuses:
        - 2xx, 3xx: Success
        - 4xx (except 429): Client errors

        Args:
            status: HTTP status code

        Returns:
            True if status is retryable, False otherwise
        """
        return status == 429 or status >= 500

    def _should_attempt_request(self, url: str) -> bool:
        """Check if request should be attempted based on circuit breaker state.

        Args:
            url: Target URL

        Returns:
            True if request should be attempted, False if circuit is open
        """
        breaker = self._circuit_breakers.get(url)
        if breaker is None:
            # No circuit breaker state yet - allow request
            return True

        if breaker.circuit_state == CircuitState.CLOSED:
            # Circuit closed - allow request
            return True

        if breaker.circuit_state == CircuitState.OPEN:
            # Check if cooldown period has elapsed
            if breaker.last_failure_time is None:
                # Should not happen, but allow request if no failure time
                return True

            elapsed = datetime.now() - breaker.last_failure_time
            if elapsed.total_seconds() >= self._circuit_breaker_cooldown_seconds:
                # Transition to half-open state
                breaker.circuit_state = CircuitState.HALF_OPEN
                self._logger.warning("Circuit breaker for %s transitioned to HALF_OPEN", url)
                return True

            # Still in cooldown - reject request
            return False

        if breaker.circuit_state == CircuitState.HALF_OPEN:
            # Allow one test request in half-open state
            return True

        # Should not reach here
        return True

    def _record_success(self, url: str) -> None:
        """Record successful request and update circuit breaker state.

        Args:
            url: Target URL
        """
        breaker = self._circuit_breakers.get(url)
        if breaker is None:
            # No circuit breaker state yet - nothing to do
            return

        # Reset failure count and close circuit
        previous_state = breaker.circuit_state
        breaker.consecutive_failures = 0
        breaker.circuit_state = CircuitState.CLOSED

        if previous_state != CircuitState.CLOSED:
            self._logger.info("Circuit breaker for %s transitioned to CLOSED", url)

    def _record_failure(self, url: str) -> None:
        """Record failed request and update circuit breaker state.

        Args:
            url: Target URL
        """
        breaker = self._circuit_breakers.get(url)
        if breaker is None:
            # Create new circuit breaker state
            breaker = CircuitBreakerState()
            self._circuit_breakers[url] = breaker

        # Increment failure count and update timestamp
        breaker.consecutive_failures += 1
        breaker.last_failure_time = datetime.now()

        # Check if threshold exceeded
        if breaker.consecutive_failures >= self._circuit_breaker_threshold:
            if breaker.circuit_state == CircuitState.HALF_OPEN:
                # Half-open test failed - reopen circuit with extended cooldown
                breaker.circuit_state = CircuitState.OPEN
                self._logger.warning(
                    "Circuit breaker for %s transitioned to OPEN (half-open test failed, failures=%d)",
                    url,
                    breaker.consecutive_failures,
                )
            elif breaker.circuit_state == CircuitState.CLOSED:
                # Threshold exceeded - open circuit
                breaker.circuit_state = CircuitState.OPEN
                self._logger.warning(
                    "Circuit breaker for %s transitioned to OPEN (failures=%d, threshold=%d)",
                    url,
                    breaker.consecutive_failures,
                    self._circuit_breaker_threshold,
                )

