"""Tests for Telegram rate limiting functionality."""

from __future__ import annotations

import asyncio
import pytest

from mover_status.plugins.telegram.rate_limiting import (
    AdvancedRateLimiter,
    RateLimitConfig,
    TokenBucket,
    QuotaTracker,
    with_rate_limiting
)


class TestTokenBucket:
    """Test suite for TokenBucket."""
    
    def test_token_bucket_initialization(self) -> None:
        """Test token bucket initialization."""
        bucket = TokenBucket(capacity=10, tokens=5, refill_rate=2.0)
        
        assert bucket.capacity == 10
        assert bucket.tokens == 5
        assert bucket.refill_rate == 2.0
    
    def test_token_bucket_consume_success(self) -> None:
        """Test successful token consumption."""
        bucket = TokenBucket(capacity=10, tokens=5, refill_rate=1.0)
        
        assert bucket.consume(3) is True
        assert abs(bucket.tokens - 2) < 0.01  # Allow for small timing differences
    
    def test_token_bucket_consume_insufficient(self) -> None:
        """Test token consumption when insufficient tokens."""
        bucket = TokenBucket(capacity=10, tokens=2, refill_rate=1.0)
        
        assert bucket.consume(3) is False
        assert abs(bucket.tokens - 2) < 0.01  # Should remain approximately unchanged
    
    def test_token_bucket_refill(self) -> None:
        """Test token bucket refill over time."""
        import time
        
        bucket = TokenBucket(capacity=10, tokens=0, refill_rate=5.0)
        
        # Manually set an earlier timestamp
        bucket.last_update = time.time() - 2.0  # 2 seconds ago
        
        # Try to consume - should trigger refill
        bucket.consume(1)
        
        # Should have refilled 10 tokens (5 per second * 2 seconds) but capped at capacity
        assert bucket.tokens == 9  # 10 (refilled) - 1 (consumed)
    
    def test_token_bucket_get_wait_time(self) -> None:
        """Test wait time calculation."""
        bucket = TokenBucket(capacity=10, tokens=1, refill_rate=2.0)
        
        # Need 3 tokens, have 1, so need 2 more
        # At 2 tokens per second, should wait 1 second
        wait_time = bucket.get_wait_time(3)
        assert wait_time == 1.0
        
        # If we have enough tokens, wait time should be 0
        wait_time = bucket.get_wait_time(1)
        assert wait_time == 0.0


class TestQuotaTracker:
    """Test suite for QuotaTracker."""
    
    def test_quota_tracker_initialization(self) -> None:
        """Test quota tracker initialization."""
        tracker = QuotaTracker(limit=100)
        
        assert tracker.limit == 100
        assert tracker.count == 0
        assert tracker.window_size == 3600.0  # 1 hour
    
    def test_quota_tracker_can_proceed(self) -> None:
        """Test quota checking."""
        tracker = QuotaTracker(limit=5)
        
        # Should allow requests under limit
        assert tracker.can_proceed() is True
        
        tracker.count = 4
        assert tracker.can_proceed() is True
        
        tracker.count = 5
        assert tracker.can_proceed() is False
    
    def test_quota_tracker_record_request(self) -> None:
        """Test request recording."""
        tracker = QuotaTracker(limit=5)
        
        tracker.record_request()
        assert tracker.count == 1
        
        tracker.record_request()
        assert tracker.count == 2
    
    def test_quota_tracker_window_reset(self) -> None:
        """Test quota window reset."""
        import time
        
        tracker = QuotaTracker(limit=5, window_size=1.0)  # 1 second window
        tracker.count = 5
        
        # Should be at limit
        assert tracker.can_proceed() is False
        
        # Manually set window start to past
        tracker.window_start = time.time() - 2.0
        
        # Should reset and allow requests
        assert tracker.can_proceed() is True
        assert tracker.count == 0


