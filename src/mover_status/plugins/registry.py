"""Provider registry for managing notification providers.

The registry stores provider instances keyed by their identifier, keeps track
of health information, and exposes helpers to retrieve only healthy providers.
This enables the application to continue operating with healthy providers when
others experience repeated failures (requirements 5.1–5.4) while still
respecting dynamic discovery and enablement (requirements 3.1, 3.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re
from mover_status.types import HealthStatus, NotificationProvider

__all__ = ["ProviderRegistry"]

_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def _now() -> datetime:
    """Return timezone-aware current datetime for health tracking."""
    return datetime.now(tz=UTC)


@dataclass(slots=True)
class _RegistryEntry[T: NotificationProvider]:
    """Internal registry entry storing provider and health data."""

    provider: T
    health: HealthStatus | None = None


class ProviderRegistry[T: NotificationProvider]:
    """Registry for notification providers with health tracking.

    Args:
        unhealthy_threshold: Number of consecutive failures tolerated
            before the provider is considered unhealthy. Must be >= 1.
    """

    def __init__(self, *, unhealthy_threshold: int = 3) -> None:
        if unhealthy_threshold < 1:
            msg = "unhealthy_threshold must be >= 1"
            raise ValueError(msg)
        self._unhealthy_threshold: int = unhealthy_threshold
        self._entries: dict[str, _RegistryEntry[T]] = {}

    def register(
        self,
        identifier: str,
        provider: T,
        *,
        initial_health: HealthStatus | None = None,
    ) -> None:
        """Register a provider instance under the given identifier."""
        slug = self._normalize_identifier(identifier)
        if slug in self._entries:
            msg = f"Provider {slug!r} already registered"
            raise ValueError(msg)

        self._entries[slug] = _RegistryEntry(provider=provider, health=initial_health)

    def unregister(self, identifier: str) -> None:
        """Remove a provider from the registry if it exists."""
        slug = self._normalize_identifier(identifier)
        _ = self._entries.pop(slug, None)

    def __contains__(self, identifier: str) -> bool:
        """Return True if the registry contains the identifier."""
        slug = self._normalize_identifier(identifier)
        return slug in self._entries

    def get(self, identifier: str) -> T | None:
        """Return the registered provider for the identifier."""
        slug = self._normalize_identifier(identifier)
        entry = self._entries.get(slug)
        if entry is None:
            return None
        return entry.provider

    def get_all(self) -> tuple[T, ...]:
        """Return all registered providers sorted by identifier."""
        return tuple(self._entries[identifier].provider for identifier in self._sorted_identifiers())

    def get_identifiers(self) -> tuple[str, ...]:
        """Return registered provider identifiers sorted alphabetically."""
        return tuple(self._sorted_identifiers())

    def get_health(self, identifier: str) -> HealthStatus | None:
        """Return the most recent health status for the provider."""
        slug = self._normalize_identifier(identifier)
        entry = self._entries.get(slug)
        if entry is None:
            return None
        return entry.health

    def update_health(self, identifier: str, status: HealthStatus) -> HealthStatus:
        """Set the provider health status explicitly."""
        entry = self._require_entry(identifier)
        entry.health = status
        return status

    def record_success(self, identifier: str) -> HealthStatus:
        """Record a successful interaction and reset failure counters."""
        status = HealthStatus(
            is_healthy=True,
            last_check=_now(),
            consecutive_failures=0,
            error_message=None,
        )
        return self.update_health(identifier, status)

    def record_failure(
        self,
        identifier: str,
        *,
        error_message: str | None = None,
    ) -> HealthStatus:
        """Record a failure and update the health status accordingly."""
        entry = self._require_entry(identifier)
        consecutive = entry.health.consecutive_failures + 1 if entry.health else 1
        is_healthy = consecutive < self._unhealthy_threshold
        status = HealthStatus(
            is_healthy=is_healthy,
            last_check=_now(),
            consecutive_failures=consecutive,
            error_message=error_message,
        )
        entry.health = status
        return status

    def get_healthy_providers(self) -> tuple[T, ...]:
        """Return providers that are currently healthy (or unchecked)."""
        identifiers: list[str] = []
        for identifier, entry in self._entries.items():
            if entry.health is None or entry.health.is_healthy:
                identifiers.append(identifier)
        return tuple(self._entries[identifier].provider for identifier in sorted(identifiers))

    def get_unhealthy_providers(self) -> tuple[T, ...]:
        """Return providers explicitly marked unhealthy."""
        identifiers: list[str] = []
        for identifier, entry in self._entries.items():
            if entry.health is not None and not entry.health.is_healthy:
                identifiers.append(identifier)
        return tuple(self._entries[identifier].provider for identifier in sorted(identifiers))

    def _require_entry(self, identifier: str) -> _RegistryEntry[T]:
        slug = self._normalize_identifier(identifier)
        if slug not in self._entries:
            msg = f"Provider {slug!r} is not registered"
            raise KeyError(msg)
        return self._entries[slug]

    @staticmethod
    def _normalize_identifier(identifier: str) -> str:
        slug = identifier.strip().lower()
        if not _IDENTIFIER_PATTERN.match(slug):
            msg = (
                "Provider identifiers must start with a letter and contain only "
                "lowercase letters, numbers, or underscores"
            )
            raise ValueError(msg)
        return slug

    def _sorted_identifiers(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))
