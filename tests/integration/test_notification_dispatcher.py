"""Integration tests for the notification dispatcher (requirement 12.3)."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

import pytest

from mover_status.core.dispatcher import NotificationDispatcher
from mover_status.plugins import ProviderRegistry
from mover_status.types import (
    HealthStatus,
    NotificationData,
    NotificationProvider,
    NotificationResult,
)
from mover_status.utils.logging import clear_correlation_id, get_correlation_id

pytestmark = pytest.mark.asyncio


def _make_notification_data(
    *,
    event_type: str = "progress",
    percent: float = 42.0,
    remaining_data: str = "58 GB",
    moved_data: str = "42 GB",
    total_data: str = "100 GB",
    rate: str = "10 MB/s",
    etc_timestamp: datetime | None = None,
    correlation_id: str = "",
) -> NotificationData:
    """Create notification data payload for integration tests."""
    resolved_etc = etc_timestamp or datetime(2024, 1, 1, tzinfo=UTC)
    return NotificationData(
        event_type=event_type,
        percent=percent,
        remaining_data=remaining_data,
        moved_data=moved_data,
        total_data=total_data,
        rate=rate,
        etc_timestamp=resolved_etc,
        correlation_id=correlation_id,
    )


class InstrumentedProvider:
    """Provider double that records dispatch metadata."""

    def __init__(
        self,
        identifier: str,
        *,
        delay: float = 0.0,
        fail_with: Exception | None = None,
        success: bool = True,
        retryable_failure: bool = False,
        record_context: bool = False,
    ) -> None:
        self.identifier: str = identifier
        self.delay: float = delay
        self.fail_with: Exception | None = fail_with
        self.success: bool = success
        self.retryable_failure: bool = retryable_failure
        self.record_context: bool = record_context
        self.calls: int = 0
        self.start_times: list[float] = []
        self.context_records: list[tuple[str, str | None]] = []
        self.was_cancelled: bool = False

    async def send_notification(self, data: NotificationData) -> NotificationResult:
        """Send notification and capture instrumentation data."""
        self.calls += 1
        self.start_times.append(time.perf_counter())
        if self.record_context:
            self.context_records.append((data.correlation_id, get_correlation_id()))
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            self.was_cancelled = True
            raise
        if self.fail_with is not None:
            raise self.fail_with
        return NotificationResult(
            success=self.success,
            provider_name=self.identifier,
            error_message=None if self.success else "failure",
            delivery_time_ms=self.delay * 1000.0,
            should_retry=self.retryable_failure if not self.success else False,
        )

    def validate_config(self) -> bool:
        return True

    async def health_check(self) -> HealthStatus:
        return HealthStatus(
            is_healthy=True,
            last_check=datetime.now(tz=UTC),
            consecutive_failures=0,
            error_message=None,
        )


async def test_notification_dispatcher_delivers_concurrently() -> None:
    """Verify concurrent dispatch shortens runtime compared to sequential execution."""
    registry: ProviderRegistry[NotificationProvider] = ProviderRegistry()
    providers = [
        InstrumentedProvider("alpha", delay=0.05),
        InstrumentedProvider("beta", delay=0.05),
        InstrumentedProvider("gamma", delay=0.05),
    ]
    for provider in providers:
        registry.register(provider.identifier, provider)

    dispatcher = NotificationDispatcher(registry, provider_timeout_seconds=0.25)
    clear_correlation_id()
    data = _make_notification_data(correlation_id="")

    start = time.perf_counter()
    results = await dispatcher.dispatch_notification(data)
    elapsed = time.perf_counter() - start

    assert len(results) == len(providers)
    assert all(result.success for result in results)
    max_delay = max(provider.delay for provider in providers)
    assert elapsed < max_delay + 0.03


async def test_exception_group_handles_mixed_outcomes() -> None:
    """Ensure mixed failures produce results without stopping healthy providers."""
    registry: ProviderRegistry[NotificationProvider] = ProviderRegistry(unhealthy_threshold=2)
    success_provider = InstrumentedProvider("alpha")
    exception_provider = InstrumentedProvider(
        "beta",
        fail_with=RuntimeError("boom"),
    )
    timeout_provider = InstrumentedProvider("gamma", delay=0.05)
    registry.register("alpha", success_provider)
    registry.register("beta", exception_provider)
    registry.register("gamma", timeout_provider)

    dispatcher = NotificationDispatcher(registry, provider_timeout_seconds=0.01)
    data = _make_notification_data(event_type="progress")

    results = await dispatcher.dispatch_notification(data)
    result_map = {result.provider_name: result for result in results}

    assert set(result_map) == {"alpha", "beta", "gamma"}
    assert result_map["alpha"].success is True
    success_health = registry.get_health("alpha")
    assert success_health is not None and success_health.is_healthy is True

    assert result_map["beta"].success is False
    assert "RuntimeError" in (result_map["beta"].error_message or "")
    failure_health = registry.get_health("beta")
    assert failure_health is not None and failure_health.is_healthy is False

    assert result_map["gamma"].success is False
    assert result_map["gamma"].should_retry is True
    timeout_health = registry.get_health("gamma")
    assert timeout_health is not None
    assert timeout_health.is_healthy is True
    assert timeout_health.consecutive_failures == 1


async def test_timeout_enforcement_cancels_slower_providers() -> None:
    """Slow providers should be cancelled quickly when exceeding timeout."""
    registry: ProviderRegistry[NotificationProvider] = ProviderRegistry()
    slow = InstrumentedProvider("slow", delay=0.2)
    fast = InstrumentedProvider("fast")
    registry.register("slow", slow)
    registry.register("fast", fast)

    dispatcher = NotificationDispatcher(registry, provider_timeout_seconds=0.05)
    data = _make_notification_data()

    start = time.perf_counter()
    results = await dispatcher.dispatch_notification(data)
    elapsed = time.perf_counter() - start
    result_map = {result.provider_name: result for result in results}

    assert result_map["fast"].success is True
    assert result_map["slow"].success is False
    assert "timed out" in (result_map["slow"].error_message or "").lower()
    assert result_map["slow"].should_retry is True
    assert slow.was_cancelled is True
    assert elapsed < slow.delay


async def test_dispatch_propagates_correlation_id_to_providers() -> None:
    """Correlation ID factory output should flow through dispatcher and providers."""
    registry: ProviderRegistry[NotificationProvider] = ProviderRegistry()
    providers = [
        InstrumentedProvider("alpha", record_context=True),
        InstrumentedProvider("beta", record_context=True),
    ]
    for provider in providers:
        registry.register(provider.identifier, provider)

    dispatcher = NotificationDispatcher(
        registry,
        provider_timeout_seconds=0.25,
        correlation_id_factory=lambda: "integration-correlation",
    )
    clear_correlation_id()
    data = _make_notification_data(correlation_id="")

    results = await dispatcher.dispatch_notification(data)

    assert len(results) == 2
    assert data.correlation_id == "integration-correlation"
    for provider in providers:
        assert provider.context_records == [("integration-correlation", "integration-correlation")]
    assert get_correlation_id() is None