class TestAdvancedRateLimiter:
    """Test suite for AdvancedRateLimiter."""
    
    @pytest.fixture
    def rate_limiter(self) -> AdvancedRateLimiter:
        """Create a rate limiter for testing."""
        config = RateLimitConfig(
            global_limit=10,
            global_burst_limit=20,
            chat_limit=5,
            chat_burst_limit=10,
            group_limit=3,
            group_burst_limit=6,
            hourly_quota=100,
            hourly_quota_enabled=True
        )
        return AdvancedRateLimiter(config)
    
    @pytest.mark.asyncio
    async def test_rate_limiter_initialization(self, rate_limiter: AdvancedRateLimiter) -> None:
        """Test rate limiter initialization."""
        assert rate_limiter.config.global_limit == 10
        assert rate_limiter.config.global_burst_limit == 20
        assert rate_limiter.global_bucket.capacity == 20
        assert rate_limiter.quota_tracker is not None
        assert rate_limiter.quota_tracker.limit == 100
    
    @pytest.mark.asyncio
    async def test_rate_limiter_acquire_success(self, rate_limiter: AdvancedRateLimiter) -> None:
        """Test successful token acquisition."""
        chat_id = "123456"
        
        wait_time = await rate_limiter.acquire(chat_id, 1)
        assert wait_time == 0.0  # Should not wait
    
    @pytest.mark.asyncio
    async def test_rate_limiter_quota_exceeded(self) -> None:
        """Test quota exceeded behavior."""
        config = RateLimitConfig(hourly_quota=2, hourly_quota_enabled=True)
        rate_limiter = AdvancedRateLimiter(config)
        
        # First two requests should succeed
        wait_time = await rate_limiter.acquire("123", 1)
        assert wait_time == 0.0
        
        wait_time = await rate_limiter.acquire("123", 1)
        assert wait_time == 0.0
        
        # Third request should be quota limited
        wait_time = await rate_limiter.acquire("123", 1)
        assert wait_time > 0  # Should need to wait
    
    @pytest.mark.asyncio
    async def test_rate_limiter_chat_type_buckets(self, rate_limiter: AdvancedRateLimiter) -> None:
        """Test different buckets for different chat types."""
        user_chat = "123456"  # User chat (no prefix)
        group_chat = "-100123456"  # Group chat (starts with -100)
        
        # Both should initially succeed
        wait_time = await rate_limiter.acquire(user_chat, 1)
        assert wait_time == 0.0
        
        wait_time = await rate_limiter.acquire(group_chat, 1)
        assert wait_time == 0.0
        
        # Verify they use different buckets
        user_bucket = rate_limiter._get_bucket_for_chat(user_chat)
        group_bucket = rate_limiter._get_bucket_for_chat(group_chat)
        
        assert user_bucket is not group_bucket
    
    def test_rate_limiter_get_statistics(self, rate_limiter: AdvancedRateLimiter) -> None:
        """Test statistics retrieval."""
        stats = rate_limiter.get_statistics()
        
        assert "global_tokens" in stats
        assert "global_capacity" in stats
        assert "chat_buckets" in stats
        assert "group_buckets" in stats
        assert "config" in stats
        assert "quota" in stats
        
        # Check config structure
        config_stats = stats["config"]
        assert isinstance(config_stats, dict)
        assert "global_limit" in config_stats
        assert "chat_limit" in config_stats
    
    def test_rate_limiter_reset_quota(self, rate_limiter: AdvancedRateLimiter) -> None:
        """Test quota reset functionality."""
        # Simulate some usage
        if rate_limiter.quota_tracker:
            rate_limiter.quota_tracker.count = 50
        
        rate_limiter.reset_quota()
        
        if rate_limiter.quota_tracker:
            assert rate_limiter.quota_tracker.count == 0
    
    def test_rate_limiter_clear_buckets(self, rate_limiter: AdvancedRateLimiter) -> None:
        """Test bucket clearing functionality."""
        # Add some buckets
        rate_limiter.chat_buckets["123"] = TokenBucket(10, 5)
        rate_limiter.group_buckets["-100123"] = TokenBucket(10, 5)
        
        rate_limiter.clear_buckets()
        
        assert len(rate_limiter.chat_buckets) == 0
        assert len(rate_limiter.group_buckets) == 0
        assert rate_limiter.global_bucket.tokens == rate_limiter.global_bucket.capacity


