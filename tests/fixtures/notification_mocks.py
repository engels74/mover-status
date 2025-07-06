"""Enhanced mock providers and utilities for notification testing."""

from __future__ import annotations

import asyncio
import random
import time
from typing import TYPE_CHECKING, override, Literal, cast
from collections.abc import Mapping
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass

from mover_status.notifications.base.provider import NotificationProvider
from mover_status.notifications.models.message import Message

if TYPE_CHECKING:
    pass


@dataclass
class MockProviderStats:
    """Statistics tracking for mock providers."""
    
    send_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_processing_time: float = 0.0
    last_message: Message | None = None
    first_message_time: float | None = None
    last_message_time: float | None = None
    
    @property
    def average_processing_time(self) -> float:
        """Calculate average processing time per message."""
        if self.send_count == 0:
            return 0.0
        return self.total_processing_time / self.send_count
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.send_count == 0:
            return 0.0
        return (self.success_count / self.send_count) * 100.0
    
    @property
    def throughput(self) -> float:
        """Calculate messages per second throughput."""
        if not self.first_message_time or not self.last_message_time:
            return 0.0
        
        time_span = self.last_message_time - self.first_message_time
        if time_span <= 0:
            return 0.0
            
        return self.send_count / time_span


class EnhancedMockProvider(NotificationProvider):
    """Enhanced mock provider with comprehensive testing features."""
    
    def __init__(
        self, 
        config: Mapping[str, object], 
        name: str = "enhanced_mock",
        *,
        base_delay: float = 0.01,
        delay_variance: float = 0.005,
        failure_rate: float = 0.0,
        failure_patterns: list[str] | None = None,
        rate_limit: int | None = None,
        rate_limit_window: float = 1.0
    ) -> None:
        super().__init__(config)
        self.name: str = name
        self.base_delay: float = base_delay
        self.delay_variance: float = delay_variance
        self.failure_rate: float = failure_rate
        self.failure_patterns: list[str] = failure_patterns or []
        self.rate_limit: int | None = rate_limit
        self.rate_limit_window: float = rate_limit_window
        
        # State tracking
        self.send_calls: list[Message] = []
        self.stats: MockProviderStats = MockProviderStats()
        self.validation_calls: int = 0
        self.rate_limit_timestamps: list[float] = []
        
        # Hooks for testing
        self.pre_send_hook: AsyncMock = AsyncMock()
        self.post_send_hook: AsyncMock = AsyncMock()
        self.validation_hook: MagicMock = MagicMock()
        
    @override
    async def send_notification(self, message: Message) -> bool:
        """Enhanced send notification with realistic behavior simulation."""
        # Record timing
        start_time = time.time()
        if self.stats.first_message_time is None:
            self.stats.first_message_time = start_time
        self.stats.last_message_time = start_time
        
        # Pre-send hook
        await self.pre_send_hook(message)
        
        # Rate limiting check
        if self.rate_limit is not None:
            await self._check_rate_limit()
        
        # Simulate network delay with variance
        delay = self.base_delay + random.uniform(-self.delay_variance, self.delay_variance)
        if delay > 0:
            await asyncio.sleep(delay)
        
        # Update statistics
        self.stats.send_count += 1
        self.send_calls.append(message)
        self.stats.last_message = message
        
        # Simulate failures
        should_fail = self._should_fail(message)
        
        if should_fail:
            self.stats.failure_count += 1
            error_msg = f"Mock failure from {self.name}: {random.choice(['Network error', 'API error', 'Timeout'])}"
            await self.post_send_hook(message, success=False, error=error_msg)
            raise Exception(error_msg)
        
        # Success case
        self.stats.success_count += 1
        processing_time = time.time() - start_time
        self.stats.total_processing_time += processing_time
        
        await self.post_send_hook(message, success=True, error=None)
        return True
    
    @override
    def validate_config(self) -> None:
        """Enhanced config validation with hook."""
        self.validation_calls += 1
        self.validation_hook(self.config)
        
        # Simulate validation logic
        required_fields = ["api_key", "endpoint"]
        for field in required_fields:
            if field not in self.config:
                raise ValueError(f"Missing required field: {field}")
        
        # Type validation
        if "enabled" in self.config and not isinstance(self.config["enabled"], bool):
            raise ValueError("enabled must be a boolean")
            
        if "timeout" in self.config:
            timeout = self.config["timeout"]
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                raise ValueError("timeout must be a positive number")
    
    @override
    def get_provider_name(self) -> str:
        """Get provider name."""
        return self.name
    
    async def _check_rate_limit(self) -> None:
        """Check and enforce rate limiting."""
        if self.rate_limit is None:
            return
            
        current_time = time.time()
        
        # Remove old timestamps outside the window
        cutoff_time = current_time - self.rate_limit_window
        self.rate_limit_timestamps = [
            ts for ts in self.rate_limit_timestamps if ts > cutoff_time
        ]
        
        # Check if we're at the rate limit
        if len(self.rate_limit_timestamps) >= self.rate_limit:
            # Calculate wait time
            oldest_timestamp = min(self.rate_limit_timestamps)
            wait_time = self.rate_limit_window - (current_time - oldest_timestamp)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
        
        # Record this request
        self.rate_limit_timestamps.append(current_time)
    
    def _should_fail(self, message: Message) -> bool:
        """Determine if this message should fail based on failure patterns."""
        # Random failure rate
        if random.random() < self.failure_rate:
            return True
        
        # Pattern-based failures
        for pattern in self.failure_patterns:
            if pattern in message.title.lower() or pattern in message.content.lower():
                return True
        
        return False
    
    def reset_stats(self) -> None:
        """Reset all statistics and call history."""
        self.send_calls.clear()
        self.stats = MockProviderStats()
        self.validation_calls = 0
        self.rate_limit_timestamps.clear()
        self.pre_send_hook.reset_mock()
        self.post_send_hook.reset_mock()
        self.validation_hook.reset_mock()


