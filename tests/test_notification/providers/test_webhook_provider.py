"""
Tests for the webhook notification provider base class.

This module contains tests for the WebhookProvider class, which provides common
functionality for webhook-based notification providers.
"""

import json
from typing import override
from unittest.mock import Mock, patch

import requests

# Import the modules to test
from mover_status.notification.formatter import RawValues
from mover_status.notification.providers.webhook_provider import WebhookProvider


class TestWebhookProvider:
    """Tests for the WebhookProvider class."""

    def test_webhook_provider_with_common_functionality(self) -> None:
        """Test that WebhookProvider provides common functionality for webhook-based providers."""
        # Create a concrete implementation for testing
        class TestWebhookProvider(WebhookProvider):
            @override
            def _prepare_payload(self, message: str, raw_values: RawValues, **kwargs: object) -> dict[str, object]:
                return {"text": message, "data": raw_values}

            @override
            def validate_config(self) -> list[str]:
                return self._validate_required_config(["webhook_url"])

        # Test that WebhookProvider can be instantiated with configuration
        config = {
            "enabled": True,
            "webhook_url": "https://hooks.example.com/webhook/123",
            "timeout": 30
        }
        provider = TestWebhookProvider("test-webhook", config)

        # Verify basic functionality
        assert provider.name == "test-webhook"
        assert provider.enabled is True
        assert provider.webhook_url == "https://hooks.example.com/webhook/123"
        assert provider.timeout == 30
        assert provider.is_initialized() is False

    def test_webhook_configuration_handling(self) -> None:
        """Test that WebhookProvider handles webhook configuration properly."""
        # Create a concrete implementation for testing
        class TestWebhookProvider(WebhookProvider):
            @override
            def _prepare_payload(self, message: str, raw_values: RawValues, **kwargs: object) -> dict[str, object]:
                return {"text": message}

            @override
            def validate_config(self) -> list[str]:
                return []

        # Test configuration with all webhook settings
        config = {
            "enabled": True,
            "webhook_url": "https://hooks.example.com/webhook/123",
            "timeout": 15,
            "headers": {"Authorization": "Bearer token123", "Content-Type": "application/json"},
            "verify_ssl": False
        }
        provider = TestWebhookProvider("test-webhook", config)

        # Test configuration access
        assert provider.webhook_url == "https://hooks.example.com/webhook/123"
        assert provider.timeout == 15
        assert provider.headers == {"Authorization": "Bearer token123", "Content-Type": "application/json"}
        assert provider.verify_ssl is False

        # Test default values
        minimal_config = {"enabled": True, "webhook_url": "https://example.com/hook"}
        minimal_provider = TestWebhookProvider("minimal", minimal_config)

        assert minimal_provider.timeout == 10  # Default timeout
        assert minimal_provider.headers == {}  # Default headers
        assert minimal_provider.verify_ssl is True  # Default SSL verification

    def test_webhook_url_validation(self) -> None:
        """Test that WebhookProvider validates webhook URLs properly."""
        # Create a concrete implementation for testing
        class TestWebhookProvider(WebhookProvider):
            @override
            def _prepare_payload(self, message: str, raw_values: RawValues, **kwargs: object) -> dict[str, object]:
                return {"text": message}

            @override
            def validate_config(self) -> list[str]:
                errors = self._validate_required_config(["webhook_url"])
                errors.extend(self._validate_webhook_url())
                return errors

        # Test valid URLs
        valid_urls = [
            "https://hooks.example.com/webhook/123",
            "http://localhost:8080/webhook",
            "https://discord.com/api/webhooks/123/abc",
            "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
        ]

        for url in valid_urls:
            config = {"enabled": True, "webhook_url": url}
            provider = TestWebhookProvider("test", config)
            errors = provider.validate_config()
            assert len(errors) == 0, f"Valid URL {url} should not produce errors"

        # Test invalid URLs
        invalid_configs = [
            {"enabled": True},  # Missing webhook_url
            {"enabled": True, "webhook_url": ""},  # Empty webhook_url
            {"enabled": True, "webhook_url": "not-a-url"},  # Invalid format
            {"enabled": True, "webhook_url": "ftp://example.com/hook"},  # Wrong protocol
        ]

        for config in invalid_configs:
            provider = TestWebhookProvider("test", config)
            errors = provider.validate_config()
            assert len(errors) > 0, f"Invalid config {config} should produce errors"

    @patch('requests.post')
    def test_webhook_sending_methods(self, mock_post: Mock) -> None:
        """Test that WebhookProvider implements webhook sending methods correctly."""
        # Create a concrete implementation for testing
        class TestWebhookProvider(WebhookProvider):
            @override
            def _prepare_payload(self, message: str, raw_values: RawValues, **kwargs: object) -> dict[str, object]:
                return {
                    "text": message,
                    "progress": raw_values.get("percent", 0),
                    "eta": raw_values.get("eta")
                }

            @override
            def validate_config(self) -> list[str]:
                return self._validate_required_config(["webhook_url"])

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None  # pyright: ignore[reportAny]
        mock_post.return_value = mock_response

        # Test sending notification
        config = {
            "enabled": True,
            "webhook_url": "https://hooks.example.com/webhook/123",
            "timeout": 10,
            "headers": {"Authorization": "Bearer token"}
        }
        provider = TestWebhookProvider("test-webhook", config)

        # Test successful sending
        raw_values = {"percent": 75.5, "eta": 300.0}
        result = provider.send_notification("Test message", raw_values=raw_values)

        assert result is True

        # Verify the request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        assert call_args[1]["url"] == "https://hooks.example.com/webhook/123"
        assert call_args[1]["timeout"] == 10
        assert call_args[1]["headers"]["Authorization"] == "Bearer token"
        assert call_args[1]["verify"] is True

        # Verify payload
        payload = json.loads(call_args[1]["data"])  # pyright: ignore[reportAny]
        assert payload["text"] == "Test message"
        assert payload["progress"] == 75.5
        assert payload["eta"] == 300.0

    @patch('requests.post')
    def test_webhook_error_handling(self, mock_post: Mock) -> None:
        """Test that WebhookProvider handles HTTP errors properly."""
        # Create a concrete implementation for testing
        class TestWebhookProvider(WebhookProvider):
            @override
            def _prepare_payload(self, message: str, raw_values: RawValues, **kwargs: object) -> dict[str, object]:
                return {"text": message}

            @override
            def validate_config(self) -> list[str]:
                return []

        config = {
            "enabled": True,
            "webhook_url": "https://hooks.example.com/webhook/123"
        }
        provider = TestWebhookProvider("test-webhook", config)

        # Test HTTP error
        mock_post.side_effect = requests.exceptions.HTTPError("404 Not Found")
        result = provider.send_notification("Test message")
        assert result is False

        # Test connection error
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")
        result = provider.send_notification("Test message")
        assert result is False

        # Test timeout error
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")
        result = provider.send_notification("Test message")
        assert result is False

    def test_webhook_provider_inheritance(self) -> None:
        """Test that WebhookProvider properly inherits from BaseProvider."""
        from mover_status.notification.providers.base_provider import BaseProvider

        # Create a concrete implementation for testing
        class TestWebhookProvider(WebhookProvider):
            @override
            def _prepare_payload(self, message: str, raw_values: RawValues, **kwargs: object) -> dict[str, object]:
                return {"text": message}

            @override
            def validate_config(self) -> list[str]:
                return []

        config = {"enabled": True, "webhook_url": "https://example.com/hook"}
        provider = TestWebhookProvider("test", config)

        # Verify inheritance
        assert isinstance(provider, BaseProvider)
        assert isinstance(provider, WebhookProvider)

        # Verify interface compliance
        assert hasattr(provider, "send_notification")
        assert hasattr(provider, "validate_config")
        assert hasattr(provider, "_prepare_payload")
        assert hasattr(provider, "_send_webhook_request")


