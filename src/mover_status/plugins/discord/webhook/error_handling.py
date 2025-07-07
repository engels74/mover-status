"""Enhanced error handling and rate limiting for Discord webhook operations."""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import TYPE_CHECKING, TypeVar, cast
from functools import wraps
from collections.abc import Mapping
from urllib.parse import urlparse

import httpx

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

F = TypeVar("F", bound="Callable[..., Awaitable[object]]")


class DiscordErrorType(Enum):
    """Types of Discord API errors."""
    RATE_LIMITED = "rate_limited"
    INVALID_WEBHOOK = "invalid_webhook"
    MISSING_PERMISSIONS = "missing_permissions"
    INVALID_PAYLOAD = "invalid_payload"
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    SERVER_ERROR = "server_error"
    UNKNOWN_ERROR = "unknown_error"


class DiscordApiError(Exception):
    """Exception for Discord API errors."""
    
    def __init__(
        self,
        error_type: DiscordErrorType,
        message: str,
        status_code: int | None = None,
        retry_after: float | None = None,
        original_error: Exception | None = None,
    ) -> None:
        """Initialize Discord API error.
        
        Args:
            error_type: Type of error
            message: Error message
            status_code: HTTP status code if applicable
            retry_after: Retry-after time in seconds if applicable
            original_error: Original exception that caused this error
        """
        super().__init__(message)
        self.error_type: DiscordErrorType = error_type
        self.message: str = message
        self.status_code: int | None = status_code
        self.retry_after: float | None = retry_after
        self.original_error: Exception | None = original_error


