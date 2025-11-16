"""Tests for the Telegram HTML formatter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import cast

from mover_status.plugins.telegram.formatter import TelegramFormatter
from mover_status.types.models import NotificationData

_DEFAULT_ETC = object()


def _make_notification(
    *,
    event_type: str = "progress",
    percent: float = 42.5,
    remaining_data: str = "125 GB",
    moved_data: str = "250 GB",
    total_data: str = "375 GB",
    rate: str = "50 MB/s",
    etc_timestamp: datetime | None | object = _DEFAULT_ETC,
    correlation_id: str = "corr-telegram",
) -> NotificationData:
    resolved_etc = (
        datetime(2024, 1, 1, 12, 30, tzinfo=timezone.utc)
        if etc_timestamp is _DEFAULT_ETC
        else cast(datetime | None, etc_timestamp)
    )
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


class TestTelegramFormatter:
    """Behavior of TelegramFormatter."""

    def test_format_time_returns_readable_string(self) -> None:
        """Datetime values are rendered as human-readable UTC strings."""
        formatter = TelegramFormatter()
        timestamp = datetime(2024, 2, 20, 15, 45, tzinfo=timezone.utc)

        result = formatter.format_time(timestamp)

        assert result == "2024-02-20 15:45 UTC"

    def test_build_message_includes_sections(self) -> None:
        """HTML message combines title, template body, metrics, and footer."""
        formatter = TelegramFormatter()
        data = _make_notification()
        template = "Progress {percent}% - Remaining {remaining_data} (ETA {etc})"

        message = formatter.build_message(
            data,
            template=template,
            footer="Mover Status v1.0",
        )

        expected_etc = formatter.format_time(cast(datetime, data.etc_timestamp))
        assert message.startswith("<b>Mover Progress</b>")
        assert f"(ETA {expected_etc})" in message
        assert "<b>Progress:</b> 42.5%" in message
        assert "<b>Remaining:</b> 125 GB" in message
        assert "<i>Mover Status v1.0</i>" in message.splitlines()[-1]

    def test_placeholders_are_html_escaped(self) -> None:
        """Placeholder values are HTML-escaped to prevent markup injection."""
        formatter = TelegramFormatter()
        data = _make_notification(
            remaining_data="<remaining>",
            moved_data="<moved>",
            total_data="<total>",
            rate="<rate>",
        )

        message = formatter.build_message(
            data,
            template="{remaining_data} {moved_data} {total_data} {rate}",
        )

        assert "&lt;remaining&gt;" in message
        assert "<remaining>" not in message
        assert "&lt;moved&gt;" in message

    def test_missing_etc_uses_placeholder_text(self) -> None:
        """Missing ETC timestamp uses 'Calculating...' label."""
        formatter = TelegramFormatter()
        data = _make_notification(etc_timestamp=None)

        message = formatter.build_message(data, template="ETA {etc}")

        assert "ETA Calculating..." in message
        assert "<b>ETA:</b> Calculating..." in message
