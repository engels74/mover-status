"""Advanced rate limiting for Telegram Bot API."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict

if TYPE_CHECKING:
    from collections.abc import Callable, Awaitable

logger = logging.getLogger(__name__)


class RateLimitType(Enum):
    """Types of rate limits."""
    GLOBAL = "global"
    CHAT = "chat"
    GROUP = "group"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    
    # Global limits (per second)
    global_limit: int = 30
    global_burst_limit: int = 100
    
    # Chat-specific limits (per minute)
    chat_limit: int = 20
    chat_burst_limit: int = 50
    
    # Group-specific limits (per minute)
    group_limit: int = 20
    group_burst_limit: int = 50
    
    # Time windows
    global_window: float = 1.0  # 1 second
    chat_window: float = 60.0   # 1 minute
    group_window: float = 60.0  # 1 minute
    
    # Burst recovery rate (tokens per second)
    burst_recovery_rate: float = 0.5
    
    # Quota limits (per hour)
    hourly_quota: int = 1000
    hourly_quota_enabled: bool = True


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""
    
    capacity: int
    tokens: float
    last_update: float = field(default_factory=time.time)
    refill_rate: float = 1.0  # tokens per second
    
    def consume(self, tokens: int = 1) -> bool:
        """Consume tokens from the bucket.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens were consumed, False if not enough tokens
        """
        now = time.time()
        
        # Refill bucket based on time elapsed
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_update = now
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        
        return False
    
    def get_wait_time(self, tokens: int = 1) -> float:
        """Get time to wait before tokens are available.
        
        Args:
            tokens: Number of tokens needed
            
        Returns:
            Time to wait in seconds
        """
        if self.tokens >= tokens:
            return 0.0
        
        needed_tokens = tokens - self.tokens
        return needed_tokens / self.refill_rate


@dataclass
class QuotaTracker:
    """Quota tracking for hourly limits."""
    
    limit: int
    count: int = 0
    window_start: float = field(default_factory=time.time)
    window_size: float = 3600.0  # 1 hour
    
    def can_proceed(self) -> bool:
        """Check if request can proceed within quota.
        
        Returns:
            True if within quota, False otherwise
        """
        now = time.time()
        
        # Reset window if expired
        if now - self.window_start >= self.window_size:
            self.count = 0
            self.window_start = now
        
        return self.count < self.limit
    
    def record_request(self) -> None:
        """Record a request against the quota."""
        self.count += 1
    
    def get_reset_time(self) -> float:
        """Get time until quota resets.
        
        Returns:
            Time until reset in seconds
        """
        return self.window_size - (time.time() - self.window_start)


class AdvancedRateLimiter:
    """Advanced rate limiter with burst limits and quota management."""
    
    def __init__(self, config: RateLimitConfig | None = None) -> None:
        """Initialize rate limiter.
        
        Args:
            config: Rate limiting configuration
        """
        self.config: RateLimitConfig = config or RateLimitConfig()
        
        # Global rate limiting
        self.global_bucket: TokenBucket = TokenBucket(
            capacity=self.config.global_burst_limit,
            tokens=self.config.global_burst_limit,
            refill_rate=self.config.global_limit / self.config.global_window
        )
        
        # Per-chat rate limiting
        self.chat_buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(
                capacity=self.config.chat_burst_limit,
                tokens=self.config.chat_burst_limit,
                refill_rate=self.config.chat_limit / self.config.chat_window
            )
        )
        
        # Group-specific rate limiting
        self.group_buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(
                capacity=self.config.group_burst_limit,
                tokens=self.config.group_burst_limit,
                refill_rate=self.config.group_limit / self.config.group_window
            )
        )
        
        # Quota tracking
        self.quota_tracker: QuotaTracker | None = QuotaTracker(
            limit=self.config.hourly_quota
        ) if self.config.hourly_quota_enabled else None
        
        # Lock for thread safety
        self._lock: asyncio.Lock = asyncio.Lock()
    
    async def acquire(self, chat_id: str, tokens: int = 1) -> float:
        """Acquire tokens for a request.
        
        Args:
            chat_id: Chat ID for the request
            tokens: Number of tokens to acquire
            
        Returns:
            Time to wait before proceeding (0 if can proceed immediately)
        """
        async with self._lock:
            # Check quota first
            if self.quota_tracker and not self.quota_tracker.can_proceed():
                reset_time = self.quota_tracker.get_reset_time()
                logger.warning(f"Hourly quota exceeded, reset in {reset_time:.1f}s")
                return reset_time
            
            # Determine bucket type
            bucket = self._get_bucket_for_chat(chat_id)
            
            # Check all relevant buckets
            buckets_to_check = [self.global_bucket, bucket]
            
            # Find maximum wait time
            max_wait_time = 0.0
            for bucket_to_check in buckets_to_check:
                if not bucket_to_check.consume(tokens):
                    wait_time = bucket_to_check.get_wait_time(tokens)
                    max_wait_time = max(max_wait_time, wait_time)
            
            # If we need to wait, restore tokens and return wait time
            if max_wait_time > 0:
                # Restore tokens to buckets that successfully consumed
                for bucket_to_check in buckets_to_check:
                    bucket_to_check.tokens = min(
                        bucket_to_check.capacity,
                        bucket_to_check.tokens + tokens
                    )
                
                logger.debug(f"Rate limit hit for chat {chat_id}, waiting {max_wait_time:.2f}s")
                return max_wait_time
            
            # Record successful request
            if self.quota_tracker:
                self.quota_tracker.record_request()
            
            logger.debug(f"Rate limit check passed for chat {chat_id}")
            return 0.0
    
    def _get_bucket_for_chat(self, chat_id: str) -> TokenBucket:
        """Get the appropriate bucket for a chat ID.
        
        Args:
            chat_id: Chat ID
            
        Returns:
            Token bucket for the chat
        """
        # Determine if it's a group or individual chat
        if chat_id.startswith("-"):
            return self.group_buckets[chat_id]
        else:
            return self.chat_buckets[chat_id]
    
    def get_statistics(self) -> dict[str, int | float | dict[str, int]]:
        """Get rate limiter statistics.
        
        Returns:
            Statistics dictionary
        """
        stats: dict[str, int | float | dict[str, int]] = {
            "global_tokens": self.global_bucket.tokens,
            "global_capacity": self.global_bucket.capacity,
            "chat_buckets": len(self.chat_buckets),
            "group_buckets": len(self.group_buckets),
            "config": {
                "global_limit": self.config.global_limit,
                "global_burst_limit": self.config.global_burst_limit,
                "chat_limit": self.config.chat_limit,
                "chat_burst_limit": self.config.chat_burst_limit,
                "group_limit": self.config.group_limit,
                "group_burst_limit": self.config.group_burst_limit,
            }
        }
        
        if self.quota_tracker:
            quota_info: dict[str, int] = {
                "used": self.quota_tracker.count,
                "limit": self.quota_tracker.limit,
                "reset_time": int(self.quota_tracker.get_reset_time())
            }
            stats["quota"] = quota_info
        
        return stats
    
    def reset_quota(self) -> None:
        """Reset hourly quota (for testing purposes)."""
        if self.quota_tracker:
            self.quota_tracker.count = 0
            self.quota_tracker.window_start = time.time()
    
    def clear_buckets(self) -> None:
        """Clear all rate limiting buckets (for testing purposes)."""
        self.chat_buckets.clear()
        self.group_buckets.clear()
        self.global_bucket.tokens = self.global_bucket.capacity


def with_rate_limiting(
    rate_limiter: AdvancedRateLimiter,
    get_chat_id: Callable[[tuple[object, ...], dict[str, object]], str] | None = None
) -> Callable[[Callable[..., Awaitable[object]]], Callable[..., Awaitable[object]]]:
    """Decorator to apply rate limiting to async functions.
    
    Args:
        rate_limiter: Rate limiter instance
        get_chat_id: Function to extract chat ID from function arguments
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable[..., Awaitable[object]]) -> Callable[..., Awaitable[object]]:
        async def wrapper(*args: object, **kwargs: object) -> object:
            # Extract chat ID
            chat_id = "global"
            if get_chat_id:
                try:
                    chat_id = get_chat_id(args, kwargs)
                except Exception:
                    logger.warning("Failed to extract chat ID for rate limiting")
            
            # Apply rate limiting
            wait_time = await rate_limiter.acquire(chat_id)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            
            # Execute function
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator