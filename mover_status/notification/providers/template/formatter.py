"""
Template notification provider formatter.

This module provides formatting functions specific to the Template notification provider.
It demonstrates how to create provider-specific formatting while leveraging the common
formatting infrastructure.

This serves as a reference implementation for creating formatters for new providers.
"""

import time
from collections.abc import Mapping

from mover_status.notification.formatter import (
    RawValues,
    FormattedValues,
    format_raw_values,
    format_message,
)


def format_template_eta(eta_timestamp: float) -> str:
    """
    Format an ETA timestamp for the Template provider.

    This function demonstrates how to create provider-specific ETA formatting.
    The Template provider uses a simple, readable format.

    Args:
        eta_timestamp: The ETA as a Unix timestamp.

    Returns:
        A formatted string representation of the ETA.

    Examples:
        >>> import time
        >>> future_time = time.time() + 3600  # 1 hour from now
        >>> eta_str = format_template_eta(future_time)
        >>> "hour" in eta_str.lower() or "minute" in eta_str.lower()
        True
    """
    if eta_timestamp <= 0:
        return "Calculating..."

    current_time = time.time()
    time_remaining = eta_timestamp - current_time

    if time_remaining <= 0:
        return "Complete"

    # Convert to hours and minutes
    hours = int(time_remaining // 3600)
    minutes = int((time_remaining % 3600) // 60)

    if hours > 0:
        if minutes > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{hours}h"
    elif minutes > 0:
        return f"{minutes}m"
    else:
        return "< 1m"


def format_template_text(
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    code: bool = False,
    emoji: str = ""
) -> str:
    """
    Format text for the Template provider.

    This function demonstrates how to apply provider-specific text formatting.
    The Template provider uses markdown-style formatting.

    Args:
        text: The text to format.
        bold: Whether to make the text bold.
        italic: Whether to make the text italic.
        code: Whether to format as inline code.
        emoji: Optional emoji to prepend to the text.

    Returns:
        The formatted text.

    Examples:
        >>> format_template_text("Hello")
        'Hello'
        >>> format_template_text("Hello", bold=True)
        '**Hello**'
        >>> format_template_text("Hello", italic=True)
        '*Hello*'
        >>> format_template_text("Hello", code=True)
        '`Hello`'
        >>> format_template_text("Hello", emoji="👋")
        '👋 Hello'
    """
    result = text

    # Apply code formatting first
    if code:
        result = f"`{result}`"

    # Apply italic formatting
    if italic:
        result = f"*{result}*"

    # Apply bold formatting
    if bold:
        result = f"**{result}**"

    # Add emoji prefix
    if emoji:
        result = f"{emoji} {result}"

    return result


def format_template_progress_bar(percent: int, width: int = 20) -> str:
    """
    Create a text-based progress bar for the Template provider.

    This function demonstrates how to create visual progress indicators
    for providers that support them.

    Args:
        percent: The progress percentage (0-100).
        width: The width of the progress bar in characters.

    Returns:
        A text-based progress bar.

    Examples:
        >>> format_template_progress_bar(50)
        '[██████████          ] 50%'
        >>> format_template_progress_bar(0)
        '[                    ] 0%'
        >>> format_template_progress_bar(100)
        '[████████████████████] 100%'
    """
    # Ensure percent is within valid range
    percent = max(0, min(100, percent))

    # Calculate filled and empty portions
    filled = int((percent / 100) * width)
    empty = width - filled

    # Create the progress bar
    bar = "█" * filled + " " * empty

    return f"[{bar}] {percent}%"


def format_template_message(
    template: str,
    raw_values: RawValues,
    defaults: Mapping[str, object] | None = None,
) -> str:
    """
    Format a message for the Template provider using the given template and raw values.

    This function demonstrates how to create provider-specific message formatting
    while leveraging the common formatting infrastructure.

    Args:
        template: The message template with placeholders.
        raw_values: The raw values to format and substitute.
        defaults: Optional default values to use for missing placeholders.

    Returns:
        The formatted message for the Template provider.

    Examples:
        >>> template = "Progress: **{percent}%** - ETA: {etc}"
        >>> raw_values = {"percent": 75, "eta": 1234567890.0}
        >>> formatted = format_template_message(template, raw_values)
        >>> "75%" in formatted
        True
        >>> "ETA:" in formatted
        True
    """
    # First, format the raw values using the common formatter
    formatted_values: FormattedValues = format_raw_values(raw_values)

    # For the Template provider, we use our custom ETA formatting
    if "eta" in raw_values and raw_values["eta"] is not None:
        formatted_values["etc"] = format_template_eta(raw_values["eta"])

    # Add a progress bar if percent is available
    # Note: progress_bar is not part of the standard FormattedValues type
    # This is a template-specific extension for demonstration purposes
    if "percent" in raw_values:
        percent = int(raw_values["percent"])
        # Use type ignore since this is a template-specific extension
        formatted_values["progress_bar"] = format_template_progress_bar(percent)  # pyright: ignore[reportGeneralTypeIssues]

    # Then, apply the formatted values to the template
    return format_message(template, formatted_values, defaults)
