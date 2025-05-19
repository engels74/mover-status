"""
Telegram-specific message formatting.

This module provides functions for formatting messages specifically for the
Telegram notification provider. It leverages the common formatters from the
notification.formatter module and adds Telegram-specific formatting.
"""

from collections.abc import Mapping
from datetime import datetime

from mover_status.notification.formatter import (
    RawValues,
    FormattedValues,
    format_message,
    format_raw_values,
)


def format_html_text(text: str, bold: bool = False, italic: bool = False) -> str:
    """
    Format text with HTML tags for Telegram.

    Args:
        text: The text to format.
        bold: Whether to make the text bold.
        italic: Whether to make the text italic.

    Returns:
        The formatted text with HTML tags.

    Examples:
        >>> format_html_text("Hello")
        'Hello'
        >>> format_html_text("Hello", bold=True)
        '<b>Hello</b>'
        >>> format_html_text("Hello", italic=True)
        '<i>Hello</i>'
        >>> format_html_text("Hello", bold=True, italic=True)
        '<b><i>Hello</i></b>'
    """
    result = text

    if italic:
        result = f"<i>{result}</i>"
    if bold:
        result = f"<b>{result}</b>"

    return result


def format_telegram_eta(eta: float | None) -> str:
    """
    Format an ETA timestamp for display in Telegram.

    This function extends the common formatter.format_eta function with
    Telegram-specific formatting.

    Args:
        eta: The ETA timestamp as a Unix timestamp, or None if still calculating.

    Returns:
        A formatted string representation of the ETA for Telegram, or "Calculating..." if None.

    Examples:
        >>> format_telegram_eta(None)
        'Calculating...'
        >>> import time
        >>> current_time = time.time()
        >>> format_telegram_eta(current_time + 3600)  # 1 hour in the future
        '12:34 on May 19 (UTC)'  # Example output, actual time will vary
    """
    if eta is None:
        return "Calculating..."

    # Convert timestamp to datetime and format for Telegram
    return format_timestamp_for_telegram(eta)


def format_timestamp_for_telegram(timestamp: float) -> str:
    """
    Format a Unix timestamp for display in Telegram.

    Args:
        timestamp: The Unix timestamp to format.

    Returns:
        A formatted string representation of the timestamp for Telegram.

    Examples:
        >>> format_timestamp_for_telegram(1609459200)  # 2021-01-01 00:00:00 UTC
        '00:00 on Jan 01 (UTC)'  # Example output, timezone may vary
    """
    # Convert timestamp to datetime
    dt = datetime.fromtimestamp(timestamp)

    # Format the datetime for Telegram
    return dt.strftime("%H:%M on %b %d (%Z)")


def format_telegram_message(
    template: str,
    raw_values: RawValues,
    defaults: Mapping[str, object] | None = None,
) -> str:
    """
    Format a message for Telegram using the given template and raw values.

    This function first formats the raw values using the common formatter,
    then applies the formatted values to the template.

    Args:
        template: The message template with placeholders.
        raw_values: The raw values to format and substitute.
        defaults: Optional default values to use for missing placeholders.

    Returns:
        The formatted message for Telegram.

    Examples:
        >>> template = "Progress: <b>{percent}</b>"
        >>> raw_values = {"percent": 50}
        >>> format_telegram_message(template, raw_values)
        'Progress: <b>50%</b>'
    """
    # First, format the raw values using the common formatter
    formatted_values: FormattedValues = format_raw_values(raw_values)

    # Then, apply the formatted values to the template
    return format_message(template, formatted_values, defaults)