class WebhookValidator:
    """Validator for Discord webhook URLs and configurations."""
    
    @staticmethod
    def validate_webhook_url(webhook_url: str) -> None:
        """Validate Discord webhook URL format.
        
        Args:
            webhook_url: Discord webhook URL to validate
            
        Raises:
            DiscordApiError: If webhook URL is invalid
        """
        try:
            parsed = urlparse(webhook_url)
            
            if parsed.scheme not in ("http", "https"):
                raise DiscordApiError(
                    DiscordErrorType.INVALID_WEBHOOK,
                    "Webhook URL must use HTTP or HTTPS protocol"
                )
            
            if not parsed.netloc.endswith(("discord.com", "discordapp.com")):
                raise DiscordApiError(
                    DiscordErrorType.INVALID_WEBHOOK,
                    "Webhook URL must be a Discord webhook"
                )
            
            if not parsed.path.startswith("/api/webhooks/"):
                raise DiscordApiError(
                    DiscordErrorType.INVALID_WEBHOOK,
                    "Invalid Discord webhook URL path format"
                )
            
            # Check for valid webhook ID and token structure
            path_parts = parsed.path.split("/")
            if len(path_parts) < 5:
                raise DiscordApiError(
                    DiscordErrorType.INVALID_WEBHOOK,
                    "Webhook URL missing ID or token"
                )
            
            webhook_id = path_parts[3]
            webhook_token = path_parts[4]
            
            # Discord webhook ID should be a snowflake (numeric)
            if not webhook_id.isdigit():
                raise DiscordApiError(
                    DiscordErrorType.INVALID_WEBHOOK,
                    "Invalid webhook ID format"
                )
            
            # Discord webhook token should be non-empty
            if not webhook_token:
                raise DiscordApiError(
                    DiscordErrorType.INVALID_WEBHOOK,
                    "Invalid webhook token"
                )
                
        except DiscordApiError:
            raise
        except Exception as e:
            raise DiscordApiError(
                DiscordErrorType.INVALID_WEBHOOK,
                f"Failed to validate webhook URL: {e}",
                original_error=e
            )
    
    @staticmethod
    def validate_embed_payload(payload: Mapping[str, object]) -> None:
        """Validate Discord webhook payload.
        
        Args:
            payload: Discord webhook payload to validate
            
        Raises:
            DiscordApiError: If payload is invalid
        """
        try:
            # Check content length
            content = payload.get("content")
            if content is not None and len(str(content)) > 2000:
                raise DiscordApiError(
                    DiscordErrorType.INVALID_PAYLOAD,
                    "Message content cannot exceed 2000 characters"
                )
            
            # Check embeds
            embeds_raw = payload.get("embeds")
            if embeds_raw is not None:
                if not isinstance(embeds_raw, list):
                    raise DiscordApiError(
                        DiscordErrorType.INVALID_PAYLOAD,
                        "Embeds must be a list"
                    )
                
                # Type-narrow to list of objects
                embeds = cast(list[object], embeds_raw)
                
                if len(embeds) > 10:
                    raise DiscordApiError(
                        DiscordErrorType.INVALID_PAYLOAD,
                        "Cannot send more than 10 embeds"
                    )
                
                for embed_obj in embeds:
                    if not isinstance(embed_obj, dict):
                        raise DiscordApiError(
                            DiscordErrorType.INVALID_PAYLOAD,
                            "Each embed must be a dictionary"
                        )
                    
                    # Type-narrow embed to dict[str, object]
                    embed = cast(dict[str, object], embed_obj)
                    
                    # Check embed limits
                    title = embed.get("title")
                    if title is not None and len(str(title)) > 256:
                        raise DiscordApiError(
                            DiscordErrorType.INVALID_PAYLOAD,
                            "Embed title cannot exceed 256 characters"
                        )
                    
                    description = embed.get("description")
                    if description is not None and len(str(description)) > 4096:
                        raise DiscordApiError(
                            DiscordErrorType.INVALID_PAYLOAD,
                            "Embed description cannot exceed 4096 characters"
                        )
                    
                    fields_raw = embed.get("fields")
                    if fields_raw is not None:
                        if not isinstance(fields_raw, list):
                            raise DiscordApiError(
                                DiscordErrorType.INVALID_PAYLOAD,
                                "Embed fields must be a list"
                            )
                        
                        # Type-narrow to list of objects
                        fields = cast(list[object], fields_raw)
                        
                        if len(fields) > 25:
                            raise DiscordApiError(
                                DiscordErrorType.INVALID_PAYLOAD,
                                "Embed cannot have more than 25 fields"
                            )
                        
                        for field_obj in fields:
                            if not isinstance(field_obj, dict):
                                raise DiscordApiError(
                                    DiscordErrorType.INVALID_PAYLOAD,
                                    "Each field must be a dictionary"
                                )
                            
                            # Type-narrow field to dict[str, object]
                            field = cast(dict[str, object], field_obj)
                            
                            if "name" not in field or "value" not in field:
                                raise DiscordApiError(
                                    DiscordErrorType.INVALID_PAYLOAD,
                                    "Each field must have 'name' and 'value'"
                                )
                            
                            if len(str(field["name"])) > 256:
                                raise DiscordApiError(
                                    DiscordErrorType.INVALID_PAYLOAD,
                                    "Field name cannot exceed 256 characters"
                                )
                            
                            if len(str(field["value"])) > 1024:
                                raise DiscordApiError(
                                    DiscordErrorType.INVALID_PAYLOAD,
                                    "Field value cannot exceed 1024 characters"
                                )
            
            # Check if either content or embeds are provided
            if content is None and embeds_raw is None:
                raise DiscordApiError(
                    DiscordErrorType.INVALID_PAYLOAD,
                    "Either content or embeds must be provided"
                )
                
        except DiscordApiError:
            raise
        except Exception as e:
            raise DiscordApiError(
                DiscordErrorType.INVALID_PAYLOAD,
                f"Failed to validate payload: {e}",
                original_error=e
            )


