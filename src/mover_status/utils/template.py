"""Message template system for placeholder-based message formatting.

This module provides a pure, stateless template system for safe placeholder
replacement in notification messages. It validates templates at load time and
ensures only known placeholders are used to prevent template injection attacks.

The template system is provider-agnostic and used by all notification providers
for consistent message formatting.
"""

import re
from collections.abc import Mapping, Set
from typing import Final

# Known placeholders that can be used in templates
KNOWN_PLACEHOLDERS: Final[Set[str]] = frozenset({
    "percent",
    "remaining_data",
    "etc",
    "moved_data",
    "total_data",
    "rate",
})

# Regex pattern to identify placeholders in templates
# Matches {placeholder_name} format (lowercase letters, numbers, underscores)
PLACEHOLDER_PATTERN: Final[re.Pattern[str]] = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


class TemplateError(ValueError):
    """Raised when template validation or processing fails."""

    pass


def identify_placeholders(template: str) -> Set[str]:
    """Identify all placeholders in a template string.

    Args:
        template: Template string potentially containing {placeholder} markers

    Returns:
        Set of placeholder names found in the template (without braces)

    Example:
        >>> identify_placeholders("Progress: {percent}% - ETC: {etc}")
        {'percent', 'etc'}
    """
    matches = PLACEHOLDER_PATTERN.findall(template)
    return frozenset(matches)


def validate_template(template: str) -> None:
    """Validate that a template only uses known placeholders.

    Args:
        template: Template string to validate

    Raises:
        TemplateError: If template contains unknown placeholders

    Example:
        >>> validate_template("Progress: {percent}%")  # OK
        >>> validate_template("Progress: {unknown}")  # Raises TemplateError
    """
    placeholders = identify_placeholders(template)
    unknown = placeholders - KNOWN_PLACEHOLDERS

    if unknown:
        unknown_list = sorted(unknown)
        known_list = sorted(KNOWN_PLACEHOLDERS)
        msg = (
            f"Template contains unknown placeholders: {unknown_list}. "
            f"Known placeholders are: {known_list}"
        )
        raise TemplateError(msg)


def replace_placeholders(
    template: str, values: Mapping[str, object]
) -> str:
    """Replace placeholders in template with provided values.

    This function performs safe string substitution without evaluating
    arbitrary code. Only placeholders present in the template are replaced.

    Args:
        template: Template string with {placeholder} markers
        values: Mapping of placeholder names to replacement values

    Returns:
        Template string with placeholders replaced by their values

    Raises:
        TemplateError: If required placeholders are missing from values

    Example:
        >>> replace_placeholders(
        ...     "Progress: {percent}%",
        ...     {"percent": 75.5}
        ... )
        'Progress: 75.5%'
    """
    # Identify placeholders in template
    placeholders = identify_placeholders(template)

    # Check that all required placeholders have values
    missing = placeholders - values.keys()
    if missing:
        missing_list = sorted(missing)
        raise TemplateError(
            f"Missing values for placeholders: {missing_list}"
        )

    # Perform safe string substitution
    # Convert all values to strings for substitution
    str_values = {key: str(value) for key, value in values.items()}

    # Use str.format_map for safe substitution
    try:
        return template.format_map(str_values)
    except KeyError as e:
        # This should not happen due to our validation above,
        # but handle it defensively
        raise TemplateError(f"Failed to replace placeholder: {e}") from e


def load_template(template_str: str) -> str:
    """Load and validate a template string.

    This function validates the template at load time to ensure it only
    contains known placeholders, preventing template injection attacks.

    Args:
        template_str: Template string to load and validate

    Returns:
        The validated template string

    Raises:
        TemplateError: If template validation fails

    Example:
        >>> load_template("Progress: {percent}% complete")
        'Progress: {percent}% complete'
    """
    validate_template(template_str)
    return template_str

