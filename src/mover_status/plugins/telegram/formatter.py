"""Telegram-specific HTML message formatter.

Responsibilities (Requirements 9.1–9.4):
- Build provider-specific HTML payloads without leaking into core modules
- Perform placeholder replacement through the shared template system
- Convert ETC timestamps into human-readable datetime strings
- Escape HTML entities to prevent markup injection
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import html
import math
from typing import Final, override

from mover_status.types.models import NotificationData
from mover_status.types.protocols import MessageFormatter
from mover_status.utils.template import replace_placeholders

_TITLE_MAP: Final[dict[str, str]] = {
    "started": "Mover Started",
    "progress": "Mover Progress",
    "completed": "Mover Completed",
}
_DEFAULT_TITLE: Final[str] = "Mover Update"
_CALCULATING_LABEL: Final[str] = "Calculating..."


@dataclass(slots=True)
class TelegramFormatter(MessageFormatter):
    """Format NotificationData into Telegram HTML messages."""

    @override
    def format_message(self, template: str, placeholders: Mapping[str, object]) -> str:
        """Replace placeholders inside the provided template string."""
        return replace_placeholders(template, placeholders)

    @override
    def format_time(self, timestamp: datetime) -> str:
        """Convert datetime to human-readable string retaining timezone info."""
        aware = self._ensure_tz(timestamp)
        return aware.strftime("%Y-%m-%d %H:%M %Z").strip()

    def build_message(
        self,
        data: NotificationData,
        *,
        template: str,
        footer: str | None = None,
    ) -> str:
        """Create a Telegram-ready HTML message."""
        placeholders = self._build_placeholders(data)
        body = self.format_message(template, placeholders)

        sections = [
            self._build_title(data.event_type),
            body,
            self._build_metrics_block(placeholders),
        ]

        if footer:
            sections.append(self._build_footer(footer))

        return "\n".join(section for section in sections if section)

    def _build_placeholders(self, data: NotificationData) -> dict[str, str]:
        """Construct escaped placeholder values from NotificationData."""
        etc_value = (
            self.format_time(data.etc_timestamp)
            if data.etc_timestamp is not None
            else _CALCULATING_LABEL
        )

        return {
            "percent": self._escape_value(self._format_percent(data.percent)),
            "remaining_data": self._escape_value(self._safe_text(data.remaining_data)),
            "moved_data": self._escape_value(self._safe_text(data.moved_data)),
            "total_data": self._escape_value(self._safe_text(data.total_data)),
            "rate": self._escape_value(self._safe_text(data.rate)),
            "etc": self._escape_value(etc_value),
        }

    def _build_title(self, event_type: str) -> str:
        """Return bolded heading for the message."""
        title = _TITLE_MAP.get(event_type.lower(), _DEFAULT_TITLE)
        return f"<b>{html.escape(title, quote=False)}</b>"

    def _build_metrics_block(self, placeholders: Mapping[str, str]) -> str:
        """Create newline-delimited HTML metrics block."""
        entries = [
            ("Progress", f"{placeholders['percent']}%"),
            ("Remaining", placeholders["remaining_data"]),
            ("Moved", placeholders["moved_data"]),
            ("Total", placeholders["total_data"]),
            ("Rate", placeholders["rate"]),
            ("ETA", placeholders["etc"]),
        ]

        return "\n".join(f"<b>{label}:</b> {value}" for label, value in entries)

    def _build_footer(self, footer: str) -> str:
        """Render italicized footer text."""
        return f"<i>{self._escape_value(footer)}</i>"

    def _format_percent(self, percent: float) -> str:
        """Format percentage values while trimming trailing zeros."""
        if not math.isfinite(percent):
            return "0"
        rounded = round(percent, 1)
        return f"{rounded:.1f}".rstrip("0").rstrip(".")

    def _safe_text(self, value: str) -> str:
        """Normalize empty values to a safe placeholder."""
        if not value:
            return "N/A"
        stripped = value.strip()
        return stripped if stripped else "N/A"

    def _escape_value(self, value: object) -> str:
        """Escape HTML entities for Telegram formatting."""
        if value is None:
            return "N/A"
        return html.escape(str(value), quote=False)

    def _ensure_tz(self, timestamp: datetime) -> datetime:
        """Ensure timestamp has timezone info (defaulting to UTC)."""
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp


__all__ = ["TelegramFormatter"]