class TestRateLimitingDecorator:
    """Test suite for rate limiting decorator."""
    
    @pytest.mark.asyncio
    async def test_decorator_basic_functionality(self) -> None:
        """Test basic decorator functionality."""
        config = RateLimitConfig(global_limit=1000)  # High limit to avoid blocking
        rate_limiter = AdvancedRateLimiter(config)
        
        call_count = 0
        
        @with_rate_limiting(rate_limiter)
        async def test_function() -> str:
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await test_function()
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_decorator_with_chat_id_extraction(self) -> None:
        """Test decorator with chat ID extraction."""
        config = RateLimitConfig(global_limit=1000)
        rate_limiter = AdvancedRateLimiter(config)
        
        def extract_chat_id(args: tuple[object, ...], kwargs: dict[str, object]) -> str:
            return str(kwargs.get("chat_id", "default"))
        
        call_count = 0
        
        @with_rate_limiting(rate_limiter, get_chat_id=extract_chat_id)
        async def test_function(message: str, chat_id: str) -> str:
            nonlocal call_count
            call_count += 1
            return f"sent to {chat_id}"
        
        result = await test_function("hello", chat_id="123456")
        assert result == "sent to 123456"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_decorator_rate_limiting_delay(self) -> None:
        """Test that decorator actually applies rate limiting delays."""
        # Use very restrictive limits to trigger rate limiting
        config = RateLimitConfig(
            global_limit=1,  # 1 per second
            global_burst_limit=1  # No burst capacity
        )
        rate_limiter = AdvancedRateLimiter(config)
        
        # First exhaust the bucket
        await rate_limiter.acquire("test", 1)
        
        @with_rate_limiting(rate_limiter)
        async def test_function() -> str:
            return "success"
        
        # This should be delayed due to rate limiting
        start_time = asyncio.get_event_loop().time()
        await test_function()
        end_time = asyncio.get_event_loop().time()
        
        # Should have waited some time (though we can't be too precise in tests)
        assert end_time - start_time >= 0.01  # At least some delay
    
    @pytest.mark.asyncio
    async def test_decorator_exception_handling(self) -> None:
        """Test decorator handles exceptions in chat ID extraction."""
        config = RateLimitConfig(global_limit=1000)
        rate_limiter = AdvancedRateLimiter(config)
        
        def failing_extract_chat_id(args: tuple[object, ...], kwargs: dict[str, object]) -> str:
            raise ValueError("Failed to extract chat ID")
        
        call_count = 0
        
        @with_rate_limiting(rate_limiter, get_chat_id=failing_extract_chat_id)
        async def test_function() -> str:
            nonlocal call_count
            call_count += 1
            return "success"
        
        # Should still work, using default "global" chat ID
        result = await test_function()
        assert result == "success"
        assert call_count == 1


class TestRateLimitingIntegration:
    """Integration tests for rate limiting with realistic scenarios."""
    
    @pytest.mark.asyncio
    async def test_burst_handling(self) -> None:
        """Test burst capacity handling."""
        config = RateLimitConfig(
            global_limit=2,  # 2 per second
            global_burst_limit=5,  # Burst of 5
            chat_limit=1,  # 1 per second per chat
            chat_burst_limit=3  # Burst of 3 per chat
        )
        rate_limiter = AdvancedRateLimiter(config)
        
        chat_id = "123456"
        
        # Should be able to consume burst capacity quickly
        for i in range(3):
            wait_time = await rate_limiter.acquire(chat_id, 1)
            assert wait_time == 0.0, f"Iteration {i} should not wait"
        
        # Fourth request should be rate limited
        wait_time = await rate_limiter.acquire(chat_id, 1)
        assert wait_time > 0, "Fourth request should be rate limited"
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self) -> None:
        """Test handling of concurrent requests from different chats."""
        config = RateLimitConfig(
            global_limit=10,
            global_burst_limit=20,
            chat_limit=5,
            chat_burst_limit=10
        )
        rate_limiter = AdvancedRateLimiter(config)
        
        async def make_request(chat_id: str) -> float:
            return await rate_limiter.acquire(chat_id, 1)
        
        # Make concurrent requests from different chats
        chat_ids = [f"chat_{i}" for i in range(5)]
        tasks = [make_request(chat_id) for chat_id in chat_ids]
        
        results = await asyncio.gather(*tasks)
        
        # All should succeed without waiting (within burst limits)
        for result in results:
            assert result == 0.0
    
    @pytest.mark.asyncio
    async def test_quota_enforcement(self) -> None:
        """Test hourly quota enforcement."""
        config = RateLimitConfig(
            global_limit=1000,  # High limit
            hourly_quota=5,  # Very low quota
            hourly_quota_enabled=True
        )
        rate_limiter = AdvancedRateLimiter(config)
        
        chat_id = "test_chat"
        
        # First 5 requests should succeed
        for i in range(5):
            wait_time = await rate_limiter.acquire(chat_id, 1)
            assert wait_time == 0.0, f"Request {i+1} should succeed"
        
        # Sixth request should be quota limited
        wait_time = await rate_limiter.acquire(chat_id, 1)
        assert wait_time > 0, "Should be quota limited"