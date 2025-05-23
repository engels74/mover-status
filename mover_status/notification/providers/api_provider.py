"""
API notification provider base class.

This module provides the ApiProvider base class, which implements common
functionality for API-based notification providers. It extends the BaseProvider
class and provides standardized HTTP request handling, authentication, and
error handling for API-based providers.
"""

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, override

import requests

from mover_status.notification.formatter import RawValues
from mover_status.notification.providers.base_provider import BaseProvider

# Get logger for this module
logger = logging.getLogger(__name__)


class ApiProvider(BaseProvider, ABC):
    """
    Base provider class for API-based notification providers.

    This class provides common functionality for API-based notification providers,
    including HTTP request handling, authentication, URL construction, timeout
    configuration, and standardized error handling. It extends the BaseProvider class.

    Attributes:
        name: The name of the notification provider.
        metadata: Optional metadata about the provider.
        config: The provider configuration.
        enabled: Whether the provider is enabled.
        base_url: The base URL for the API.
        api_key: The API key for authentication.
        timeout: Request timeout in seconds.
        headers: Additional headers to include in requests.
        verify_ssl: Whether to verify SSL certificates.
        http_method: HTTP method to use for requests (GET, POST, PUT, etc.).
    """

    def __init__(
        self,
        name: str,
        config: Mapping[str, Any],  # pyright: ignore[reportExplicitAny]
        metadata: Mapping[str, object] | None = None
    ) -> None:
        """
        Initialize the API provider.

        Args:
            name: The name of the notification provider.
            config: The provider configuration.
            metadata: Optional metadata about the provider.
        """
        # Initialize the parent class
        super().__init__(name, config, metadata)

        # Extract API-specific configuration values
        self.base_url: str = str(self._get_config_value("base_url", ""))
        self.api_key: str = str(self._get_config_value("api_key", ""))

        # Handle timeout with proper type conversion
        timeout_value = self._get_config_value("timeout", 10)
        if isinstance(timeout_value, (int, float)):
            self.timeout: int = int(timeout_value)
        else:
            self.timeout = 10

        # Handle headers with proper type conversion
        headers_value = self._get_config_value("headers", {})
        if isinstance(headers_value, dict):
            # Convert all keys and values to strings with proper type handling
            self.headers: dict[str, str] = {}
            for key, value in headers_value.items():  # pyright: ignore[reportUnknownVariableType]
                # Ensure both key and value are converted to strings safely
                str_key = str(key) if key is not None else ""  # pyright: ignore[reportUnknownArgumentType]
                str_value = str(value) if value is not None else ""  # pyright: ignore[reportUnknownArgumentType]
                self.headers[str_key] = str_value
        else:
            self.headers = {}

        self.verify_ssl: bool = bool(self._get_config_value("verify_ssl", True))
        self.http_method: str = str(self._get_config_value("http_method", "POST")).upper()

    @abstractmethod
    def _get_api_url(self, **kwargs: object) -> str:
        """
        Get the API URL for the request.

        Subclasses must implement this method to construct the appropriate
        API URL based on the base URL and any additional parameters.

        Args:
            **kwargs: Additional parameters that may be used to construct the URL.

        Returns:
            The complete API URL for the request.
        """
        pass

    @abstractmethod
    def _prepare_request_data(
        self,
        message: str,
        raw_values: RawValues,
        **kwargs: object
    ) -> dict[str, object]:
        """
        Prepare the request data for the API call.

        Subclasses must implement this method to define the structure
        of the data that will be sent to the API.

        Args:
            message: The message to send.
            raw_values: Extracted and validated raw values.
            **kwargs: Additional provider-specific arguments.

        Returns:
            A dictionary representing the data to send to the API.
        """
        pass

    def _prepare_auth_headers(self) -> dict[str, str]:
        """
        Prepare authentication headers for the API request.

        This method creates the appropriate authentication headers based on
        the API key. By default, it uses the "Authorization" header with
        "Bearer" prefix, but subclasses can override this for different
        authentication schemes.

        Returns:
            A dictionary of authentication headers.
        """
        auth_headers: dict[str, str] = {}

        if self.api_key:
            # Default to Bearer token authentication
            # Subclasses can override this method for different auth schemes
            auth_headers["Authorization"] = f"Bearer {self.api_key}"

        return auth_headers

    def _send_api_request(self, data: dict[str, object], **kwargs: object) -> bool:
        """
        Send the API request with the prepared data.

        This method handles the actual HTTP request to the API, including
        error handling and response validation.

        Args:
            data: The prepared request data.
            **kwargs: Additional parameters for URL construction.

        Returns:
            True if the request was successful, False otherwise.
        """
        try:
            # Get the API URL
            url = self._get_api_url(**kwargs)

            # Prepare headers
            request_headers = self.headers.copy()
            request_headers.update(self._prepare_auth_headers())

            # Ensure Content-Type is set for JSON requests
            if self.http_method in ("POST", "PUT", "PATCH") and "Content-Type" not in request_headers:
                request_headers["Content-Type"] = "application/json"

            # Send the request with proper typing
            self._logger.debug("Sending %s request to API: %s", self.http_method, url)

            # Prepare request based on HTTP method
            if self.http_method in ("POST", "PUT", "PATCH"):
                if request_headers.get("Content-Type") == "application/json":
                    response = requests.request(
                        method=self.http_method,
                        url=url,
                        json=data,
                        timeout=self.timeout,
                        headers=request_headers,
                        verify=self.verify_ssl
                    )
                else:
                    response = requests.request(
                        method=self.http_method,
                        url=url,
                        data=json.dumps(data),
                        timeout=self.timeout,
                        headers=request_headers,
                        verify=self.verify_ssl
                    )
            elif self.http_method == "GET":
                # For GET requests, add data as query parameters
                # Convert data to string parameters for requests
                params = {str(k): str(v) for k, v in data.items() if v is not None}
                response = requests.request(
                    method=self.http_method,
                    url=url,
                    params=params,
                    timeout=self.timeout,
                    headers=request_headers,
                    verify=self.verify_ssl
                )
            else:
                # For other methods, send without data
                response = requests.request(
                    method=self.http_method,
                    url=url,
                    timeout=self.timeout,
                    headers=request_headers,
                    verify=self.verify_ssl
                )

            # Raise an exception for HTTP error status codes
            response.raise_for_status()

            # Log success
            self._logger.info("API request sent successfully (status: %d)", response.status_code)
            return True

        except requests.exceptions.HTTPError as e:
            self._logger.error("HTTP error sending API request: %s", e)
            return False
        except requests.exceptions.ConnectionError as e:
            self._logger.error("Connection error sending API request: %s", e)
            return False
        except requests.exceptions.Timeout as e:
            self._logger.error("Timeout error sending API request: %s", e)
            return False
        except requests.exceptions.RequestException as e:
            self._logger.error("Request error sending API request: %s", e)
            return False
        except Exception as e:
            self._logger.error("Unexpected error sending API request: %s", e)
            return False

    @override
    def _send_notification_impl(
        self,
        message: str,
        raw_values: RawValues,
        **kwargs: object
    ) -> bool:
        """
        API-specific notification sending implementation.

        This method implements the API sending logic by preparing
        the request data and sending the API request.

        Args:
            message: The message to send.
            raw_values: Extracted and validated raw values.
            **kwargs: Additional provider-specific arguments.

        Returns:
            True if the notification was sent successfully, False otherwise.
        """
        # Prepare the request data using the subclass implementation
        data = self._prepare_request_data(message, raw_values, **kwargs)

        # Send the API request
        return self._send_api_request(data, **kwargs)

    def _validate_api_config(self) -> list[str]:
        """
        Validate API-specific configuration.

        This method validates common API configuration fields like base_url
        and api_key. Subclasses can call this method and add their own
        validation logic.

        Returns:
            A list of validation error messages.
        """
        errors: list[str] = []

        # Validate base URL
        if not self.base_url:
            errors.append("API base_url is required")
        elif not self.base_url.startswith(("http://", "https://")):
            errors.append("API base_url must start with http:// or https://")

        # Validate API key (optional for some APIs)
        if not self.api_key:
            errors.append("API api_key is required")

        # Validate HTTP method
        valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE"}
        if self.http_method not in valid_methods:
            errors.append(f"Invalid HTTP method: {self.http_method}. Must be one of: {', '.join(valid_methods)}")

        # Validate timeout
        if self.timeout <= 0:
            errors.append("API timeout must be greater than 0")

        return errors