class ReliableMockProvider(EnhancedMockProvider):
    """Mock provider that simulates a reliable service."""
    
    def __init__(self, config: Mapping[str, object], name: str = "reliable_mock") -> None:
        super().__init__(
            config,
            name,
            base_delay=0.01,
            delay_variance=0.002,
            failure_rate=0.001,  # 0.1% failure rate
            rate_limit=1000,     # High rate limit
            rate_limit_window=1.0
        )


class UnreliableMockProvider(EnhancedMockProvider):
    """Mock provider that simulates an unreliable service."""
    
    def __init__(self, config: Mapping[str, object], name: str = "unreliable_mock") -> None:
        super().__init__(
            config,
            name,
            base_delay=0.1,
            delay_variance=0.05,
            failure_rate=0.15,   # 15% failure rate
            failure_patterns=["error", "fail", "timeout"],
            rate_limit=10,       # Low rate limit
            rate_limit_window=1.0
        )


class SlowMockProvider(EnhancedMockProvider):
    """Mock provider that simulates a slow service."""
    
    def __init__(self, config: Mapping[str, object], name: str = "slow_mock") -> None:
        super().__init__(
            config,
            name,
            base_delay=0.5,
            delay_variance=0.2,
            failure_rate=0.05,   # 5% failure rate
            rate_limit=5,        # Very low rate limit
            rate_limit_window=1.0
        )


class FastMockProvider(EnhancedMockProvider):
    """Mock provider that simulates a fast service."""
    
    def __init__(self, config: Mapping[str, object], name: str = "fast_mock") -> None:
        super().__init__(
            config,
            name,
            base_delay=0.001,
            delay_variance=0.0005,
            failure_rate=0.0,    # No failures
            rate_limit=10000,    # Very high rate limit
            rate_limit_window=1.0
        )


@dataclass
class TestScenario:
    """Test scenario configuration."""
    
    name: str
    providers: dict[str, EnhancedMockProvider]
    message_count: int
    concurrent_dispatches: int = 1
    expected_success_rate: float = 95.0
    max_processing_time: float = 10.0
    description: str = ""


