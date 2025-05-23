"""
Template notification provider implementation.

This module provides a reference implementation of a notification provider,
demonstrating best practices for creating new providers. It shows how to:

1. Inherit from the appropriate base class (ApiProvider in this case)
2. Handle configuration properly
3. Implement required abstract methods
4. Use provider-specific formatting
5. Handle errors gracefully
6. Provide comprehensive documentation

This template can be used as a starting point for creating new notification providers.
"""

import logging
import time
from typing import NotRequired, TypedDict, cast, override, Any
from collections.abc import Mapping

import requests

from mover_status.notification.formatter import RawValues
from mover_status.notification.providers.api_provider import ApiProvider
from mover_status.notification.providers.template.formatter import format_template_message

# Get logger for this module
logger = logging.getLogger(__name__)


class TemplateConfig(TypedDict, total=False):
    """Type definition for Template provider configuration."""
    enabled: bool
    api_endpoint: str
    api_key: str
    message_template: str
    timeout: int
    retry_attempts: int
    verify_ssl: bool
    custom_headers: dict[str, str]


class TemplateResponseData(TypedDict):
    """Type definition for Template API response data."""
    success: bool
    message: NotRequired[str]
    error: NotRequired[str]


class TemplateProvider(ApiProvider):
    """
    Template notification provider.

    This class serves as a reference implementation for creating notification providers.
    It demonstrates how to properly inherit from ApiProvider and implement all required
    methods while following best practices.

    The Template provider simulates sending notifications to a generic API endpoint,
    showing how to handle authentication, request formatting, and error handling.

    Attributes:
        name: The name of the notification provider.
        api_endpoint: The API endpoint URL for sending notifications.
        api_key: The API key for authentication.
        message_template: The template to use for formatting messages.
        timeout: Request timeout in seconds.
        retry_attempts: Number of retry attempts for failed requests.
        verify_ssl: Whether to verify SSL certificates.
        custom_headers: Custom headers to include in requests.
        enabled: Whether the provider is enabled.
    """

    def __init__(
        self,
        name: str,
        config: Mapping[str, Any],  # pyright: ignore[reportExplicitAny]
        metadata: Mapping[str, object] | None = None
    ) -> None:
        """
        Initialize the Template notification provider.

        Args:
            name: The name of the notification provider.
            config: The provider configuration.
            metadata: Optional metadata about the provider.
        """
        # Initialize the parent class
        super().__init__(name, config, metadata)

        # Extract Template-specific configuration values
        self.api_endpoint: str = str(self._get_config_value("api_endpoint", ""))
        self.api_key: str = str(self._get_config_value("api_key", ""))
        self.message_template: str = str(self._get_config_value("message_template", ""))

        # Handle numeric values with proper type conversion
        timeout_value = self._get_config_value("timeout", 30)
        self.timeout: int = int(timeout_value) if isinstance(timeout_value, (int, str)) else 30

        retry_value = self._get_config_value("retry_attempts", 3)
        self.retry_attempts: int = int(retry_value) if isinstance(retry_value, (int, str)) else 3

        self.verify_ssl: bool = bool(self._get_config_value("verify_ssl", True))

        # Handle custom headers with proper type checking
        custom_headers = self._get_config_value("custom_headers", {})
        if isinstance(custom_headers, dict):
            # Type ignore for the dict comprehension since we're converting unknown types to strings
            self.custom_headers: dict[str, str] = {
                str(k): str(v) for k, v in custom_headers.items()  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
            }
        else:
            self.custom_headers = {}

        # Set up API provider configuration
        self.base_url: str = self.api_endpoint
        self.headers.update(self.custom_headers)

        self._logger.debug("Template provider initialized with endpoint: %s", self.api_endpoint)

    @override
    def validate_config(self) -> list[str]:
        """
        Validate the Template provider configuration.

        This method demonstrates comprehensive configuration validation,
        checking for required fields, valid values, and logical consistency.

        Returns:
            A list of error messages. An empty list indicates a valid configuration.
        """
        errors: list[str] = []

        # Check required fields
        if not self.api_endpoint:
            errors.append("Template provider requires 'api_endpoint' to be set")
        elif not self.api_endpoint.startswith(("http://", "https://")):
            errors.append("Template provider 'api_endpoint' must be a valid HTTP/HTTPS URL")

        if not self.api_key:
            errors.append("Template provider requires 'api_key' to be set")

        # Validate numeric values
        if self.timeout <= 0:
            errors.append("Template provider 'timeout' must be greater than 0")

        if self.retry_attempts < 0:
            errors.append("Template provider 'retry_attempts' must be 0 or greater")

        return errors

    @override
    def _get_api_url(self, **kwargs: object) -> str:
        """
        Get the API URL for the Template provider.

        This method demonstrates how to construct API URLs, potentially
        with dynamic parameters.

        Args:
            **kwargs: Additional parameters for URL construction.

        Returns:
            The complete API URL.
        """
        return self.api_endpoint

    @override
    def _prepare_auth_headers(self) -> dict[str, str]:
        """
        Prepare authentication headers for the Template API.

        This method demonstrates how to implement custom authentication
        schemes beyond the default Bearer token.

        Returns:
            A dictionary of authentication headers.
        """
        auth_headers: dict[str, str] = {}

        if self.api_key:
            # Template provider uses a custom "X-API-Key" header
            auth_headers["X-API-Key"] = self.api_key

        return auth_headers

    @override
    def _prepare_request_data(
        self,
        message: str,
        raw_values: RawValues,
        **kwargs: object
    ) -> dict[str, object]:
        """
        Prepare the request data for the Template API.

        This method demonstrates how to format data for API requests,
        including message formatting and additional metadata.

        Args:
            message: The message to send.
            raw_values: Extracted and validated raw values.
            **kwargs: Additional provider-specific arguments.

        Returns:
            A dictionary containing the request data for the Template API.
        """
        # Format the message if raw_values are provided and we have a template
        formatted_message = message
        if raw_values and self.message_template:
            formatted_message = format_template_message(
                self.message_template,
                raw_values
            )
        elif self.message_template and not raw_values:
            # Use the template as-is if no raw values provided
            formatted_message = self.message_template

        # Prepare the request payload
        request_data: dict[str, object] = {
            "message": formatted_message,
            "timestamp": int(time.time()) if 'time' in globals() else 0,
            "source": "MoverStatus",
            "provider": self.name,
        }

        # Add raw values if available (for debugging/logging purposes)
        if raw_values:
            request_data["metadata"] = {
                "percent": raw_values.get("percent"),
                "eta": raw_values.get("eta"),
                "remaining_data": raw_values.get("remaining_data"),
                "current_size": raw_values.get("current_size"),
                "initial_size": raw_values.get("initial_size"),
            }

        return request_data

    def _handle_api_response(self, response: requests.Response) -> bool:
        """
        Handle the API response from the Template service.

        This method demonstrates how to parse and validate API responses,
        including error handling for different response formats.

        Args:
            response: The HTTP response from the API.

        Returns:
            True if the response indicates success, False otherwise.
        """
        try:
            # Try to parse JSON response
            response_data = response.json()  # pyright: ignore[reportAny]
            template_response = cast(TemplateResponseData, response_data)

            # Check for success indicator
            if template_response.get("success", False):
                self._logger.info("Template notification sent successfully")
                return True
            else:
                error_msg = template_response.get("error", "Unknown error")
                self._logger.error("Template API returned error: %s", error_msg)
                return False

        except ValueError as e:
            # Handle non-JSON responses
            self._logger.error("Template API returned invalid JSON: %s", e)
            return False
