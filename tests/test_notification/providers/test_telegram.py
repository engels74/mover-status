"""
Tests for the Telegram notification provider.

This module contains tests for the Telegram notification provider, including
the formatter module and the provider implementation.
"""

import time
from datetime import datetime
from typing import TypedDict, NotRequired
from unittest.mock import patch, MagicMock

import requests

from mover_status.notification.formatter import RawValues
from mover_status.notification.providers.telegram.formatter import (
    format_telegram_message,
    format_telegram_eta,
    format_html_text,
    format_timestamp_for_telegram,
)
from mover_status.notification.providers.telegram.provider import TelegramProvider, TelegramConfig
from mover_status.notification.registry import ProviderRegistry


class TestTelegramFormatter:
    """Test cases for the Telegram formatter module."""

    def test_format_html_text(self) -> None:
        """Test formatting text with HTML tags for Telegram."""
        # Test basic text formatting
        assert format_html_text("Test") == "Test"

        # Test bold formatting
        assert format_html_text("Test", bold=True) == "<b>Test</b>"

        # Test italic formatting
        assert format_html_text("Test", italic=True) == "<i>Test</i>"

        # Test combined formatting
        assert format_html_text("Test", bold=True, italic=True) == "<b><i>Test</i></b>"

    def test_format_telegram_eta(self) -> None:
        """Test formatting ETA for Telegram."""
        # Test None ETA (still calculating)
        assert format_telegram_eta(None) == "Calculating..."

        # Test with a specific timestamp
        # Create a timestamp for testing (e.g., 1 hour from now)
        current_time = time.time()
        future_time = current_time + 3600  # 1 hour in the future

        # Format the expected result manually for comparison
        expected_format = datetime.fromtimestamp(future_time).strftime("%H:%M on %b %d (%Z)")

        # Test the formatter
        assert format_telegram_eta(future_time) == expected_format

    def test_format_telegram_message_with_raw_values(self) -> None:
        """Test formatting a message with raw values for Telegram."""
        # Define a template with HTML formatting
        template = (
            "Moving data from SSD Cache to HDD Array. &#10;"
            "Progress: <b>{percent}</b> complete. &#10;"
            "Remaining data: {remaining_data}.&#10;"
            "Estimated completion time: {etc}.&#10;&#10;"
            "Note: Services like Plex may run slow or be unavailable during the move."
        )

        # Define raw values
        raw_values: RawValues = {
            "percent": 50,
            "remaining_bytes": 1073741824,  # 1 GB
            "eta": None,
        }

        # Format the message
        formatted_message = format_telegram_message(template, raw_values)

        # Check that the message contains expected formatted values
        assert "<b>50%</b>" in formatted_message
        assert "1.0 GB" in formatted_message
        assert "Calculating..." in formatted_message
        assert "&#10;" in formatted_message  # HTML newline entity

    def test_format_timestamp_for_telegram(self) -> None:
        """Test formatting a timestamp for Telegram."""
        # Create a specific timestamp for testing
        test_timestamp = 1609459200  # 2021-01-01 00:00:00 UTC

        # Format the timestamp
        formatted_timestamp = format_timestamp_for_telegram(test_timestamp)

        # Expected format: "%H:%M on %b %d (%Z)"
        # The exact output will depend on the local timezone, so we'll check the format
        assert ":" in formatted_timestamp  # Contains time with colon
        assert " on " in formatted_timestamp  # Contains " on " separator
        assert "(" in formatted_timestamp and ")" in formatted_timestamp  # Contains timezone in parentheses


class TelegramMessageResult(TypedDict):
    """Type definition for Telegram message result data."""
    message_id: int


class TelegramResponseDict(TypedDict):
    """Type definition for Telegram API response."""
    ok: bool
    result: NotRequired[TelegramMessageResult]
    description: NotRequired[str]


class TelegramRequestJSON(TypedDict):
    """Type definition for Telegram request JSON data."""
    chat_id: str
    text: str
    parse_mode: str
    disable_notification: bool