class NotificationTestUtils:
    """Utility functions for notification testing."""
    
    @staticmethod
    def create_test_messages(count: int, prefix: str = "Test") -> list[Message]:
        """Create a list of test messages."""
        messages = []
        priorities = ["low", "normal", "high"]
        
        for i in range(count):
            priority_str = priorities[i % len(priorities)]
            # Type assertion to satisfy type checker
            priority = cast(Literal["low", "normal", "high", "urgent"], priority_str)
            message = Message(
                title=f"{prefix} Message {i}",
                content=f"This is test message {i} with some content for testing purposes.",
                priority=priority,
                tags=[f"test_{i}", "automated", prefix.lower()],
                metadata={"test_id": str(i), "batch": prefix}
            )
            messages.append(message)
        
        return messages
    
    @staticmethod
    def create_provider_configs() -> dict[str, dict[str, object]]:
        """Create standard provider configurations for testing."""
        return {
            "reliable": {
                "enabled": True,
                "api_key": "reliable_test_key",
                "endpoint": "https://reliable.api.com",
                "timeout": 30
            },
            "unreliable": {
                "enabled": True,
                "api_key": "unreliable_test_key",
                "endpoint": "https://unreliable.api.com",
                "timeout": 10
            },
            "slow": {
                "enabled": True,
                "api_key": "slow_test_key",
                "endpoint": "https://slow.api.com",
                "timeout": 60
            },
            "fast": {
                "enabled": True,
                "api_key": "fast_test_key",
                "endpoint": "https://fast.api.com",
                "timeout": 5
            }
        }
    
    @staticmethod
    def create_test_scenarios() -> list[TestScenario]:
        """Create standard test scenarios."""
        configs = NotificationTestUtils.create_provider_configs()
        
        scenarios = [
            TestScenario(
                name="single_reliable",
                providers={"reliable": ReliableMockProvider(configs["reliable"], "reliable")},
                message_count=10,
                expected_success_rate=99.0,
                description="Single reliable provider with small message load"
            ),
            TestScenario(
                name="mixed_reliability",
                providers={
                    "reliable": ReliableMockProvider(configs["reliable"], "reliable"),
                    "unreliable": UnreliableMockProvider(configs["unreliable"], "unreliable")
                },
                message_count=50,
                expected_success_rate=80.0,  # More realistic with 15% failure rate
                description="Mixed reliable and unreliable providers"
            ),
            TestScenario(
                name="high_volume",
                providers={
                    "fast1": FastMockProvider(configs["fast"], "fast1"),
                    "fast2": FastMockProvider(configs["fast"], "fast2"),
                    "fast3": FastMockProvider(configs["fast"], "fast3")
                },
                message_count=200,
                concurrent_dispatches=5,
                expected_success_rate=99.0,
                max_processing_time=5.0,
                description="High volume with multiple fast providers"
            ),
            TestScenario(
                name="stress_test",
                providers={
                    "reliable": ReliableMockProvider(configs["reliable"], "reliable"),
                    "unreliable": UnreliableMockProvider(configs["unreliable"], "unreliable"),
                    "slow": SlowMockProvider(configs["slow"], "slow"),
                    "fast": FastMockProvider(configs["fast"], "fast")
                },
                message_count=100,
                concurrent_dispatches=3,
                expected_success_rate=80.0,
                max_processing_time=15.0,
                description="Stress test with all provider types"
            )
        ]
        
        return scenarios
    
    @staticmethod
    def analyze_test_results(
        providers: dict[str, EnhancedMockProvider],
        processing_time: float
    ) -> dict[str, object]:
        """Analyze test results and return metrics."""
        total_messages = sum(len(p.send_calls) for p in providers.values())
        total_successes = sum(p.stats.success_count for p in providers.values())
        total_failures = sum(p.stats.failure_count for p in providers.values())
        
        provider_stats = {}
        for name, provider in providers.items():
            provider_stats[name] = {
                "send_count": provider.stats.send_count,
                "success_count": provider.stats.success_count,
                "failure_count": provider.stats.failure_count,
                "success_rate": provider.stats.success_rate,
                "average_processing_time": provider.stats.average_processing_time,
                "throughput": provider.stats.throughput
            }
        
        return {
            "total_messages": total_messages,
            "total_successes": total_successes,
            "total_failures": total_failures,
            "overall_success_rate": (total_successes / total_messages * 100) if total_messages > 0 else 0,
            "total_processing_time": processing_time,
            "messages_per_second": total_messages / processing_time if processing_time > 0 else 0,
            "provider_stats": provider_stats
        }
