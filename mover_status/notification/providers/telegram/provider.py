"""
Telegram notification provider implementation.

This module provides the implementation of the Telegram notification provider,
which sends notifications to Telegram using the Bot API.
"""

import logging
from typing import NotRequired, TypedDict, cast, override, Any
from collections.abc import Mapping

import requests

from mover_status.notification.formatter import RawValues
from mover_status.notification.providers.api_provider import ApiProvider
from mover_status.notification.providers.telegram.formatter import format_telegram_message

# Get logger for this module
logger = logging.getLogger(__name__)

# Telegram API URL
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

# Valid parse modes for Telegram
VALID_PARSE_MODES = ["HTML", "MarkdownV2", "Markdown"]


class TelegramConfig(TypedDict, total=False):
    """Type definition for Telegram provider configuration."""
    enabled: bool
    bot_token: str
    chat_id: str
    message_template: str
    parse_mode: str
    disable_notification: bool


class TelegramResponseData(TypedDict):
    """Type definition for Telegram API response data."""
    ok: bool
    result: NotRequired[dict[str, object]]
    description: NotRequired[str]


class TelegramProvider(ApiProvider):
    """
    Telegram notification provider.

    This class implements the NotificationProvider interface for sending
    notifications to Telegram using the Bot API.

    Attributes:
        name: The name of the notification provider.
        bot_token: The Telegram bot token.
        chat_id: The Telegram chat ID to send messages to.
        parse_mode: The parse mode to use for messages (HTML, MarkdownV2, Markdown).
        disable_notification: Whether to send the message silently.
        message_template: The template to use for formatting messages.
        enabled: Whether the provider is enabled.
    """

    def __init__(
        self,
        name: str,
        config: Mapping[str, Any],  # pyright: ignore[reportExplicitAny]
        metadata: Mapping[str, object] | None = None
    ) -> None:
        """
        Initialize the Telegram notification provider.

        Args:
            name: The name of the notification provider.
            config: The provider configuration.
            metadata: Optional metadata about the provider.
        """
        # Initialize the parent class
        super().__init__(name, config, metadata)

        # Extract Telegram-specific configuration values
        self.bot_token: str = str(self._get_config_value("bot_token", ""))
        self.chat_id: str = str(self._get_config_value("chat_id", ""))
        self.parse_mode: str = str(self._get_config_value("parse_mode", "HTML"))
        self.disable_notification: bool = bool(self._get_config_value("disable_notification", False))
        self.message_template: str = str(self._get_config_value("message_template", ""))

    @override
    def validate_config(self) -> list[str]:
        """
        Validate the provider configuration.

        Returns:
            A list of error messages. An empty list indicates a valid configuration.
        """
        errors: list[str] = []

        # Check required fields
        if not self.bot_token:
            errors.append("Telegram bot_token is required")

        if not self.chat_id:
            errors.append("Telegram chat_id is required")

        # Validate parse mode
        if self.parse_mode and self.parse_mode not in VALID_PARSE_MODES:
            error_msg = (f"Invalid parse_mode: {self.parse_mode}. "
                         f"Must be one of: {', '.join(VALID_PARSE_MODES)}")
            errors.append(error_msg)

        return errors

    @override
    def _get_api_url(self, **kwargs: object) -> str:
        """
        Get the Telegram API URL for sending messages.

        Args:
            **kwargs: Additional parameters (not used for Telegram).

        Returns:
            The Telegram API URL with the bot token.
        """
        return TELEGRAM_API_URL.format(token=self.bot_token)

    @override
    def _prepare_request_data(
        self,
        message: str,
        raw_values: RawValues,
        **kwargs: object
    ) -> dict[str, object]:
        """
        Prepare the request data for the Telegram API.

        Args:
            message: The message to send.
            raw_values: Extracted and validated raw values.
            **kwargs: Additional provider-specific arguments.

        Returns:
            A dictionary containing the request data for the Telegram API.
        """
        # Format the message if raw_values are provided and we have a template
        formatted_message = message
        if raw_values and self.message_template:
            formatted_message = format_telegram_message(
                self.message_template,
                raw_values
            )
        elif self.message_template and not raw_values:
            # Use the template as-is if no raw values provided
            formatted_message = self.message_template

        # Prepare the request payload
        return {
            "chat_id": self.chat_id,
            "text": formatted_message,
            "parse_mode": self.parse_mode,
            "disable_notification": self.disable_notification,
        }

    @override
    def _send_api_request(self, data: dict[str, object], **kwargs: object) -> bool:
        """
        Send the API request with Telegram-specific response validation.

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

            # Send POST request to Telegram API
            response = requests.request(
                method=self.http_method,
                url=url,
                json=data,
                timeout=self.timeout,
                headers=request_headers,
                verify=self.verify_ssl
            )

            # Raise an exception for HTTP error status codes
            response.raise_for_status()

            # Validate Telegram-specific response
            return self._validate_api_response(response)

        except requests.exceptions.RequestException as e:
            self._logger.error("HTTP error sending API request: %s", e)
            return False
        except Exception as e:
            self._logger.error("Unexpected error sending API request: %s", e)
            return False

    def _validate_api_response(self, response: requests.Response) -> bool:
        """
        Validate the Telegram API response.

        Args:
            response: The HTTP response from the Telegram API.

        Returns:
            True if the response indicates success, False otherwise.
        """
        try:
            # Parse the JSON response and cast it to a known type
            response_json = cast(dict[str, object], response.json())

            # Create our typed dict with proper validation
            response_data: TelegramResponseData = {
                # Always convert to bool to ensure type safety
                "ok": bool(response_json.get("ok", False)),
            }

            # Only add result if it exists and is a dictionary
            if "result" in response_json and isinstance(response_json["result"], dict):
                # We've verified it's a dict at runtime
                result_dict = cast(dict[str, object], response_json["result"])
                # Now we can safely assign it to our typed dict
                response_data["result"] = result_dict

            # Only add description if it exists
            if "description" in response_json:
                # Get the description value and convert to string
                description_raw = response_json.get("description", "")
                # Convert to string to ensure type safety
                response_data["description"] = str(description_raw)

            if not response_data["ok"]:
                description = response_data.get("description", "Unknown error")
                self._logger.error("Telegram API error: %s", description)
                return False

            self._logger.info("Notification sent to Telegram successfully")
            return True

        except (ValueError, TypeError) as e:
            # Handle JSON parsing errors
            self._logger.error("Error parsing Telegram API response: %s", e)
            return False
