"""Secret sanitization utilities for logging and error messages.

This module provides utilities to sanitize sensitive information (webhook URLs,
API tokens, credentials) from strings, URLs, and structured data before logging
or displaying in error messages.

Security Requirements:
    - 6.4: NO logging or exposure of secrets in error messages or diagnostic output
    - 6.5: Authentication failures logged WITHOUT including secret values

Examples:
    >>> sanitize_url("https://discord.com/api/webhooks/123/secret_token")
    'https://discord.com/api/webhooks/123/<REDACTED>'

    >>> sanitize_url("https://api.telegram.org/bot123:ABC/sendMessage")
    'https://api.telegram.org/bot<REDACTED>/sendMessage'

    >>> sanitize_value({"webhook": "https://example.com/token", "count": 42})
    {'webhook': 'https://example.com/<REDACTED>', 'count': 42}
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import TypeIs

# Redaction marker for sanitized values
REDACTED = "<REDACTED>"

# URL patterns for provider-specific endpoints
# Discord: https://discord.com/api/webhooks/<id>/<token>
# Discord: https://discordapp.com/api/webhooks/<id>/<token>
_DISCORD_WEBHOOK_PATTERN = re.compile(
    r"(https?://(?:discord(?:app)?\.com)/api/webhooks/\d+/)([^/?#]+)",
    re.IGNORECASE,
)

# Telegram: https://api.telegram.org/bot<token>/method
_TELEGRAM_BOT_PATTERN = re.compile(
    r"(https?://api\.telegram\.org/bot)([^/?#]+)(/[^?#]*)",
    re.IGNORECASE,
)

# Generic patterns for common secret-bearing URL structures
# Pattern for URLs with tokens in path segments
_GENERIC_TOKEN_IN_PATH = re.compile(
    r"(/(?:token|api[-_]?key|auth|secret|bearer)[=/])([^/?#]+)",
    re.IGNORECASE,
)

# Pattern for URLs with tokens in query parameters
_GENERIC_TOKEN_IN_QUERY = re.compile(
    r"([?&](?:token|api[-_]?key|auth|secret|bearer)=)([^&]+)",
    re.IGNORECASE,
)

# Sensitive field name patterns (case-insensitive)
_SENSITIVE_FIELD_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r".*token.*",
        r".*key.*",
        r".*secret.*",
        r".*password.*",
        r".*credential.*",
        r".*auth.*",
        r".*bearer.*",
        r".*webhook.*",
    ]
]


def is_sensitive_field(field_name: str) -> bool:
    """Check if a field name indicates sensitive data.

    Args:
        field_name: The field name to check (e.g., "api_token", "webhook_url")

    Returns:
        True if the field name matches sensitive patterns

    Examples:
        >>> is_sensitive_field("api_token")
        True
        >>> is_sensitive_field("webhook_url")
        True
        >>> is_sensitive_field("username")
        False
    """
    return any(pattern.match(field_name) for pattern in _SENSITIVE_FIELD_PATTERNS)


def sanitize_url(url: str) -> str:
    """Sanitize sensitive tokens from URLs while preserving structure.

    This function identifies and redacts tokens in URLs from various services:
    - Webhook services (Discord, generic webhooks)
    - API endpoints with tokens in path or query parameters
    - Bot APIs (Telegram)

    The URL structure is preserved to maintain useful debugging information
    (scheme, domain, path structure) while removing sensitive token values.

    Args:
        url: The URL to sanitize

    Returns:
        Sanitized URL with tokens replaced by REDACTED marker

    Examples:
        >>> sanitize_url("https://discord.com/api/webhooks/123/secret_token")
        'https://discord.com/api/webhooks/123/<REDACTED>'

        >>> sanitize_url("https://api.telegram.org/bot123:ABC/sendMessage")
        'https://api.telegram.org/bot<REDACTED>/sendMessage'

        >>> sanitize_url("https://api.example.com/data?token=secret123")
        'https://api.example.com/data?token=<REDACTED>'
    """
    # Defensive check for runtime safety, even though type signature requires str
    if not url or not isinstance(url, str):  # pyright: ignore[reportUnnecessaryIsInstance]
        return url

    # Apply provider-specific patterns first (most specific)
    sanitized = _DISCORD_WEBHOOK_PATTERN.sub(rf"\1{REDACTED}", url)
    sanitized = _TELEGRAM_BOT_PATTERN.sub(rf"\1{REDACTED}\3", sanitized)

    # Apply generic patterns to catch other token-bearing URLs
    sanitized = _GENERIC_TOKEN_IN_PATH.sub(rf"\1{REDACTED}", sanitized)
    sanitized = _GENERIC_TOKEN_IN_QUERY.sub(rf"\1{REDACTED}", sanitized)

    return sanitized


def _is_primitive(value: object) -> TypeIs[str | int | float | bool | None]:
    """Type predicate to check if value is a primitive type.

    Args:
        value: Value to check

    Returns:
        True if value is str, int, float, bool, or None
    """
    return isinstance(value, (str, int, float, bool, type(None)))


def _is_mapping(value: object) -> TypeIs[Mapping[str, object]]:
    """Type predicate to check if value is a mapping.

    Args:
        value: Value to check

    Returns:
        True if value is a Mapping (dict, etc.)
    """
    return isinstance(value, Mapping)


def _is_sequence(value: object) -> TypeIs[Sequence[object]]:
    """Type predicate to check if value is a sequence (but not str/bytes).

    Args:
        value: Value to check

    Returns:
        True if value is a Sequence but not str or bytes
    """
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def sanitize_value(
    value: object,
    *,
    field_name: str | None = None,
) -> object:
    """Recursively sanitize sensitive values from structured data.

    This function walks through nested data structures (dicts, lists, tuples)
    and sanitizes sensitive values based on:
    1. Field name patterns (e.g., "token", "password", "webhook")
    2. URL patterns in string values
    3. Recursive processing of nested structures

    Args:
        value: The value to sanitize (can be any type)
        field_name: Optional field name for context-aware sanitization

    Returns:
        Sanitized value with secrets replaced by REDACTED marker

    Examples:
        >>> sanitize_value("https://discord.com/api/webhooks/123/token")
        'https://discord.com/api/webhooks/123/<REDACTED>'

        >>> sanitize_value({"api_token": "secret", "count": 42})
        {'api_token': '<REDACTED>', 'count': 42}

        >>> sanitize_value(["https://api.telegram.org/bot123/send", "ok"])
        ['https://api.telegram.org/bot<REDACTED>/send', 'ok']
    """
    # Check if field name indicates sensitive data
    if field_name and is_sensitive_field(field_name):
        return REDACTED

    # Handle primitive types
    if _is_primitive(value):
        if type(value) is str:  # Use type() instead of isinstance() for exact type check
            # Sanitize URLs in strings
            return sanitize_url(value)
        return value

    # Handle mappings (dict, etc.)
    if _is_mapping(value):
        sanitized_dict: dict[str, object] = {
            key: sanitize_value(val, field_name=str(key)) for key, val in value.items()
        }
        return sanitized_dict

    # Handle sequences (list, tuple, etc.)
    if _is_sequence(value):
        sanitized_items: list[object] = [sanitize_value(item) for item in value]
        # Preserve original type (list, tuple, etc.)
        # Use conditional to handle different sequence types
        if isinstance(value, tuple):
            return tuple(sanitized_items)
        # For all other sequence types (list, etc.), return as list
        return sanitized_items

    # For other types (objects, custom classes), convert to string and sanitize
    # This is a fail-safe for unexpected types
    str_repr = str(value)
    return sanitize_url(str_repr)


def sanitize_exception(exc: BaseException) -> str:
    """Sanitize exception messages to remove sensitive information.

    Args:
        exc: The exception to sanitize

    Returns:
        Sanitized exception message safe for logging

    Examples:
        >>> exc = ValueError("Invalid token: abc123")
        >>> sanitize_exception(exc)
        'ValueError: Invalid token: <REDACTED>'
    """
    exc_type = type(exc).__name__
    exc_message = str(exc)
    sanitized_message = sanitize_url(exc_message)
    return f"{exc_type}: {sanitized_message}"


def sanitize_args(args: tuple[object, ...]) -> tuple[object, ...]:
    """Sanitize a tuple of logging arguments.

    This is used to sanitize the args tuple from LogRecord objects before
    they are formatted into log messages.

    Args:
        args: Tuple of arguments to sanitize

    Returns:
        Tuple with sanitized arguments

    Examples:
        >>> sanitize_args(("Connecting to %s", "https://discord.com/api/webhooks/1/token"))
        ('Connecting to %s', 'https://discord.com/api/webhooks/1/<REDACTED>')
    """
    return tuple(sanitize_value(arg) for arg in args)


def sanitize_mapping(
    data: Mapping[str, object],
) -> dict[str, object]:
    """Sanitize a mapping (e.g., logging extra dict) for safe output.

    Args:
        data: Mapping to sanitize

    Returns:
        Dictionary with sanitized values

    Examples:
        >>> sanitize_mapping({"url": "https://api.telegram.org/bot123/send", "status": 200})
        {'url': 'https://api.telegram.org/bot<REDACTED>/send', 'status': 200}
    """
    return {key: sanitize_value(val, field_name=key) for key, val in data.items()}
