"""Notification dispatcher coordinating concurrent provider delivery.

This module implements the NotificationDispatcher class responsible for
dispatching notifications to all healthy providers concurrently using
asyncio.TaskGroup with per-provider timeouts and correlation ID tracking.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from uuid import uuid4

from mover_status.plugins.registry import ProviderRegistry
from mover_status.types import NotificationData, NotificationProvider, NotificationResult
from mover_status.utils.logging import (
    clear_correlation_id,
    get_logger,
    log_with_context,
    set_correlation_id,
)

__all__ = ["NotificationDispatcher"]

type CorrelationIDFactory = Callable[[], str]


class NotificationDispatcher:
    """Dispatch notifications concurrently to all healthy providers."""

    def __init__(
        self,
        registry: ProviderRegistry[NotificationProvider],
        *,
        provider_timeout_seconds: float = 15.0,
        correlation_id_factory: CorrelationIDFactory | None = None,
        logger_obj: logging.Logger | None = None,
    ) -> None:
        if provider_timeout_seconds <= 0:
            msg = "provider_timeout_seconds must be greater than zero"
            raise ValueError(msg)

        self._registry: ProviderRegistry[NotificationProvider] = registry
        self._provider_timeout_seconds: float = provider_timeout_seconds
        self._correlation_id_factory: CorrelationIDFactory = (
            correlation_id_factory or (lambda: uuid4().hex)
        )
        self._logger: logging.Logger = logger_obj or get_logger(__name__)

    async def dispatch_notification(self, data: NotificationData) -> tuple[NotificationResult, ...]:
        """Dispatch notification data to all healthy providers concurrently."""
        providers = self._collect_healthy_providers()
        if not providers:
            log_with_context(
                self._logger,
                logging.WARNING,
                "No healthy providers available for notification dispatch",
                extra={"event_type": data.event_type},
            )
            return ()

        correlation_id = self._ensure_correlation_id(data)
        set_correlation_id(correlation_id)

        log_with_context(
            self._logger,
            logging.INFO,
            "Dispatching notification",
            extra={
                "event_type": data.event_type,
                "percent": data.percent,
                "provider_count": len(providers),
            },
        )

        ordered_identifiers = [identifier for identifier, _ in providers]
        results: dict[str, NotificationResult] = {}

        async def _dispatch_single(identifier: str, provider: NotificationProvider) -> None:
            start = time.perf_counter()
            result: NotificationResult | None = None
            try:
                async with asyncio.timeout(self._provider_timeout_seconds):
                    result = await provider.send_notification(data)
            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                delivery_ms = (time.perf_counter() - start) * 1000.0
                message = (
                    "Notification delivery timed out "
                    f"after {self._provider_timeout_seconds:.2f}s"
                )
                result = NotificationResult(
                    success=False,
                    provider_name=identifier,
                    error_message=message,
                    delivery_time_ms=delivery_ms,
                )
                self._handle_provider_failure(identifier, result)
            except Exception as exc:
                delivery_ms = (time.perf_counter() - start) * 1000.0
                error_message = f"Notification dispatch failed: {type(exc).__name__}: {exc}"
                result = NotificationResult(
                    success=False,
                    provider_name=identifier,
                    error_message=error_message,
                    delivery_time_ms=delivery_ms,
                )
                self._handle_provider_failure(identifier, result)
            else:
                if result.success:
                    self._handle_provider_success(identifier, result, data)
                else:
                    self._handle_provider_failure(identifier, result)
            finally:
                if result is not None:
                    results[identifier] = result

        try:
            async with asyncio.TaskGroup() as task_group:
                for identifier, provider in providers:
                    _ = task_group.create_task(_dispatch_single(identifier, provider))
        finally:
            clear_correlation_id()

        return tuple(results[identifier] for identifier in ordered_identifiers if identifier in results)

    def _collect_healthy_providers(self) -> list[tuple[str, NotificationProvider]]:
        providers: list[tuple[str, NotificationProvider]] = []
        for identifier in self._registry.get_identifiers():
            provider = self._registry.get(identifier)
            if provider is None:
                continue
            health = self._registry.get_health(identifier)
            if health is not None and not health.is_healthy:
                continue
            providers.append((identifier, provider))
        return providers

    def _handle_provider_success(
        self,
        identifier: str,
        result: NotificationResult,
        data: NotificationData,
    ) -> None:
        _ = self._registry.record_success(identifier)
        log_with_context(
            self._logger,
            logging.INFO,
            "Notification delivered successfully",
            extra={
                "provider_identifier": identifier,
                "provider_name": result.provider_name,
                "event_type": data.event_type,
                "percent": data.percent,
                "delivery_time_ms": result.delivery_time_ms,
            },
        )

    def _handle_provider_failure(
        self,
        identifier: str,
        result: NotificationResult,
    ) -> None:
        _ = self._registry.record_failure(
            identifier,
            error_message=result.error_message,
        )
        log_with_context(
            self._logger,
            logging.ERROR,
            "Notification delivery failed",
            extra={
                "provider_identifier": identifier,
                "provider_name": result.provider_name,
                "error_message": result.error_message or "unknown error",
                "delivery_time_ms": result.delivery_time_ms,
            },
        )

    def _ensure_correlation_id(self, data: NotificationData) -> str:
        if data.correlation_id:
            return data.correlation_id
        correlation_id = self._correlation_id_factory()
        data.correlation_id = correlation_id
        return correlation_id
