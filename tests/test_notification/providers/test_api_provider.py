"""
Tests for the API notification provider base class.

This module contains tests for the ApiProvider class, which provides common
functionality for API-based notification providers.
"""

import json
from typing import override
from unittest.mock import Mock, patch

import requests

# Import the modules to test
from mover_status.notification.formatter import RawValues
from mover_status.notification.providers.api_provider import ApiProvider


class TestApiProvider:
    """Tests for the ApiProvider class."""

    def test_api_provider_with_common_functionality(self) -> None:
        """Test that ApiProvider provides common functionality for API-based providers."""
        # Create a concrete implementation for testing
        class TestApiProvider(ApiProvider):
            @override
            def _get_api_url(self, **kwargs: object) -> str:
                return f"{self.base_url}/sendMessage"

            @override
            def _prepare_request_data(self, message: str, raw_values: RawValues, **kwargs: object) -> dict[str, object]:
                return {"text": message, "data": raw_values}

            @override
            def validate_config(self) -> list[str]:
                return self._validate_required_config(["base_url", "api_key"])

        # Test that ApiProvider can be instantiated with configuration
        config = {
            "enabled": True,
            "base_url": "https://api.example.com",
            "api_key": "test-api-key-123",
            "timeout": 30
        }
        provider = TestApiProvider("test-api", config)

        # Verify basic functionality
        assert provider.name == "test-api"
        assert provider.enabled is True
        assert provider.base_url == "https://api.example.com"
        assert provider.api_key == "test-api-key-123"
        assert provider.timeout == 30
        assert provider.is_initialized() is False

    def test_api_configuration_handling(self) -> None:
        """Test that ApiProvider handles API configuration properly."""
        # Create a concrete implementation for testing
        class TestApiProvider(ApiProvider):
            @override
            def _get_api_url(self, **kwargs: object) -> str:
                return f"{self.base_url}/api/v1/messages"

            @override
            def _prepare_request_data(self, message: str, raw_values: RawValues, **kwargs: object) -> dict[str, object]:
                return {"message": message}

            @override
            def validate_config(self) -> list[str]:
                return []

        # Test configuration with all API settings
        config = {
            "enabled": True,
            "base_url": "https://api.example.com",
            "api_key": "secret-key-456",
            "timeout": 15,
            "headers": {"User-Agent": "MoverStatus/1.0", "Accept": "application/json"},
            "verify_ssl": False,
            "http_method": "PUT"
        }
        provider = TestApiProvider("test-api", config)

        # Test configuration access
        assert provider.base_url == "https://api.example.com"
        assert provider.api_key == "secret-key-456"
        assert provider.timeout == 15
        assert provider.headers == {"User-Agent": "MoverStatus/1.0", "Accept": "application/json"}
        assert provider.verify_ssl is False
        assert provider.http_method == "PUT"

        # Test default values
        minimal_config = {"enabled": True, "base_url": "https://api.test.com", "api_key": "key123"}
        minimal_provider = TestApiProvider("minimal", minimal_config)

        assert minimal_provider.timeout == 10  # Default timeout
        assert minimal_provider.headers == {}  # Default headers
        assert minimal_provider.verify_ssl is True  # Default SSL verification
        assert minimal_provider.http_method == "POST"  # Default HTTP method

    def test_api_request_methods(self) -> None:
        """Test that ApiProvider implements API request methods correctly."""
        # Create a concrete implementation for testing
        class TestApiProvider(ApiProvider):
            @override
            def _get_api_url(self, **kwargs: object) -> str:
                endpoint = kwargs.get("endpoint", "messages")
                return f"{self.base_url}/api/{endpoint}"

            @override
            def _prepare_request_data(self, message: str, raw_values: RawValues, **kwargs: object) -> dict[str, object]:
                return {
                    "content": message,
                    "progress": raw_values.get("percent", 0),
                    "eta_seconds": raw_values.get("eta")
                }

            @override
            def validate_config(self) -> list[str]:
                return self._validate_required_config(["base_url", "api_key"])

        config = {
            "enabled": True,
            "base_url": "https://api.example.com",
            "api_key": "test-key",
            "http_method": "POST"
        }
        provider = TestApiProvider("test-api", config)

        # Test URL generation
        url = provider._get_api_url(endpoint="notifications")  # pyright: ignore[reportPrivateUsage]
        assert url == "https://api.example.com/api/notifications"

        # Test request data preparation
        raw_values: RawValues = {"percent": 75.5, "eta": 300.0}
        data = provider._prepare_request_data("Test message", raw_values)  # pyright: ignore[reportPrivateUsage]
        assert data["content"] == "Test message"
        assert data["progress"] == 75.5
        assert data["eta_seconds"] == 300.0

        # Test authentication header preparation
        auth_headers = provider._prepare_auth_headers()  # pyright: ignore[reportPrivateUsage]
        assert "Authorization" in auth_headers or "X-API-Key" in auth_headers

    @patch('requests.request')
    def test_api_sending_methods(self, mock_request: Mock) -> None:
        """Test that ApiProvider implements API sending methods correctly."""
        # Create a concrete implementation for testing
        class TestApiProvider(ApiProvider):
            @override
            def _get_api_url(self, **kwargs: object) -> str:
                return f"{self.base_url}/api/send"

            @override
            def _prepare_request_data(self, message: str, raw_values: RawValues, **kwargs: object) -> dict[str, object]:
                return {
                    "message": message,
                    "progress": raw_values.get("percent", 0),
                    "eta": raw_values.get("eta")
                }

            @override
            def validate_config(self) -> list[str]:
                return self._validate_required_config(["base_url", "api_key"])

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None  # pyright: ignore[reportAny]
        mock_response.json.return_value = {"success": True, "id": "msg123"}  # pyright: ignore[reportAny]
        mock_request.return_value = mock_response

        # Test sending notification
        config = {
            "enabled": True,
            "base_url": "https://api.example.com",
            "api_key": "test-key-789",
            "timeout": 10,
            "headers": {"User-Agent": "TestBot/1.0"},
            "http_method": "POST"
        }
        provider = TestApiProvider("test-api", config)

        # Test successful sending
        raw_values = {"percent": 85.2, "eta": 120.5}
        result = provider.send_notification("API test message", raw_values=raw_values)

        assert result is True

        # Verify the request was made correctly
        mock_request.assert_called_once()
        call_args = mock_request.call_args

        # Check keyword arguments
        assert call_args.kwargs["method"] == "POST"  # HTTP method
        assert call_args.kwargs["url"] == "https://api.example.com/api/send"  # URL
        assert call_args.kwargs["timeout"] == 10
        assert call_args.kwargs["verify"] is True

        # Verify headers include authentication
        headers: dict[str, str] = call_args.kwargs["headers"]  # pyright: ignore[reportAny]
        assert "User-Agent" in headers
        assert "Authorization" in headers

        # Verify payload
        if "json" in call_args.kwargs:
            payload: dict[str, object] = call_args.kwargs["json"]  # pyright: ignore[reportAny]
        else:
            payload = json.loads(call_args.kwargs["data"])  # pyright: ignore[reportAny]

        assert payload["message"] == "API test message"
        assert payload["progress"] == 85.2
        assert payload["eta"] == 120.5

    @patch('requests.request')
    def test_api_error_handling(self, mock_request: Mock) -> None:
        """Test that ApiProvider handles API errors properly."""
        # Create a concrete implementation for testing
        class TestApiProvider(ApiProvider):
            @override
            def _get_api_url(self, **kwargs: object) -> str:
                return f"{self.base_url}/api/send"

            @override
            def _prepare_request_data(self, message: str, raw_values: RawValues, **kwargs: object) -> dict[str, object]:
                return {"message": message}

            @override
            def validate_config(self) -> list[str]:
                return []

        config = {
            "enabled": True,
            "base_url": "https://api.example.com",
            "api_key": "test-key"
        }
        provider = TestApiProvider("test-api", config)

        # Test HTTP error
        mock_request.side_effect = requests.exceptions.HTTPError("401 Unauthorized")
        result = provider.send_notification("Test message")
        assert result is False

        # Test connection error
        mock_request.side_effect = requests.exceptions.ConnectionError("Connection failed")
        result = provider.send_notification("Test message")
        assert result is False

        # Test timeout error
        mock_request.side_effect = requests.exceptions.Timeout("Request timed out")
        result = provider.send_notification("Test message")
        assert result is False

    def test_api_provider_inheritance(self) -> None:
        """Test that ApiProvider properly inherits from BaseProvider."""
        from mover_status.notification.providers.base_provider import BaseProvider

        # Create a concrete implementation for testing
        class TestApiProvider(ApiProvider):
            @override
            def _get_api_url(self, **kwargs: object) -> str:
                return f"{self.base_url}/test"

            @override
            def _prepare_request_data(self, message: str, raw_values: RawValues, **kwargs: object) -> dict[str, object]:
                return {"message": message}

            @override
            def validate_config(self) -> list[str]:
                return []

        config = {"enabled": True, "base_url": "https://api.test.com", "api_key": "key"}
        provider = TestApiProvider("test", config)

        # Verify inheritance
        assert isinstance(provider, BaseProvider)
        assert isinstance(provider, ApiProvider)

        # Verify interface compliance
        assert hasattr(provider, "send_notification")
        assert hasattr(provider, "validate_config")
        assert hasattr(provider, "_get_api_url")
        assert hasattr(provider, "_prepare_request_data")
        assert hasattr(provider, "_send_api_request")


