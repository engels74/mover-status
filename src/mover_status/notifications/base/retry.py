"""Advanced retry mechanisms with timeout and circuit breaker support."""

from __future__ import annotations

import asyncio
import time
from functools import wraps
from typing import TYPE_CHECKING, TypeVar, cast
from enum import Enum
from collections.abc import Mapping
import logging

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

F = TypeVar("F", bound="Callable[..., Awaitable[object]]")


class CircuitBreakerState(Enum):
    """States for the circuit breaker."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class RetryTimeoutError(Exception):
    """Exception raised when retry timeout is exceeded."""
    pass


class CircuitBreaker:
    """Circuit breaker implementation to prevent cascading failures."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type[Exception] | tuple[type[Exception], ...] = Exception
    ) -> None:
        """Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before attempting to recover
            expected_exception: Exception types that count as failures
        """
        self.failure_threshold: int = failure_threshold
        self.recovery_timeout: float = recovery_timeout
        self.expected_exception: type[Exception] | tuple[type[Exception], ...] = expected_exception
        
        self.failure_count: int = 0
        self.last_failure_time: float = 0.0
        self.state: CircuitBreakerState = CircuitBreakerState.CLOSED
        
    def __call__(self, func: F) -> F:
        """Decorator to apply circuit breaker to a function."""
        @wraps(func)
        async def wrapper(*args: object, **kwargs: object) -> object:
            if self.state == CircuitBreakerState.OPEN:
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = CircuitBreakerState.HALF_OPEN
                    logger.info("Circuit breaker transitioning to HALF_OPEN state")
                else:
                    logger.warning("Circuit breaker is OPEN, rejecting call")
                    raise CircuitBreakerError("Circuit breaker is open")
            
            try:
                result = await func(*args, **kwargs)  # type: ignore[misc]
                if self.state == CircuitBreakerState.HALF_OPEN:
                    self.state = CircuitBreakerState.CLOSED
                    self.failure_count = 0
                    logger.info("Circuit breaker transitioning to CLOSED state")
                return result
            except self.expected_exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitBreakerState.OPEN
                    logger.warning(
                        "Circuit breaker opening due to %d failures", self.failure_count
                    )
                raise e
                
        return cast(F, wrapper)


def with_timeout(timeout_seconds: float) -> Callable[[F], F]:
    """Decorator that adds timeout to async functions.
    
    Args:
        timeout_seconds: Maximum time to wait for function completion
        
    Returns:
        Decorated function with timeout
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: object, **kwargs: object) -> object:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),  # type: ignore[misc]
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.warning("Function %s timed out after %.1fs", func.__name__, timeout_seconds)
                raise RetryTimeoutError(f"Operation timed out after {timeout_seconds} seconds")
        return cast(F, wrapper)
    return decorator


def with_advanced_retry(
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    timeout_seconds: float | None = None,
    circuit_breaker_config: Mapping[str, object] | None = None,
    jitter: bool = True
) -> Callable[[F], F]:
    """Advanced retry decorator with timeout and circuit breaker support.
    
    Args:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff
        timeout_seconds: Optional timeout for each attempt
        circuit_breaker_config: Optional circuit breaker configuration
        jitter: Whether to add random jitter to backoff delays
        
    Returns:
        Decorated function with advanced retry logic
    """
    def decorator(func: F) -> F:
        # Apply circuit breaker if configured
        if circuit_breaker_config is not None:
            failure_threshold_val = circuit_breaker_config.get("failure_threshold", 5)
            recovery_timeout_val = circuit_breaker_config.get("recovery_timeout", 60.0)
            expected_exception_val = circuit_breaker_config.get(
                "expected_exception", Exception
            )
            
            # Type-safe conversions
            failure_threshold = int(failure_threshold_val) if isinstance(failure_threshold_val, (int, float, str)) else 5
            recovery_timeout = float(recovery_timeout_val) if isinstance(recovery_timeout_val, (int, float, str)) else 60.0
            
            # Handle expected_exception type
            if isinstance(expected_exception_val, type) and issubclass(expected_exception_val, Exception):
                expected_exception: type[Exception] | tuple[type[Exception], ...] = expected_exception_val
            elif isinstance(expected_exception_val, tuple):
                # Validate all tuple elements are exception types
                valid_tuple = True
                for exc in expected_exception_val:
                    if not (isinstance(exc, type) and issubclass(exc, Exception)):
                        valid_tuple = False
                        break
                
                if valid_tuple:
                    expected_exception = expected_exception_val  # pyright: ignore[reportUnknownVariableType]
                else:
                    expected_exception = Exception
            else:
                expected_exception = Exception
            
            circuit_breaker = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception
            )
            func = circuit_breaker(func)
        
        # Apply timeout if configured
        if timeout_seconds is not None:
            func = with_timeout(timeout_seconds)(func)
        
        @wraps(func)
        async def wrapper(*args: object, **kwargs: object) -> object:
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    logger.debug("Attempt %d/%d for %s", attempt + 1, max_attempts, func.__name__)
                    return await func(*args, **kwargs)  # type: ignore[misc]
                except (Exception, CircuitBreakerError, RetryTimeoutError) as e:
                    last_exception = e
                    
                    # Don't retry on circuit breaker errors or timeout errors
                    if isinstance(e, (CircuitBreakerError, RetryTimeoutError)):
                        logger.warning("Non-retryable error: %s", e)
                        raise
                    
                    if attempt == max_attempts - 1:
                        logger.error("All %d attempts failed for %s", max_attempts, func.__name__)
                        raise
                    
                    # Calculate backoff delay
                    base_delay = backoff_factor ** attempt
                    
                    # Add jitter if enabled
                    if jitter:
                        import random
                        jitter_factor = random.uniform(0.5, 1.5)
                        delay = base_delay * jitter_factor
                    else:
                        delay = base_delay
                    
                    logger.info(
                        "Attempt %d failed for %s, retrying in %.2fs: %s",
                        attempt + 1, func.__name__, delay, e
                    )
                    await asyncio.sleep(delay)
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            return None
            
        return cast(F, wrapper)
    return decorator