class DiscordErrorClassifier:
    """Classifier for Discord API errors."""
    
    @staticmethod
    def classify_http_error(response: httpx.Response) -> DiscordApiError:
        """Classify HTTP error from Discord API response.
        
        Args:
            response: HTTP response object
            
        Returns:
            Classified Discord API error
        """
        status_code = response.status_code
        
        if status_code == 429:
            # Rate limited
            retry_after_header = response.headers.get("Retry-After")
            try:
                retry_after = float(retry_after_header) if retry_after_header is not None else 1.0
            except (ValueError, TypeError):
                retry_after = 1.0
            
            return DiscordApiError(
                DiscordErrorType.RATE_LIMITED,
                f"Rate limited by Discord API. Retry after {retry_after} seconds",
                status_code=status_code,
                retry_after=retry_after
            )
        
        elif status_code == 400:
            return DiscordApiError(
                DiscordErrorType.INVALID_PAYLOAD,
                "Invalid request payload",
                status_code=status_code
            )
        
        elif status_code == 401:
            return DiscordApiError(
                DiscordErrorType.MISSING_PERMISSIONS,
                "Unauthorized - invalid webhook credentials",
                status_code=status_code
            )
        
        elif status_code == 403:
            return DiscordApiError(
                DiscordErrorType.MISSING_PERMISSIONS,
                "Forbidden - insufficient permissions",
                status_code=status_code
            )
        
        elif status_code == 404:
            return DiscordApiError(
                DiscordErrorType.INVALID_WEBHOOK,
                "Webhook not found - invalid webhook URL",
                status_code=status_code
            )
        
        elif 500 <= status_code < 600:
            return DiscordApiError(
                DiscordErrorType.SERVER_ERROR,
                f"Discord API server error (HTTP {status_code})",
                status_code=status_code
            )
        
        else:
            return DiscordApiError(
                DiscordErrorType.UNKNOWN_ERROR,
                f"Unknown Discord API error (HTTP {status_code})",
                status_code=status_code
            )
    
    @staticmethod
    def classify_network_error(error: Exception) -> DiscordApiError:
        """Classify network error.
        
        Args:
            error: Network exception
            
        Returns:
            Classified Discord API error
        """
        if isinstance(error, httpx.TimeoutException):
            return DiscordApiError(
                DiscordErrorType.TIMEOUT_ERROR,
                "Request timed out",
                original_error=error
            )
        
        elif isinstance(error, (httpx.ConnectError, httpx.NetworkError)):
            return DiscordApiError(
                DiscordErrorType.NETWORK_ERROR,
                f"Network connection error: {error}",
                original_error=error
            )
        
        else:
            return DiscordApiError(
                DiscordErrorType.UNKNOWN_ERROR,
                f"Unknown network error: {error}",
                original_error=error
            )


