"""
Telegram notification provider implementation.

This module provides the implementation of the Telegram notification provider,
which sends notifications to Telegram using the Bot API.
"""

import logging
from typing import NotRequired, TypedDict, cast, override

import requests

from mover_status.notification.base import NotificationProvider
from mover_status.notification.formatter import RawValues
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


class TelegramProvider(NotificationProvider):
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

    def __init__(self, config: TelegramConfig) -> None:
        """
        Initialize the Telegram notification provider.

        Args:
            config: The provider configuration.
        """
        super().__init__("telegram")
        self.bot_token: str = config.get("bot_token", "")
        self.chat_id: str = config.get("chat_id", "")
        self.parse_mode: str = config.get("parse_mode", "HTML")
        self.disable_notification: bool = config.get("disable_notification", False)
        self.message_template: str = config.get("message_template", "")
        self.enabled: bool = config.get("enabled", False)

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
    def send_notification(self, message: str, **kwargs: object) -> bool:
        """
        Send a notification to Telegram.

        Args:
            message: The message to send.
            **kwargs: Additional arguments.
                raw_values: Optional raw values to format the message with.

        Returns:
            True if the notification was sent successfully, False otherwise.
        """
        if not self.enabled:
            logger.info("Telegram notifications are disabled")
            return False

        # Validate configuration
        errors = self.validate_config()
        if errors:
            logger.error("Invalid Telegram configuration: %s", ", ".join(errors))
            return False

        # Format the message if raw_values are provided
        raw_values: RawValues = {}

        if "raw_values" in kwargs and isinstance(kwargs["raw_values"], dict):
            # We need to handle the raw_values dictionary carefully since it comes from kwargs
            # and its exact structure is not known at compile time.

            # Get the raw values dictionary from kwargs and cast it to a known type
            # We know it's a dict from the isinstance check above
            raw_dict = cast(dict[str, object], kwargs["raw_values"])

            # Use a sentinel value to distinguish between missing keys and None values
            sentinel = object()

            try:
                # Extract and validate percent value
                percent_val = raw_dict.get("percent", sentinel)

                if percent_val is not sentinel:
                    # Runtime type checking for percent
                    if isinstance(percent_val, (int, float)):
                        # After runtime type checking, we know this is safe to assign
                        raw_values["percent"] = percent_val
            except (KeyError, TypeError, AttributeError):
                # Handle any unexpected errors when accessing the dictionary
                logger.debug("Error extracting percent value from raw_values")

            try:
                # Extract and validate remaining_bytes value
                bytes_val = raw_dict.get("remaining_bytes", sentinel)

                if bytes_val is not sentinel:
                    # Runtime type checking for remaining_bytes
                    if isinstance(bytes_val, int):
                        raw_values["remaining_bytes"] = bytes_val
            except (KeyError, TypeError, AttributeError):
                # Handle any unexpected errors when accessing the dictionary
                logger.debug("Error extracting remaining_bytes value from raw_values")

            try:
                # Extract and validate eta value
                eta_val = raw_dict.get("eta", sentinel)

                if eta_val is not sentinel:
                    # Runtime type checking for eta
                    if eta_val is None or isinstance(eta_val, float):
                        # After runtime type checking, we know this is safe to assign
                        raw_values["eta"] = eta_val
            except (KeyError, TypeError, AttributeError):
                # Handle any unexpected errors when accessing the dictionary
                logger.debug("Error extracting eta value from raw_values")

            # Use the message template if the message is empty
            template = message if message else self.message_template
            message = format_telegram_message(template, raw_values)

        # Prepare the API URL
        api_url = TELEGRAM_API_URL.format(token=self.bot_token)

        # Prepare the request payload
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": self.parse_mode,
            "disable_notification": self.disable_notification,
        }

        try:
            # Send the request to the Telegram API
            logger.debug("Sending notification to Telegram: %s", api_url)
            response = requests.post(api_url, json=payload, timeout=10)
            response.raise_for_status()

            # Check the response
            # The response.json() returns a dictionary for Telegram API responses,
            # but the type checker doesn't know the exact structure at compile time.
            # We need to handle this carefully with runtime type checking.
            try:
                # Parse the JSON response and cast it to a known type
                # This helps the type checker understand what we're working with
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
            except (ValueError, TypeError) as e:
                # Handle JSON parsing errors
                logger.error("Error parsing Telegram API response: %s", e)
                return False

            if not response_data["ok"]:
                description = response_data.get("description", "Unknown error")
                logger.error("Telegram API error: %s", description)
                return False

            logger.info("Notification sent to Telegram successfully")
            return True

        except requests.exceptions.RequestException as e:
            logger.error("Error sending notification to Telegram: %s", e)
            return False