class TestTelegramProvider:
    """Test cases for the Telegram provider implementation."""

    def test_init(self) -> None:
        """Test initialization of the TelegramProvider class."""
        # Create a provider with valid config
        config: TelegramConfig = {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_id": "12345678",
            "parse_mode": "HTML",
            "disable_notification": False,
            "message_template": "Test message",
            "enabled": True
        }
        provider = TelegramProvider("telegram", config)

        # Check that the provider was initialized correctly
        assert provider.name == "telegram"
        assert provider.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        assert provider.chat_id == "12345678"
        assert provider.parse_mode == "HTML"
        assert provider.disable_notification is False
        assert provider.message_template == "Test message"
        assert provider.enabled is True

    def test_validate_config_valid(self) -> None:
        """Test validation of a valid configuration."""
        # Create a provider with valid config
        config: TelegramConfig = {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_id": "12345678",
            "parse_mode": "HTML",
            "disable_notification": False,
            "message_template": "Test message",
            "enabled": True
        }
        provider = TelegramProvider("telegram", config)

        # Validate the config
        errors = provider.validate_config()

        # Check that there are no errors
        assert len(errors) == 0

    def test_validate_config_missing_bot_token(self) -> None:
        """Test validation of a configuration with a missing bot token."""
        # Create a provider with missing bot token
        config: TelegramConfig = {
            "chat_id": "12345678",
            "parse_mode": "HTML",
            "disable_notification": False,
            "message_template": "Test message",
            "enabled": True
        }
        provider = TelegramProvider("telegram", config)

        # Validate the config
        errors = provider.validate_config()

        # Check that there is an error for the missing bot token
        assert len(errors) == 1
        assert "bot_token" in errors[0].lower()

    def test_validate_config_missing_chat_id(self) -> None:
        """Test validation of a configuration with a missing chat ID."""
        # Create a provider with missing chat ID
        config: TelegramConfig = {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "parse_mode": "HTML",
            "disable_notification": False,
            "message_template": "Test message",
            "enabled": True
        }
        provider = TelegramProvider("telegram", config)

        # Validate the config
        errors = provider.validate_config()

        # Check that there is an error for the missing chat ID
        assert len(errors) == 1
        assert "chat_id" in errors[0].lower()

    def test_validate_config_invalid_parse_mode(self) -> None:
        """Test validation of a configuration with an invalid parse mode."""
        # Create a provider with invalid parse mode
        config: TelegramConfig = {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_id": "12345678",
            "parse_mode": "INVALID",
            "disable_notification": False,
            "message_template": "Test message",
            "enabled": True
        }
        provider = TelegramProvider("telegram", config)

        # Validate the config
        errors = provider.validate_config()

        # Check that there is an error for the invalid parse mode
        assert len(errors) == 1
        assert "parse_mode" in errors[0].lower()

    def test_send_notification_success(self) -> None:
        """Test sending a notification successfully."""
        # Create a provider with valid config
        config: TelegramConfig = {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_id": "12345678",
            "parse_mode": "HTML",
            "disable_notification": False,
            "message_template": "Test message",
            "enabled": True
        }
        provider = TelegramProvider("telegram", config)

        # Create expected request JSON for type checking
        expected_request_json: TelegramRequestJSON = {
            "chat_id": "12345678",
            "text": "Test message",
            "parse_mode": "HTML",
            "disable_notification": False
        }

        # Mock the requests.post method to return a successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = TelegramResponseDict(  # pyright: ignore[reportAny]
            ok=True,
            result=TelegramMessageResult(message_id=123)
        )

        with patch("requests.request", return_value=mock_response) as mock_request:
            # Send a notification
            result = provider.send_notification("Test message")

            # Check that the notification was sent successfully
            assert result is True

            # Check that requests.request was called with the correct arguments
            mock_request.assert_called_once()

            # Extract the URL from the mock call
            api_url = f"https://api.telegram.org/bot{config['bot_token']}/sendMessage"
            call_args = mock_request.call_args
            assert call_args.kwargs["method"] == "POST"
            assert call_args.kwargs["url"] == api_url
            assert call_args.kwargs["json"] == expected_request_json
            assert call_args.kwargs["timeout"] == 10

    def test_send_notification_http_error(self) -> None:
        """Test handling HTTP errors when sending a notification."""
        # Create a provider with valid config
        config: TelegramConfig = {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_id": "12345678",
            "parse_mode": "HTML",
            "disable_notification": False,
            "message_template": "Test message",
            "enabled": True
        }
        provider = TelegramProvider("telegram", config)

        # Mock the requests.request method to raise an HTTPError
        with patch("requests.request", side_effect=requests.exceptions.HTTPError("404 Client Error")):
            # Send a notification
            result = provider.send_notification("Test message")

            # Check that the notification failed
            assert result is False

    def test_send_notification_connection_error(self) -> None:
        """Test handling connection errors when sending a notification."""
        # Create a provider with valid config
        config: TelegramConfig = {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_id": "12345678",
            "parse_mode": "HTML",
            "disable_notification": False,
            "message_template": "Test message",
            "enabled": True
        }
        provider = TelegramProvider("telegram", config)

        # Mock the requests.request method to raise a ConnectionError
        with patch("requests.request", side_effect=requests.exceptions.ConnectionError("Connection refused")):
            # Send a notification
            result = provider.send_notification("Test message")

            # Check that the notification failed
            assert result is False

    def test_send_notification_api_error(self) -> None:
        """Test handling API errors when sending a notification."""
        # Create a provider with valid config
        config: TelegramConfig = {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_id": "12345678",
            "parse_mode": "HTML",
            "disable_notification": False,
            "message_template": "Test message",
            "enabled": True
        }
        provider = TelegramProvider("telegram", config)

        # Mock the requests.post method to return an error response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = TelegramResponseDict(  # pyright: ignore[reportAny]
            ok=False,
            description="Bad Request: chat not found"
        )

        with patch("requests.request", return_value=mock_response):
            # Send a notification
            result = provider.send_notification("Test message")

            # Check that the notification failed
            assert result is False

    def test_send_notification_with_raw_values(self) -> None:
        """Test sending a notification with raw values."""
        # Create a provider with valid config
        config: TelegramConfig = {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_id": "12345678",
            "parse_mode": "HTML",
            "disable_notification": False,
            "message_template": "Progress: <b>{percent}</b> complete",
            "enabled": True
        }
        provider = TelegramProvider("telegram", config)

        # Create expected request JSON for type checking
        expected_request_json: TelegramRequestJSON = {
            "chat_id": "12345678",
            "text": "Progress: <b>50%</b> complete",
            "parse_mode": "HTML",
            "disable_notification": False
        }

        # Mock the requests.post method to return a successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = TelegramResponseDict(  # pyright: ignore[reportAny]
            ok=True,
            result=TelegramMessageResult(message_id=123)
        )

        with patch("requests.request", return_value=mock_response) as mock_request:
            # Send a notification with raw values
            raw_values: RawValues = {"percent": 50}
            result = provider.send_notification("", raw_values=raw_values)

            # Check that the notification was sent successfully
            assert result is True

            # Check that requests.request was called with the correct arguments
            mock_request.assert_called_once()

            # Extract the URL from the mock call
            api_url = f"https://api.telegram.org/bot{config['bot_token']}/sendMessage"
            call_args = mock_request.call_args
            assert call_args.kwargs["method"] == "POST"
            assert call_args.kwargs["url"] == api_url
            assert call_args.kwargs["json"] == expected_request_json
            assert call_args.kwargs["timeout"] == 10


