"""
Tests for the dry run simulation module.

This module contains tests for the dry run functionality, which simulates
a monitoring session without actually monitoring the mover process.

Note: This file contains intentional type warnings related to MagicMock objects,
which are expected and can be safely ignored in test files.
"""

from unittest.mock import MagicMock, patch
from typing import override

from mover_status.notification.manager import NotificationManager
from mover_status.notification.base import NotificationProvider


class TestDryRunSimulation:
    """Tests for the dry run simulation functionality."""

    def test_simulate_monitoring_session(self) -> None:
        """Test simulating a monitoring session."""
        from mover_status.core.dry_run import simulate_monitoring_session

        # Create a mock notification manager
        notification_manager = MagicMock(spec=NotificationManager)

        # Run the simulation
        result = simulate_monitoring_session(notification_manager)

        # Verify the simulation ran successfully
        assert result is True

        # Verify that notifications were sent
        assert notification_manager.send_notification.call_count > 0

    def test_generate_test_notification(self) -> None:
        """Test generating a test notification."""
        from mover_status.core.dry_run import generate_test_notification

        # Create a mock notification manager
        notification_manager = MagicMock(spec=NotificationManager)

        # Generate a test notification
        result = generate_test_notification(notification_manager)

        # Verify the notification was sent
        assert result is True
        notification_manager.send_notification.assert_called_once()

        # Verify the raw values in the notification
        args, kwargs = notification_manager.send_notification.call_args
        assert "raw_values" in kwargs
        raw_values = kwargs["raw_values"]
        assert "progress" in raw_values
        assert "remaining_size" in raw_values
        assert "initial_size" in raw_values
        assert "eta" in raw_values
        assert "total_moved" in raw_values

    def test_dry_run_doesnt_monitor_real_processes(self) -> None:
        """Test that dry run doesn't actually monitor real processes."""
        from mover_status.core.dry_run import simulate_monitoring_session

        # Create a mock notification manager
        notification_manager = MagicMock(spec=NotificationManager)

        # Mock the process monitoring functions to ensure they're not called
        with patch("mover_status.utils.process.is_mover_running") as mock_is_running:
            # Run the simulation
            _ = simulate_monitoring_session(notification_manager)

            # Verify that the process monitoring function was not called
            mock_is_running.assert_not_called()

    def test_dry_run_with_custom_progress_values(self) -> None:
        """Test dry run with custom progress values."""
        from mover_status.core.dry_run import generate_test_notification

        # Create a mock notification manager
        notification_manager = MagicMock(spec=NotificationManager)

        # Generate a test notification with custom progress
        result = generate_test_notification(
            notification_manager,
            progress=75,
            remaining_size=250 * 1024 * 1024,  # 250 MB
            initial_size=1024 * 1024 * 1024,  # 1 GB
        )

        # Verify the notification was sent with the custom values
        assert result is True
        notification_manager.send_notification.assert_called_once()

        # Verify the raw values in the notification
        args, kwargs = notification_manager.send_notification.call_args
        raw_values = kwargs["raw_values"]
        assert raw_values["progress"] == 75
        assert raw_values["remaining_size"] == 250 * 1024 * 1024
        assert raw_values["initial_size"] == 1024 * 1024 * 1024
        assert "eta" in raw_values
        assert raw_values["total_moved"] == 1024 * 1024 * 1024 - 250 * 1024 * 1024

    def test_simulate_monitoring_session_with_custom_parameters(self) -> None:
        """Test simulating a monitoring session with custom parameters."""
        from mover_status.core.dry_run import simulate_monitoring_session

        # Create a mock notification manager
        notification_manager = MagicMock(spec=NotificationManager)

        # Run the simulation with custom parameters
        result = simulate_monitoring_session(
            notification_manager,
            initial_size=2 * 1024 * 1024 * 1024,  # 2 GB
            notification_count=3,
            completion_delay=0.1,
        )

        # Verify the simulation ran successfully
        assert result is True

        # Verify that the expected number of notifications were sent
        # Initial notification + progress notifications + completion notification
        assert notification_manager.send_notification.call_count == 3 + 1 + 1


class MockProvider(NotificationProvider):
    """Mock notification provider for testing."""

    def __init__(self, name: str) -> None:
        """Initialize the mock provider."""
        super().__init__(name)
        self.notifications_sent: int = 0
        self.last_message: str = ""
        self.last_kwargs: dict[str, object] = {}

    @override
    def send_notification(self, message: str, **kwargs: object) -> bool:
        """Send a notification with the given message."""
        self.notifications_sent += 1
        self.last_message = message
        self.last_kwargs = kwargs
        return True

    @override
    def validate_config(self) -> list[str]:
        """Validate the provider configuration."""
        return []


class TestDryRunIntegration:
    """Tests for the integration of dry run with notification providers."""

    def test_dry_run_with_real_notification_manager(self) -> None:
        """Test dry run with a real notification manager and mock providers."""
        from mover_status.core.dry_run import generate_test_notification

        # Create a real notification manager
        manager = NotificationManager()

        # Create and register mock providers
        provider1 = MockProvider("test_provider_1")
        provider2 = MockProvider("test_provider_2")
        manager.register_provider(provider1)
        manager.register_provider(provider2)

        # Generate a test notification
        result = generate_test_notification(manager)

        # Verify the notification was sent to all providers
        assert result is True
        assert provider1.notifications_sent == 1
        assert provider2.notifications_sent == 1

        # Verify the raw values were passed to the providers
        assert "raw_values" in provider1.last_kwargs
        raw_values = provider1.last_kwargs["raw_values"]
        assert isinstance(raw_values, dict)
        assert "progress" in raw_values
        assert "remaining_size" in raw_values
        assert "initial_size" in raw_values
        assert "eta" in raw_values
        assert "total_moved" in raw_values
