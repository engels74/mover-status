"""Discord-specific message formatter for embed payloads.

Responsibilities (Requirements 9.1–9.4):
- Build self-contained embed structures for the Discord plugin
- Perform placeholder replacement using the shared template system
- Convert ETC timestamps to Discord's `<t:unix:R>` format
- Apply progress-based color coding with optional overrides
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, override

from mover_status.types.models import NotificationData
from mover_status.types.protocols import MessageFormatter
from mover_status.utils.template import replace_placeholders

# Color palette derived from the legacy bash implementation for continuity.
_COLOR_STOPS: Final[tuple[tuple[float, int], ...]] = (
    (34.0, 0xFF8080),  # Light red for early progress
    (65.0, 0xFFA500),  # Light orange for mid progress
    (100.0, 0x90EE90),  # Light green near completion
)
_COMPLETION_COLOR: Final[int] = 0x00FF00  # Bright green on completion
_DEFAULT_COLOR: Final[int] = 0x5865F2  # Discord blurple fallback

_TITLE_MAP: Final[dict[str, str]] = {
    "started": "Mover Started",
    "progress": "Mover Progress",
    "completed": "Mover Completed",
}
_DEFAULT_TITLE: Final[str] = "Mover Update"
_CALCULATING_LABEL: Final[str] = "Calculating..."


@dataclass(slots=True)
class DiscordFormatter(MessageFormatter):
    """Format NotificationData into Discord embed payloads."""

    @override
    def format_message(self, template: str, placeholders: Mapping[str, object]) -> str:
        """Replace placeholders in the provided template."""
        return replace_placeholders(template, placeholders)

    @override
    def format_time(self, timestamp: datetime) -> str:
        """Convert datetime instance to Discord relative timestamp."""
        unix_timestamp = int(self._ensure_tz(timestamp).timestamp())
        return f"<t:{unix_timestamp}:R>"

    def build_embed(
        self,
        data: NotificationData,
        *,
        template: str,
        footer: str | None = None,
        color_override: int | None = None,
    ) -> dict[str, object]:
        """Create a Discord embed dictionary ready for JSON serialization."""
        placeholder_values = self._build_placeholders(data)
        description = self.format_message(template, placeholder_values)
        embed_color = color_override if color_override is not None else self._resolve_color(data)

        embed: dict[str, object] = {
            "title": self._resolve_title(data.event_type),
            "description": description,
            "color": embed_color,
            "timestamp": datetime.now(UTC).isoformat(),
            "fields": self._build_fields(placeholder_values),
        }

        if footer:
            embed["footer"] = {"text": footer}

        return embed

    def _build_placeholders(self, data: NotificationData) -> dict[str, str]:
        """Construct placeholder values from NotificationData."""
        etc_value = self.format_time(data.etc_timestamp) if data.etc_timestamp is not None else _CALCULATING_LABEL

        return {
            "percent": self._format_percent(data.percent),
            "remaining_data": self._safe_value(data.remaining_data),
            "moved_data": self._safe_value(data.moved_data),
            "total_data": self._safe_value(data.total_data),
            "rate": self._safe_value(data.rate),
            "etc": etc_value,
        }

    def _build_fields(self, placeholders: Mapping[str, str]) -> list[dict[str, object]]:
        """Create embed fields for key metrics."""
        moved_total = f"{placeholders['moved_data']} / {placeholders['total_data']}"
        progress_value = f"{placeholders['percent']}%"

        return [
            {"name": "Progress", "value": progress_value, "inline": True},
            {"name": "Remaining", "value": placeholders["remaining_data"], "inline": True},
            {"name": "Transfer Rate", "value": placeholders["rate"], "inline": True},
            {"name": "Moved / Total", "value": moved_total, "inline": True},
            {"name": "ETA", "value": placeholders["etc"], "inline": True},
        ]

    def _resolve_color(self, data: NotificationData) -> int:
        """Determine embed color using progress thresholds."""
        percent = data.percent
        if not math.isfinite(percent):
            return _DEFAULT_COLOR

        if data.event_type.lower() == "completed" or percent >= 100.0:
            return _COMPLETION_COLOR

        clamped = max(0.0, percent)
        for threshold, color in _COLOR_STOPS:
            if clamped <= threshold:
                return color
        return _COLOR_STOPS[-1][1]

    def _resolve_title(self, event_type: str) -> str:
        """Map event type to a human-readable embed title."""
        return _TITLE_MAP.get(event_type.lower(), _DEFAULT_TITLE)

    def _format_percent(self, percent: float) -> str:
        """Format percentage values without trailing zeros."""
        if not math.isfinite(percent):
            return "0"
        rounded = round(percent, 1)
        return f"{rounded:.1f}".rstrip("0").rstrip(".")

    def _safe_value(self, value: str) -> str:
        """Guard against empty strings in placeholder values."""
        return value if value else "N/A"

    def _ensure_tz(self, timestamp: datetime) -> datetime:
        """Ensure timestamps are timezone-aware for consistent conversion."""
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC)


__all__ = ["DiscordFormatter"]