class TestWebhookProviderIntegration:
    """Integration tests for WebhookProvider with other components."""

    def test_integration_with_base_provider_functionality(self) -> None:
        """Test that WebhookProvider integrates properly with BaseProvider functionality."""
        # Create a concrete implementation for testing
        class TestWebhookProvider(WebhookProvider):
            @override
            def _prepare_payload(self, message: str, raw_values: RawValues, **kwargs: object) -> dict[str, object]:
                return {"text": message, "data": raw_values}

            @override
            def validate_config(self) -> list[str]:
                return self._validate_required_config(["webhook_url"])

        # Test that BaseProvider functionality works
        config = {
            "enabled": True,
            "webhook_url": "https://hooks.example.com/webhook/123"
        }
        provider = TestWebhookProvider("test", config)

        # Test configuration validation from BaseProvider
        assert provider.enabled is True
        assert provider.name == "test"

        # Test lifecycle methods from BaseProvider
        assert provider.is_initialized() is False
        assert provider.initialize() is True
        assert provider.is_initialized() is True
        assert provider.health_check() is True

    @patch('requests.post')
    def test_webhook_with_raw_values_processing(self, mock_post: Mock) -> None:
        """Test that WebhookProvider properly processes raw values from BaseProvider."""
        # Create a concrete implementation for testing
        class TestWebhookProvider(WebhookProvider):
            @override
            def _prepare_payload(self, message: str, raw_values: RawValues, **kwargs: object) -> dict[str, object]:
                return {
                    "message": message,
                    "progress_percent": raw_values.get("percent"),
                    "estimated_time": raw_values.get("eta"),
                    "remaining_bytes": raw_values.get("remaining_bytes")
                }

            @override
            def validate_config(self) -> list[str]:
                return []

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None  # pyright: ignore[reportAny]
        mock_post.return_value = mock_response

        config = {
            "enabled": True,
            "webhook_url": "https://hooks.example.com/webhook/123"
        }
        provider = TestWebhookProvider("test", config)

        # Test with raw values
        raw_values = {
            "percent": 85.2,
            "eta": 120.5,
            "remaining_bytes": 2048
        }

        result = provider.send_notification("Progress update", raw_values=raw_values)
        assert result is True

        # Verify the payload was prepared correctly with raw values
        call_args = mock_post.call_args
        payload = json.loads(call_args[1]["data"])  # pyright: ignore[reportAny]

        assert payload["message"] == "Progress update"
        assert payload["progress_percent"] == 85.2
        assert payload["estimated_time"] == 120.5
        assert payload["remaining_bytes"] == 2048