class AdvancedRateLimiter:
    """Advanced rate limiter with burst handling and adaptive delays."""
    
    def __init__(
        self,
        max_requests: int = 30,
        time_window: float = 60.0,
        burst_limit: int = 5,
        adaptive_delay: bool = True,
    ) -> None:
        """Initialize advanced rate limiter.
        
        Args:
            max_requests: Maximum requests per time window
            time_window: Time window in seconds
            burst_limit: Maximum burst requests
            adaptive_delay: Whether to use adaptive delays
        """
        self.max_requests: int = max_requests
        self.time_window: float = time_window
        self.burst_limit: int = burst_limit
        self.adaptive_delay: bool = adaptive_delay
        
        self._request_timestamps: list[float] = []
        self._burst_timestamps: list[float] = []
        self._lock: asyncio.Lock = asyncio.Lock()
        self._consecutive_rate_limits: int = 0
        self._last_rate_limit_time: float = 0.0
    
    async def acquire(self) -> None:
        """Acquire rate limit permission."""
        async with self._lock:
            current_time = time.time()
            
            # Clean old timestamps
            self._request_timestamps = [
                ts for ts in self._request_timestamps
                if current_time - ts < self.time_window
            ]
            
            self._burst_timestamps = [
                ts for ts in self._burst_timestamps
                if current_time - ts < 5.0  # 5 second burst window
            ]
            
            # Check burst limit
            if len(self._burst_timestamps) >= self.burst_limit:
                burst_wait = 5.0 - (current_time - min(self._burst_timestamps))
                if burst_wait > 0:
                    logger.warning(f"Burst limit reached. Waiting {burst_wait:.1f} seconds")
                    await asyncio.sleep(burst_wait)
            
            # Check main rate limit
            if len(self._request_timestamps) >= self.max_requests:
                oldest_request = min(self._request_timestamps)
                wait_time = self.time_window - (current_time - oldest_request)
                
                if wait_time > 0:
                    # Apply adaptive delay if enabled
                    if self.adaptive_delay:
                        self._consecutive_rate_limits += 1
                        adaptive_multiplier = min(1.5 ** self._consecutive_rate_limits, 4.0)
                        wait_time *= adaptive_multiplier
                        
                        logger.warning(
                            f"Rate limit reached. Adaptive waiting {wait_time:.1f} seconds " +
                            f"(consecutive limits: {self._consecutive_rate_limits})"
                        )
                    else:
                        logger.warning(f"Rate limit reached. Waiting {wait_time:.1f} seconds")
                    
                    self._last_rate_limit_time = current_time
                    await asyncio.sleep(wait_time)
            
            # Reset consecutive rate limits if enough time has passed
            if current_time - self._last_rate_limit_time > self.time_window:
                self._consecutive_rate_limits = 0
            
            # Add current request timestamps
            current_time = time.time()
            self._request_timestamps.append(current_time)
            self._burst_timestamps.append(current_time)
    
    def get_stats(self) -> dict[str, object]:
        """Get rate limiter statistics.
        
        Returns:
            Dictionary with rate limiter statistics
        """
        current_time = time.time()
        
        # Clean old timestamps for accurate stats
        recent_requests = [
            ts for ts in self._request_timestamps
            if current_time - ts < self.time_window
        ]
        
        recent_bursts = [
            ts for ts in self._burst_timestamps
            if current_time - ts < 5.0
        ]
        
        return {
            "requests_in_window": len(recent_requests),
            "max_requests": self.max_requests,
            "burst_requests": len(recent_bursts),
            "burst_limit": self.burst_limit,
            "consecutive_rate_limits": self._consecutive_rate_limits,
            "time_since_last_rate_limit": current_time - self._last_rate_limit_time,
        }


