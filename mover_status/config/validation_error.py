"""
Custom exception for configuration validation errors.

This module provides the ValidationError class, which is raised when
configuration validation fails.
"""

from typing import final


@final
class ValidationError(Exception):
    """
    Exception raised when configuration validation fails.

    This exception includes information about the validation errors,
    such as missing required fields, incorrect field types, or invalid values.
    """

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        """
        Initialize the ValidationError.

        Args:
            message: The error message.
            errors: Optional list of specific validation errors.
        """
        self.errors: list[str] = errors or []
        error_details = "\n - " + "\n - ".join(self.errors) if self.errors else ""
        super().__init__(f"{message}{error_details}")
