"""Shared utility modules for common operations.

This package provides pure, stateless utility functions for:
- Data size formatting (bytes to human-readable)
- Time duration formatting (seconds to human-readable)
- Data rate formatting (bytes/second to human-readable)
- Message template system (placeholder-based message formatting)

All utilities maintain provider agnosticism and have no side effects.

Requirements:
- 16.1: Shared utility modules for disk usage calculation, time formatting, size formatting
- 16.3: Shared message template system for placeholder replacement
- 16.4: Pure and stateless utility functions for reuse without side effects
- 16.5: No provider-specific logic in shared utility modules
"""

from mover_status.utils.formatting import (
    format_duration,
    format_rate,
    format_size,
)
from mover_status.utils.template import (
    KNOWN_PLACEHOLDERS,
    TemplateError,
    identify_placeholders,
    load_template,
    replace_placeholders,
    validate_template,
)

__all__ = [
    # Formatting utilities
    "format_duration",
    "format_rate",
    "format_size",
    # Template system
    "KNOWN_PLACEHOLDERS",
    "TemplateError",
    "identify_placeholders",
    "load_template",
    "replace_placeholders",
    "validate_template",
]