def with_discord_error_handling(
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    max_backoff: float = 60.0,
    jitter: bool = True,
    respect_retry_after: bool = True,
) -> Callable[[F], F]:
    """Decorator for Discord-specific error handling and retry logic.
    
    Args:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Exponential backoff factor
        max_backoff: Maximum backoff time in seconds
        jitter: Whether to add random jitter to backoff
        respect_retry_after: Whether to respect Discord's Retry-After header
        
    Returns:
        Decorated function with Discord error handling
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: object, **kwargs: object) -> object:
            last_exception: Exception | None = None
            
            for attempt in range(max_attempts):
                try:
                    logger.debug(f"Discord API attempt {attempt + 1}/{max_attempts} for {func.__name__}")
                    return await func(*args, **kwargs)  # type: ignore[misc]
                    
                except DiscordApiError as e:
                    last_exception = e
                    
                    # Don't retry on certain error types
                    if e.error_type in (
                        DiscordErrorType.INVALID_WEBHOOK,
                        DiscordErrorType.MISSING_PERMISSIONS,
                        DiscordErrorType.INVALID_PAYLOAD,
                    ):
                        logger.error(f"Non-retryable Discord error: {e}")
                        raise
                    
                    # Handle rate limiting
                    if e.error_type == DiscordErrorType.RATE_LIMITED:
                        if respect_retry_after and e.retry_after:
                            logger.warning(f"Rate limited, waiting {e.retry_after} seconds")
                            await asyncio.sleep(e.retry_after)
                            continue
                    
                    # Last attempt
                    if attempt == max_attempts - 1:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}: {e}")
                        raise
                    
                    # Calculate backoff delay
                    base_delay = min(backoff_factor ** attempt, max_backoff)
                    
                    # Add jitter if enabled
                    if jitter:
                        import random
                        jitter_factor = random.uniform(0.5, 1.5)
                        delay = base_delay * jitter_factor
                    else:
                        delay = base_delay
                    
                    logger.info(
                        f"Discord API attempt {attempt + 1} failed, retrying in {delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(delay)
                
                except Exception as e:
                    # Convert other exceptions to Discord API errors
                    last_exception = e
                    
                    if isinstance(e, httpx.HTTPStatusError):
                        discord_error = DiscordErrorClassifier.classify_http_error(e.response)
                        logger.warning(f"HTTP error converted to Discord error: {discord_error}")
                        # Replace the exception with the converted error and handle as DiscordApiError
                        last_exception = discord_error
                        
                        # Handle like a DiscordApiError
                        if discord_error.error_type in (
                            DiscordErrorType.INVALID_WEBHOOK,
                            DiscordErrorType.MISSING_PERMISSIONS,
                            DiscordErrorType.INVALID_PAYLOAD,
                        ):
                            logger.error(f"Non-retryable Discord error: {discord_error}")
                            raise discord_error
                        
                        # Handle rate limiting
                        if discord_error.error_type == DiscordErrorType.RATE_LIMITED:
                            if respect_retry_after and discord_error.retry_after:
                                logger.warning(f"Rate limited, waiting {discord_error.retry_after} seconds")
                                await asyncio.sleep(discord_error.retry_after)
                                continue
                        
                        # Last attempt
                        if attempt == max_attempts - 1:
                            logger.error(f"All {max_attempts} attempts failed for {func.__name__}: {discord_error}")
                            raise discord_error
                        
                        # Calculate backoff delay
                        base_delay = min(backoff_factor ** attempt, max_backoff)
                        
                        # Add jitter if enabled
                        if jitter:
                            import random
                            jitter_factor = random.uniform(0.5, 1.5)
                            delay = base_delay * jitter_factor
                        else:
                            delay = base_delay
                        
                        logger.info(
                            f"Discord API attempt {attempt + 1} failed, retrying in {delay:.2f}s: {discord_error}"
                        )
                        await asyncio.sleep(delay)
                    
                    elif isinstance(e, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)):
                        discord_error = DiscordErrorClassifier.classify_network_error(e)
                        logger.warning(f"Network error converted to Discord error: {discord_error}")
                        # Replace the exception with the converted error
                        last_exception = discord_error
                        
                        # Last attempt
                        if attempt == max_attempts - 1:
                            logger.error(f"All {max_attempts} attempts failed for {func.__name__}: {discord_error}")
                            raise discord_error
                        
                        # Calculate backoff delay
                        base_delay = min(backoff_factor ** attempt, max_backoff)
                        
                        # Add jitter if enabled
                        if jitter:
                            import random
                            jitter_factor = random.uniform(0.5, 1.5)
                            delay = base_delay * jitter_factor
                        else:
                            delay = base_delay
                        
                        logger.info(
                            f"Discord API attempt {attempt + 1} failed, retrying in {delay:.2f}s: {discord_error}"
                        )
                        await asyncio.sleep(delay)
                    
                    else:
                        logger.error(f"Unexpected error in Discord operation: {e}")
                        if attempt == max_attempts - 1:
                            raise
                        
                        # Use default backoff for unknown errors
                        delay = min(backoff_factor ** attempt, max_backoff)
                        if jitter:
                            import random
                            jitter_factor = random.uniform(0.5, 1.5)
                            delay *= jitter_factor
                        
                        logger.info(f"Retrying after unexpected error in {delay:.2f}s")
                        await asyncio.sleep(delay)
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            return None
            
        return cast(F, wrapper)
    return decorator