class TestTelegramProviderRefactored:
    """Test cases for the refactored Telegram provider using new base classes."""

    def test_telegram_provider_using_new_base_classes(self) -> None:
        """Test that Telegram provider uses new base classes correctly."""
        from mover_status.notification.providers.api_provider import ApiProvider

        # Create a provider with valid config
        config = {
            "enabled": True,
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_id": "12345678",
            "parse_mode": "HTML",
            "disable_notification": False,
            "message_template": "Test message"
        }
        provider = TelegramProvider("telegram", config)

        # Verify that the provider inherits from ApiProvider
        assert isinstance(provider, ApiProvider)

        # Verify that the provider has the expected name
        assert provider.name == "telegram"

        # Verify that the provider is enabled
        assert provider.enabled is True

        # Verify that the provider can be initialized
        assert provider.initialize() is True

    def test_self_registration_with_provider_registry(self) -> None:
        """Test that Telegram provider can self-register with provider registry."""
        # Create a provider registry
        registry = ProviderRegistry()

        # Create a provider with valid config
        config = {
            "enabled": True,
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_id": "12345678",
            "parse_mode": "HTML",
            "disable_notification": False,
            "message_template": "Test message"
        }

        # Create provider with metadata for registration
        metadata = {
            "version": "1.0.0",
            "description": "Telegram notification provider",
            "author": "MoverStatus Team"
        }
        provider = TelegramProvider("telegram", config, metadata)

        # Register the provider
        registry.register_provider("telegram", provider)

        # Verify that the provider is registered
        registered_providers = registry.get_registered_providers()
        assert "telegram" in registered_providers
        assert registered_providers["telegram"] == provider

    def test_configuration_schema_validation(self) -> None:
        """Test that Telegram provider configuration schema validation works."""
        from mover_status.notification.providers.telegram.config import validate_telegram_config

        # Test valid configuration
        valid_config: dict[str, object] = {
            "enabled": True,
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_id": "12345678",
            "parse_mode": "HTML",
            "disable_notification": False,
            "message_template": "Test message"
        }

        # Validate the configuration - should not raise an exception
        validated_config = validate_telegram_config(valid_config)
        assert validated_config["enabled"] is True
        assert validated_config["bot_token"] == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        assert validated_config["chat_id"] == "12345678"

        # Test configuration with missing required fields
        invalid_config: dict[str, object] = {
            "enabled": True,
            "parse_mode": "HTML"
            # Missing bot_token and chat_id
        }

        # Validate the configuration - should raise an exception
        try:
            _ = validate_telegram_config(invalid_config)
            assert False, "Expected SchemaValidationError to be raised"
        except Exception as e:
            # Should raise a validation error
            assert "bot_token" in str(e) or "chat_id" in str(e)