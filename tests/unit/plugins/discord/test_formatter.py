"""Tests for the Discord embed formatter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import cast

from mover_status.plugins.discord.formatter import DiscordFormatter
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
    correlation_id: str = "corr-123",
) -> NotificationData:
    resolved_etc = (
        datetime(2024, 1, 1, tzinfo=timezone.utc)
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


def _field_value(embed: dict[str, object], field_name: str) -> str:
    fields = cast(list[dict[str, object]], embed["fields"])
    for field in fields:
        name = field.get("name")
        if isinstance(name, str) and name == field_name:
            value = field.get("value")
            if isinstance(value, str):
                return value
    msg = f"Field {field_name} not found"
    raise AssertionError(msg)


class TestDiscordFormatter:
    """DiscordFormatter behavior."""

    def test_format_time_produces_relative_timestamp(self) -> None:
        """ETC timestamps use Discord's relative format."""
        formatter = DiscordFormatter()
        timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)

        result = formatter.format_time(timestamp)

        assert result == "<t:1704067200:R>"

    def test_build_embed_applies_template_and_fields(self) -> None:
        """Embed description and fields use placeholder values."""
        formatter = DiscordFormatter()
        data = _make_notification()
        template = "{percent}% done, {remaining_data} left (ETA {etc})"

        embed = formatter.build_embed(data, template=template, footer="Version v1.0")

        assert data.etc_timestamp is not None
        expected_etc = formatter.format_time(data.etc_timestamp)
        assert embed["title"] == "Mover Progress"
        assert embed["description"] == f"42.5% done, 125 GB left (ETA {expected_etc})"
        assert embed["color"] == 0xFFA500  # 42.5% falls into mid-range
        assert isinstance(embed["timestamp"], str)
        assert _field_value(embed, "ETA") == expected_etc
        assert _field_value(embed, "Progress") == "42.5%"
        assert embed["footer"] == {"text": "Version v1.0"}

    def test_color_override_takes_precedence(self) -> None:
        """Explicit color overrides bypass threshold logic."""
        formatter = DiscordFormatter()
        data = _make_notification(percent=10.0)

        embed = formatter.build_embed(data, template="{percent}%", color_override=0x123456)

        assert embed["color"] == 0x123456

    def test_completed_event_uses_completion_color(self) -> None:
        """Completion events always use completion color."""
        formatter = DiscordFormatter()
        data = _make_notification(event_type="completed", percent=100.0)

        embed = formatter.build_embed(data, template="{percent}% complete")

        assert embed["color"] == 0x00FF00
        assert embed["title"] == "Mover Completed"

    def test_missing_etc_timestamp_uses_placeholder(self) -> None:
        """When ETC timestamp is missing, placeholder text is used."""
        formatter = DiscordFormatter()
        data = _make_notification(etc_timestamp=None)

        embed = formatter.build_embed(data, template="{etc} soon")

        assert _field_value(embed, "ETA") == "Calculating..."
        assert embed["description"] == "Calculating... soon"

    def test_progress_field_trims_trailing_zero(self) -> None:
        """Percent formatting avoids .0 suffix."""
        formatter = DiscordFormatter()
        data = _make_notification(percent=50.0)

        embed = formatter.build_embed(data, template="{percent}% done")

        assert embed["description"] == "50% done"
        assert _field_value(embed, "Progress") == "50%"
