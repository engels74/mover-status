"""
Webhook notification provider base class.

This module provides the WebhookProvider base class, which implements common
functionality for webhook-based notification providers. It extends the BaseProvider
class and provides standardized HTTP request handling, URL validation, and
error handling for webhook-based providers.
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, override

import requests

from mover_status.notification.formatter import RawValues
from mover_status.notification.providers.base_provider import BaseProvider

# Get logger for this module
logger = logging.getLogger(__name__)

# URL validation pattern for webhooks (HTTP/HTTPS only)
WEBHOOK_URL_PATTERN = re.compile(
    r'^https?://'  # http:// or https://
    + r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
    + r'localhost|'  # localhost...
    + r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
    + r'(?::\d+)?'  # optional port
    + r'(?:/?|[/?]\S+)$',
    re.IGNORECASE
)


class WebhookProvider(BaseProvider, ABC):
    """
    Base provider class for webhook-based notification providers.

    This class provides common functionality for webhook-based notification providers,
    including HTTP request handling, URL validation, timeout configuration, and
    standardized error handling. It extends the BaseProvider class.

    Attributes:
        name: The name of the notification provider.
        metadata: Optional metadata about the provider.
        config: The provider configuration.
        enabled: Whether the provider is enabled.
        webhook_url: The webhook URL to send requests to.
        timeout: Request timeout in seconds.
        headers: Additional HTTP headers to send with requests.
        verify_ssl: Whether to verify SSL certificates.
        _initialized: Whether the provider has been initialized.
        _logger: Provider-specific logger instance.
    """

    def __init__(
        self,
        name: str,
        config: Mapping[str, Any],  # pyright: ignore[reportExplicitAny]
        metadata: Mapping[str, object] | None = None
    ) -> None:
        """
        Initialize the webhook provider.

        Args:
            name: The name of the notification provider.
            config: The provider configuration.
            metadata: Optional metadata about the provider.
        """
        # Initialize the parent class
        super().__init__(name, config, metadata)

        # Extract webhook-specific configuration values
        self.webhook_url: str = str(self._get_config_value("webhook_url", ""))

        # Handle timeout with proper type conversion
        timeout_value = self._get_config_value("timeout", 10)
        if isinstance(timeout_value, (int, float)):
            self.timeout: int = int(timeout_value)
        else:
            self.timeout = 10

        self.verify_ssl: bool = bool(self._get_config_value("verify_ssl", True))

        # Extract headers configuration with proper type checking
        headers_config = self._get_config_value("headers", {})
        if isinstance(headers_config, dict):
            self.headers: dict[str, str] = {}
            for k, v in headers_config.items():  # pyright: ignore[reportUnknownVariableType]
                if k is not None and v is not None:
                    # Type ignore needed due to dynamic config value types
                    self.headers[str(k)] = str(v)  # pyright: ignore[reportUnknownArgumentType]
        else:
            self.headers = {}

    def _validate_webhook_url(self) -> list[str]:
        """
        Validate the webhook URL configuration.

        Returns:
            A list of error messages. An empty list indicates a valid URL.
        """
        errors: list[str] = []

        if not self.webhook_url:
            errors.append(f"{self.name.title()} webhook_url is required")
        elif not WEBHOOK_URL_PATTERN.match(self.webhook_url):
            errors.append(f"Invalid webhook_url format: {self.webhook_url}")

        return errors

    def _prepare_request_headers(self) -> dict[str, str]:
        """
        Prepare HTTP headers for the webhook request.

        Returns:
            A dictionary of HTTP headers to send with the request.
        """
        # Start with default headers
        request_headers = {
            "Content-Type": "application/json",
            "User-Agent": f"MoverStatus/{self.name}"
        }

        # Add configured headers (they can override defaults)
        request_headers.update(self.headers)

        return request_headers

    @abstractmethod
    def _prepare_payload(
        self,
        message: str,
        raw_values: RawValues,
        **kwargs: object
    ) -> dict[str, object]:
        """
        Prepare the payload for the webhook request.

        Subclasses must implement this method to define the structure
        of the payload that will be sent to the webhook.

        Args:
            message: The message to send.
            raw_values: Extracted and validated raw values.
            **kwargs: Additional provider-specific arguments.

        Returns:
            A dictionary representing the payload to send to the webhook.
        """
        pass

    def _send_webhook_request(
        self,
        payload: dict[str, object]
    ) -> bool:
        """
        Send the webhook request with the prepared payload.

        Args:
            payload: The payload to send to the webhook.

        Returns:
            True if the request was sent successfully, False otherwise.
        """
        try:
            # Prepare headers
            headers = self._prepare_request_headers()

            # Send the request with explicit parameters to avoid type issues
            self._logger.debug("Sending webhook request to: %s", self.webhook_url)
            response = requests.post(
                url=self.webhook_url,
                data=json.dumps(payload),
                headers=headers,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()

            # Log success
            self._logger.info("Webhook notification sent successfully to %s", self.webhook_url)
            return True

        except requests.exceptions.HTTPError as e:
            self._logger.error("HTTP error sending webhook to %s: %s", self.webhook_url, e)
            return False
        except requests.exceptions.ConnectionError as e:
            self._logger.error("Connection error sending webhook to %s: %s", self.webhook_url, e)
            return False
        except requests.exceptions.Timeout as e:
            self._logger.error("Timeout error sending webhook to %s: %s", self.webhook_url, e)
            return False
        except requests.exceptions.RequestException as e:
            self._logger.error("Request error sending webhook to %s: %s", self.webhook_url, e)
            return False
        except Exception as e:
            self._logger.error("Unexpected error sending webhook to %s: %s", self.webhook_url, e)
            return False

    @override
    def _send_notification_impl(
        self,
        message: str,
        raw_values: RawValues,
        **kwargs: object
    ) -> bool:
        """
        Webhook-specific notification sending implementation.

        This method implements the webhook sending logic by preparing
        the payload and sending the HTTP request.

        Args:
            message: The message to send.
            raw_values: Extracted and validated raw values.
            **kwargs: Additional provider-specific arguments.

        Returns:
            True if the notification was sent successfully, False otherwise.
        """
        # Prepare the payload using the subclass implementation
        payload = self._prepare_payload(message, raw_values, **kwargs)

        # Send the webhook request
        return self._send_webhook_request(payload)

    @override
    def _initialize_provider(self) -> bool:
        """
        Webhook provider-specific initialization logic.

        This method performs webhook-specific initialization, including
        URL validation and connectivity checks.

        Returns:
            True if initialization was successful, False otherwise.
        """
        # Validate webhook URL
        url_errors = self._validate_webhook_url()
        if url_errors:
            for error in url_errors:
                self._logger.error("Webhook initialization error: %s", error)
            return False

        self._logger.debug("Webhook provider initialized with URL: %s", self.webhook_url)
        return True
