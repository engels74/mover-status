"""Tests for the NotificationDispatcher core component."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import cast

import pytest
from _pytest.logging import LogCaptureFixture

from mover_status.core.dispatcher import NotificationDispatcher
from mover_status.plugins import ProviderRegistry
from mover_status.types import (
    HealthStatus,
    NotificationData,
    NotificationProvider,
    NotificationResult,
)
from mover_status.utils.logging import clear_correlation_id, get_correlation_id


def _make_notification_data(
    *,
    event_type: str = "progress",
    percent: float = 50.0,
    remaining_data: str = "100 GB",
    moved_data: str = "100 GB",
    total_data: str = "200 GB",
    rate: str = "10 MB/s",
    etc_timestamp: datetime | None = None,
    correlation_id: str = "initial-id",
) -> NotificationData:
    """Create NotificationData with sensible defaults for tests."""
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


class StubProvider:
    """Test double implementing the NotificationProvider Protocol."""

    def __init__(
        self,
        name: str,
        *,
        delay: float = 0.0,
        fail_with: Exception | None = None,
        success: bool = True,
        retryable_failure: bool = False,
    ) -> None:
        self.name: str = name
        self.delay: float = delay
        self.fail_with: Exception | None = fail_with
        self.success: bool = success
        self.retryable_failure: bool = retryable_failure
        self.calls: int = 0

    async def send_notification(self, data: NotificationData) -> NotificationResult:
        _ = data
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail_with is not None:
            raise self.fail_with
        return NotificationResult(
            success=self.success,
            provider_name=self.name,
            error_message=None if self.success else "failure",
            delivery_time_ms=5.0,
            should_retry=self.retryable_failure if not self.success else False,
        )

    def validate_config(self) -> bool:  # pragma: no cover - protocol compliance
        return True

    async def health_check(self) -> HealthStatus:  # pragma: no cover - protocol compliance
        return HealthStatus(
            is_healthy=True,
            last_check=datetime.now(tz=UTC),
            consecutive_failures=0,
            error_message=None,
        )


@pytest.mark.asyncio
async def test_dispatch_success_sets_correlation_id_and_records_results() -> None:
    """Dispatcher should send to healthy providers and generate correlation IDs."""
    registry: ProviderRegistry[NotificationProvider] = ProviderRegistry(unhealthy_threshold=1)
    provider = StubProvider("alpha")
    registry.register("alpha", provider)
    dispatcher = NotificationDispatcher(
        registry,
        provider_timeout_seconds=1.0,
        correlation_id_factory=lambda: "generated-id",
    )

    clear_correlation_id()
    data = _make_notification_data(correlation_id="")

    results = await dispatcher.dispatch_notification(data)

    assert len(results) == 1
    assert results[0].success is True
    assert provider.calls == 1
    assert data.correlation_id == "generated-id"
    assert get_correlation_id() is None


@pytest.mark.asyncio
async def test_dry_run_logs_payload_and_skips_provider_calls(
    caplog: LogCaptureFixture,
) -> None:
    """Dry-run mode should log notification data without invoking providers."""
    registry: ProviderRegistry[NotificationProvider] = ProviderRegistry(unhealthy_threshold=1)
    provider = StubProvider("alpha")
    registry.register("alpha", provider)
    dispatcher = NotificationDispatcher(
        registry,
        provider_timeout_seconds=1.0,
        dry_run_enabled=True,
    )

    data = _make_notification_data(event_type="started", correlation_id="")
    caplog.set_level(logging.INFO)

    results = await dispatcher.dispatch_notification(data)

    assert provider.calls == 0
    assert len(results) == 1
    assert results[0].success is True
    assert data.correlation_id  # correlation ID should still be generated
    dry_run_logs = [record for record in caplog.records if record.message == "Dry-run notification recorded"]
    assert dry_run_logs, "Dry-run dispatch should be logged"
    # Access dynamic attribute added via extra={} in logging call
    payload = cast(dict[str, object], dry_run_logs[0].notification_payload)  # pyright: ignore[reportAttributeAccessIssue]
    assert payload["event_type"] == "started"
    assert payload["correlation_id"] == data.correlation_id


@pytest.mark.asyncio
async def test_unhealthy_providers_are_skipped() -> None:
    """Dispatcher should ignore providers marked unhealthy."""
    registry: ProviderRegistry[NotificationProvider] = ProviderRegistry(unhealthy_threshold=1)
    healthy = StubProvider("healthy")
    failing = StubProvider("failing")
    registry.register("healthy", healthy)
    registry.register("failing", failing)
    _ = registry.record_failure("failing", error_message="previous failure")

    dispatcher = NotificationDispatcher(registry, provider_timeout_seconds=1.0)
    data = _make_notification_data()

    results = await dispatcher.dispatch_notification(data)

    assert len(results) == 1
    assert healthy.calls == 1
    assert failing.calls == 0
    assert results[0].provider_name == "healthy"


@pytest.mark.asyncio
async def test_timeout_failure_does_not_block_other_providers(
    caplog: LogCaptureFixture,
) -> None:
    """Per-provider timeout should mark one provider unhealthy and allow others to succeed."""
    registry: ProviderRegistry[NotificationProvider] = ProviderRegistry(unhealthy_threshold=1)
    slow = StubProvider("slow", delay=0.05)
    fast = StubProvider("fast")
    registry.register("slow", slow)
    registry.register("fast", fast)

    dispatcher = NotificationDispatcher(registry, provider_timeout_seconds=0.01)
    data = _make_notification_data()
    caplog.set_level(logging.WARNING)

    results = await dispatcher.dispatch_notification(data)

    assert len(results) == 2
    slow_result = next(result for result in results if result.provider_name == "slow")
    fast_result = next(result for result in results if result.provider_name == "fast")

    assert slow_result.success is False
    assert "timed out" in (slow_result.error_message or "")
    assert fast_result.success is True
    slow_health = registry.get_health("slow")
    assert slow_health is not None
    assert slow_health.is_healthy is False
    timeout_logs = [record for record in caplog.records if "timed out" in record.message]
    assert timeout_logs, "Timeout warning should be logged"


@pytest.mark.asyncio
async def test_retryable_failure_marks_provider_for_retry() -> None:
    """Retryable failures should keep provider eligible in registry."""
    registry: ProviderRegistry[NotificationProvider] = ProviderRegistry(unhealthy_threshold=3)
    retrying = StubProvider("retrying", success=False, retryable_failure=True)
    registry.register("retrying", retrying)

    dispatcher = NotificationDispatcher(registry, provider_timeout_seconds=1.0)
    data = _make_notification_data()

    results = await dispatcher.dispatch_notification(data)

    assert len(results) == 1
    result = results[0]
    assert result.success is False
    health = registry.get_health("retrying")
    assert health is not None
    assert health.is_healthy is True


@pytest.mark.asyncio
async def test_permanent_failure_marks_provider_unhealthy() -> None:
    """Permanent failures should mark provider unhealthy immediately."""
    registry: ProviderRegistry[NotificationProvider] = ProviderRegistry(unhealthy_threshold=5)
    failing = StubProvider("failing", success=False, retryable_failure=False)
    registry.register("failing", failing)

    dispatcher = NotificationDispatcher(registry, provider_timeout_seconds=1.0)
    data = _make_notification_data()

    results = await dispatcher.dispatch_notification(data)

    assert len(results) == 1
    result = results[0]
    assert result.success is False
    health = registry.get_health("failing")
    assert health is not None
    assert health.is_healthy is False


@pytest.mark.asyncio
async def test_exception_group_logs_runtime_failure(
    caplog: LogCaptureFixture,
) -> None:
    """Provider runtime exception should be logged while other providers succeed."""
    registry: ProviderRegistry[NotificationProvider] = ProviderRegistry(unhealthy_threshold=1)
    failing = StubProvider("failing", fail_with=RuntimeError("boom"))
    healthy = StubProvider("healthy")
    registry.register("failing", failing)
    registry.register("healthy", healthy)
    dispatcher = NotificationDispatcher(registry, provider_timeout_seconds=1.0)
    data = _make_notification_data()
    caplog.set_level(logging.ERROR)

    results = await dispatcher.dispatch_notification(data)

    assert len(results) == 2
    failing_result = next(result for result in results if result.provider_name == "failing")
    healthy_result = next(result for result in results if result.provider_name == "healthy")
    assert failing_result.success is False
    assert "RuntimeError" in (failing_result.error_message or "")
    assert healthy_result.success is True
    health = registry.get_health("failing")
    assert health is not None
    assert health.is_healthy is False
    failure_logs = [record for record in caplog.records if "Provider raised exception" in record.message]
    assert failure_logs, "Exception dispatch should be logged"
