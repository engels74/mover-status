"""Test cases for advanced retry mechanisms."""

from __future__ import annotations

import asyncio
import time

import pytest

from mover_status.notifications.base.retry import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerState,
    RetryTimeoutError,
    with_advanced_retry,
    with_timeout,
)


class TestCircuitBreaker:
    """Test cases for the CircuitBreaker class."""
    
    def test_circuit_breaker_initialization(self) -> None:
        """Test circuit breaker initialization with default values."""
        cb = CircuitBreaker()
        
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 60.0
        assert cb.expected_exception == Exception
        assert cb.failure_count == 0
        assert cb.state == CircuitBreakerState.CLOSED
    
    def test_circuit_breaker_custom_initialization(self) -> None:
        """Test circuit breaker initialization with custom values."""
        cb = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30.0,
            expected_exception=ValueError
        )
        
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 30.0
        assert cb.expected_exception == ValueError
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_success_calls(self) -> None:
        """Test circuit breaker allows successful calls."""
        cb = CircuitBreaker(failure_threshold=3)
        
        @cb
        async def test_function() -> str:
            return "success"
        
        result = await test_function()
        
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self) -> None:
        """Test circuit breaker opens after reaching failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)
        call_count = 0
        
        @cb
        async def test_function() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("Test error")
        
        # First 3 calls should fail and open the circuit
        for _ in range(3):
            with pytest.raises(ValueError):
                _ = await test_function()
        
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.failure_count == 3
        assert call_count == 3
        
        # Next call should be rejected by circuit breaker
        with pytest.raises(CircuitBreakerError):
            _ = await test_function()
        
        # Function should not have been called again
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self) -> None:
        """Test circuit breaker recovery through half-open state."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        call_count = 0
        should_fail = True
        
        @cb
        async def test_function() -> str:
            nonlocal call_count
            call_count += 1
            if should_fail:
                raise ValueError("Test error")
            return "success"
        
        # Trigger circuit breaker to open
        for _ in range(2):
            with pytest.raises(ValueError):
                _ = await test_function()
        
        assert cb.state == CircuitBreakerState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(0.2)
        
        # Function should succeed and close the circuit
        should_fail = False
        result = await test_function()
        
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_failure(self) -> None:
        """Test circuit breaker reopens on failure in half-open state."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        @cb
        async def test_function() -> str:
            raise ValueError("Test error")
        
        # Trigger circuit breaker to open
        for _ in range(2):
            with pytest.raises(ValueError):
                _ = await test_function()
        
        assert cb.state == CircuitBreakerState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(0.2)
        
        # Function should fail and reopen the circuit
        with pytest.raises(ValueError):
            _ = await test_function()
        
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.failure_count == 3


class TestTimeoutDecorator:
    """Test cases for the timeout decorator."""
    
    @pytest.mark.asyncio
    async def test_timeout_decorator_success(self) -> None:
        """Test timeout decorator with successful completion."""
        @with_timeout(1.0)
        async def test_function() -> str:
            await asyncio.sleep(0.1)
            return "success"
        
        result = await test_function()
        
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_timeout_decorator_timeout(self) -> None:
        """Test timeout decorator with timeout exceeded."""
        @with_timeout(0.1)
        async def test_function() -> str:
            await asyncio.sleep(0.2)
            return "success"
        
        with pytest.raises(RetryTimeoutError, match="Operation timed out after 0.1 seconds"):
            _ = await test_function()
    
    @pytest.mark.asyncio
    async def test_timeout_decorator_preserves_metadata(self) -> None:
        """Test timeout decorator preserves function metadata."""
        @with_timeout(1.0)
        async def test_function() -> str:
            """Test docstring."""
            return "success"
        
        assert test_function.__name__ == "test_function"
        assert test_function.__doc__ == "Test docstring."


class TestAdvancedRetry:
    """Test cases for the advanced retry decorator."""
    
    @pytest.mark.asyncio
    async def test_advanced_retry_success_first_try(self) -> None:
        """Test advanced retry with successful first attempt."""
        call_count = 0
        
        @with_advanced_retry(max_attempts=3)
        async def test_function() -> str:
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await test_function()
        
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_advanced_retry_success_after_failures(self) -> None:
        """Test advanced retry with success after failures."""
        call_count = 0
        
        @with_advanced_retry(max_attempts=3, backoff_factor=0.1, jitter=False)
        async def test_function() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"
        
        result = await test_function()
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_advanced_retry_all_attempts_fail(self) -> None:
        """Test advanced retry when all attempts fail."""
        call_count = 0
        
        @with_advanced_retry(max_attempts=3, backoff_factor=0.1, jitter=False)
        async def test_function() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("Persistent failure")
        
        with pytest.raises(ValueError, match="Persistent failure"):
            _ = await test_function()
        
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_advanced_retry_with_timeout(self) -> None:
        """Test advanced retry with timeout configuration."""
        call_count = 0
        
        @with_advanced_retry(
            max_attempts=3,
            timeout_seconds=0.1,
            backoff_factor=0.1,
            jitter=False
        )
        async def test_function() -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.2)  # Longer than timeout
            return "success"
        
        with pytest.raises(RetryTimeoutError):
            _ = await test_function()
        
        # Should only be called once due to timeout
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_advanced_retry_with_circuit_breaker(self) -> None:
        """Test advanced retry with circuit breaker configuration."""
        call_count = 0
        
        @with_advanced_retry(
            max_attempts=5,
            circuit_breaker_config={
                "failure_threshold": 3,
                "recovery_timeout": 0.1,
                "expected_exception": ValueError
            },
            backoff_factor=0.1,
            jitter=False
        )
        async def test_function() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("Test error")
        
        with pytest.raises(CircuitBreakerError):
            _ = await test_function()
        
        # Should be called 3 times (failure threshold) + 1 more time
        # that gets rejected by circuit breaker
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_advanced_retry_with_jitter(self) -> None:
        """Test advanced retry with jitter enabled."""
        call_count = 0
        
        @with_advanced_retry(max_attempts=3, backoff_factor=1.0, jitter=True)
        async def test_function() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"
        
        start_time = time.time()
        result = await test_function()
        end_time = time.time()
        
        assert result == "success"
        assert call_count == 3
        
        # With jitter, timing should be different from pure exponential backoff
        # This is a simple test to ensure jitter is applied
        total_time = end_time - start_time
        assert total_time > 0.5  # Should have some delay
        assert total_time < 3.0  # But not too much due to jitter
    
    @pytest.mark.asyncio
    async def test_advanced_retry_preserves_metadata(self) -> None:
        """Test advanced retry preserves function metadata."""
        @with_advanced_retry(max_attempts=3)
        async def test_function() -> str:
            """Test docstring."""
            return "success"
        
        assert test_function.__name__ == "test_function"
        assert test_function.__doc__ == "Test docstring."
    
    @pytest.mark.asyncio
    async def test_advanced_retry_no_retry_on_circuit_breaker_error(self) -> None:
        """Test that circuit breaker errors are not retried."""
        call_count = 0
        
        @with_advanced_retry(max_attempts=3, backoff_factor=0.1)
        async def test_function() -> str:
            nonlocal call_count
            call_count += 1
            raise CircuitBreakerError("Circuit breaker is open")
        
        with pytest.raises(CircuitBreakerError):
            _ = await test_function()
        
        # Should only be called once (no retry on circuit breaker error)
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_advanced_retry_no_retry_on_timeout_error(self) -> None:
        """Test that timeout errors are not retried."""
        call_count = 0
        
        @with_advanced_retry(max_attempts=3, backoff_factor=0.1)
        async def test_function() -> str:
            nonlocal call_count
            call_count += 1
            raise RetryTimeoutError("Operation timed out")
        
        with pytest.raises(RetryTimeoutError):
            _ = await test_function()
        
        # Should only be called once (no retry on timeout error)
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_advanced_retry_backoff_timing(self) -> None:
        """Test that advanced retry implements proper backoff timing."""
        call_count = 0
        start_time = time.time()
        
        @with_advanced_retry(max_attempts=3, backoff_factor=0.2, jitter=False)
        async def test_function() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"
        
        result = await test_function()
        end_time = time.time()
        
        assert result == "success"
        assert call_count == 3
        
        # Should have waited at least 0.2 + 0.4 = 0.6 seconds
        # (backoff_factor^0 + backoff_factor^1)
        assert end_time - start_time >= 0.6