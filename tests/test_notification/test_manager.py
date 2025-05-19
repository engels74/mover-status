"""
Tests for the notification manager module.

This module contains tests for the notification manager, which is responsible
for managing notification providers and sending notifications to all registered providers.
"""

from typing import override
from unittest.mock import patch

from mover_status.notification.base import NotificationProvider
from mover_status.notification.formatter import RawValues
from mover_status.notification.manager import NotificationManager


class MockProvider(NotificationProvider):
    """Mock notification provider for testing."""

    def __init__(self, name: str, should_succeed: bool = True) -> None:
        """
        Initialize the mock provider.

        Args:
            name: The name of the provider.
            should_succeed: Whether the provider should succeed when sending notifications.
        """
        super().__init__(name)
        self.should_succeed: bool = should_succeed
        self.notifications_sent: int = 0
        self.last_message: str = ""
        self.last_kwargs: dict[str, object] = {}

    @override
    def send_notification(self, message: str, **kwargs: object) -> bool:
        """
        Send a notification with the given message.

        Args:
            message: The message to send.
            **kwargs: Additional provider-specific arguments.

        Returns:
            True if the notification was sent successfully, False otherwise.
        """
        self.notifications_sent += 1
        self.last_message = message
        self.last_kwargs = kwargs
        return self.should_succeed

    @override
    def validate_config(self) -> list[str]:
        """
        Validate the provider configuration.

        Returns:
            A list of error messages. An empty list indicates a valid configuration.
        """
        return []


class TestNotificationManager:
    """Tests for the NotificationManager class."""

    def test_init(self) -> None:
        """Test initialization of the NotificationManager class."""
        # Create a manager with no providers
        manager = NotificationManager()

        # Check that the manager was initialized correctly
        assert manager.providers == []

    def test_register_provider(self) -> None:
        """Test registering a provider with the manager."""
        # Create a manager
        manager = NotificationManager()

        # Create a provider
        provider = MockProvider("test_provider")

        # Register the provider
        manager.register_provider(provider)

        # Check that the provider was registered
        assert len(manager.providers) == 1
        assert manager.providers[0] == provider

    def test_register_multiple_providers(self) -> None:
        """Test registering multiple providers with the manager."""
        # Create a manager
        manager = NotificationManager()

        # Create providers
        provider1 = MockProvider("provider1")
        provider2 = MockProvider("provider2")
        provider3 = MockProvider("provider3")

        # Register the providers
        manager.register_provider(provider1)
        manager.register_provider(provider2)
        manager.register_provider(provider3)

        # Check that all providers were registered
        assert len(manager.providers) == 3
        assert manager.providers[0] == provider1
        assert manager.providers[1] == provider2
        assert manager.providers[2] == provider3

    def test_send_notification_to_all_providers(self) -> None:
        """Test sending a notification to all registered providers."""
        # Create a manager
        manager = NotificationManager()

        # Create providers
        provider1 = MockProvider("provider1")
        provider2 = MockProvider("provider2")

        # Register the providers
        manager.register_provider(provider1)
        manager.register_provider(provider2)

        # Send a notification
        message = "Test notification"
        result = manager.send_notification(message)

        # Check that the notification was sent to all providers
        assert result is True
        assert provider1.notifications_sent == 1
        assert provider1.last_message == message
        assert provider2.notifications_sent == 1
        assert provider2.last_message == message

    def test_send_notification_with_raw_values(self) -> None:
        """Test sending a notification with raw values to all registered providers."""
        # Create a manager
        manager = NotificationManager()

        # Create providers
        provider1 = MockProvider("provider1")
        provider2 = MockProvider("provider2")

        # Register the providers
        manager.register_provider(provider1)
        manager.register_provider(provider2)

        # Send a notification with raw values
        message = "Test notification"
        raw_values: RawValues = {
            "percent": 50,
            "remaining_bytes": 1073741824,  # 1 GB
            "eta": None,
        }
        result = manager.send_notification(message, raw_values=raw_values)

        # Check that the notification was sent to all providers with raw values
        assert result is True
        assert provider1.notifications_sent == 1
        assert provider1.last_message == message
        assert "raw_values" in provider1.last_kwargs
        assert provider1.last_kwargs["raw_values"] == raw_values
        assert provider2.notifications_sent == 1
        assert provider2.last_message == message
        assert "raw_values" in provider2.last_kwargs
        assert provider2.last_kwargs["raw_values"] == raw_values

    def test_handle_provider_errors(self) -> None:
        """Test handling errors from providers when sending notifications."""
        # Create a manager
        manager = NotificationManager()

        # Create providers (one that succeeds and one that fails)
        provider1 = MockProvider("provider1", should_succeed=True)
        provider2 = MockProvider("provider2", should_succeed=False)

        # Register the providers
        manager.register_provider(provider1)
        manager.register_provider(provider2)

        # Send a notification
        message = "Test notification"
        result = manager.send_notification(message)

        # Check that the notification was sent to all providers
        # and the result indicates partial failure
        assert result is False
        assert provider1.notifications_sent == 1
        assert provider1.last_message == message
        assert provider2.notifications_sent == 1
        assert provider2.last_message == message

    def test_no_providers_registered(self) -> None:
        """Test sending a notification when no providers are registered."""
        # Create a manager with no providers
        manager = NotificationManager()

        # Send a notification
        message = "Test notification"

        # Capture logs to verify warning
        with patch("logging.Logger.warning") as mock_warning:
            result = manager.send_notification(message)

        # Check that the result is True (no failures) but a warning was logged
        assert result is True
        mock_warning.assert_called_once()
        # Check that the warning message contains the expected text
        # We know the first argument to warning() is the message string
        mock_warning.assert_called_with("No notification providers registered")