class TestApiProviderIntegration:
    """Integration tests for ApiProvider with other components."""

    def test_integration_with_base_provider_functionality(self) -> None:
        """Test that ApiProvider integrates properly with BaseProvider functionality."""
        # Create a concrete implementation for testing
        class TestApiProvider(ApiProvider):
            @override
            def _get_api_url(self, **kwargs: object) -> str:
                return f"{self.base_url}/api/messages"

            @override
            def _prepare_request_data(self, message: str, raw_values: RawValues, **kwargs: object) -> dict[str, object]:
                return {"text": message, "data": raw_values}

            @override
            def validate_config(self) -> list[str]:
                return self._validate_required_config(["base_url", "api_key"])

        # Test that BaseProvider functionality works
        config = {
            "enabled": True,
            "base_url": "https://api.example.com",
            "api_key": "test-key-integration"
        }
        provider = TestApiProvider("test", config)

        # Test configuration validation from BaseProvider
        assert provider.enabled is True
        assert provider.name == "test"

        # Test lifecycle methods from BaseProvider
        assert provider.is_initialized() is False
        assert provider.initialize() is True
        assert provider.is_initialized() is True
        assert provider.health_check() is True

    @patch('requests.request')
    def test_api_with_raw_values_processing(self, mock_request: Mock) -> None:
        """Test that ApiProvider properly processes raw values from BaseProvider."""
        # Create a concrete implementation for testing
        class TestApiProvider(ApiProvider):
            @override
            def _get_api_url(self, **kwargs: object) -> str:
                return f"{self.base_url}/api/notifications"

            @override
            def _prepare_request_data(self, message: str, raw_values: RawValues, **kwargs: object) -> dict[str, object]:
                return {
                    "content": message,
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
        mock_response.json.return_value = {"status": "sent", "message_id": "abc123"}  # pyright: ignore[reportAny]
        mock_request.return_value = mock_response

        config = {
            "enabled": True,
            "base_url": "https://api.example.com",
            "api_key": "integration-test-key"
        }
        provider = TestApiProvider("test", config)

        # Test with raw values
        raw_values = {
            "percent": 92.7,
            "eta": 45.3,
            "remaining_bytes": 1024
        }

        result = provider.send_notification("Integration test", raw_values=raw_values)
        assert result is True

        # Verify the payload was prepared correctly with raw values
        call_args = mock_request.call_args

        # Check if data was sent as JSON or form data
        if "json" in call_args.kwargs:
            payload: dict[str, object] = call_args.kwargs["json"]  # pyright: ignore[reportAny]
        else:
            payload = json.loads(call_args.kwargs["data"])  # pyright: ignore[reportAny]

        assert payload["content"] == "Integration test"
        assert payload["progress_percent"] == 92.7
        assert payload["estimated_time"] == 45.3
        assert payload["remaining_bytes"] == 1024
