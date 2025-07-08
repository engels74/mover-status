"""Integration tests for dry-run validation scenarios."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, override
from collections.abc import Mapping
from unittest.mock import MagicMock, patch
import pytest

from mover_status.app.runner import ApplicationRunner
from mover_status.app.cli import cli
from mover_status.notifications.base.provider import NotificationProvider
from mover_status.notifications.manager.dispatcher import AsyncDispatcher
from mover_status.notifications.models.message import Message
from mover_status.config.models.monitoring import MonitoringConfig

if TYPE_CHECKING:
    pass


class DryRunMockProvider(NotificationProvider):
    """Mock provider that tracks dry-run behavior."""
    
    def __init__(self, config: Mapping[str, object], name: str = "dry_run_mock") -> None:
        super().__init__(config)
        self.name: str = name
        self.send_calls: list[Message] = []
        self.dry_run_mode: bool = bool(config.get("dry_run", False))
        self.actual_sends: int = 0
        self.dry_run_sends: int = 0
        
    @override
    async def send_notification(self, message: Message) -> bool:
        """Mock send notification with dry-run tracking."""
        self.send_calls.append(message)
        
        if self.dry_run_mode:
            self.dry_run_sends += 1
            # In dry-run mode, log but don't actually send
            print(f"DRY RUN: Would send notification: {message.title}")
            return True
        else:
            self.actual_sends += 1
            # In normal mode, simulate actual sending
            print(f"SENDING: {message.title}")
            return True
        
    @override
    def validate_config(self) -> None:
        """Mock validate config."""
        pass
        
    @override
    def get_provider_name(self) -> str:
        """Get provider name."""
        return self.name


@pytest.fixture
def dry_run_providers() -> dict[str, DryRunMockProvider]:
    """Create dry-run mock providers."""
    return {
        "dry_run_enabled": DryRunMockProvider(
            {"dry_run": True, "enabled": True}, 
            "dry_run_enabled"
        ),
        "dry_run_disabled": DryRunMockProvider(
            {"dry_run": False, "enabled": True}, 
            "dry_run_disabled"
        ),
    }


class TestDryRunValidation:
    """Test suite for dry-run validation scenarios."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_dry_run_prevents_actual_notifications(
        self, 
        dry_run_providers: dict[str, DryRunMockProvider]
    ) -> None:
        """Test that dry-run mode prevents actual notification sending."""
        # Setup dry-run provider
        provider = dry_run_providers["dry_run_enabled"]
        
        # Create test message
        message = Message(
            title="Test Notification",
            content="This is a test notification",
            priority="normal",
            tags=["test", "dry_run"]
        )
        
        # Send notification in dry-run mode
        success = await provider.send_notification(message)
        
        # Verify dry-run behavior
        assert success is True
        assert len(provider.send_calls) == 1
        assert provider.dry_run_sends == 1
        assert provider.actual_sends == 0
        
        # Verify message was logged but not actually sent
        assert provider.send_calls[0].title == "Test Notification"
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_normal_mode_sends_actual_notifications(
        self, 
        dry_run_providers: dict[str, DryRunMockProvider]
    ) -> None:
        """Test that normal mode sends actual notifications."""
        provider = dry_run_providers["dry_run_disabled"]
        
        # Create test message
        message = Message(
            title="Test Notification",
            content="This is a test notification",
            priority="normal",
            tags=["test", "normal_mode"]
        )
        
        # Send notification in normal mode
        success = await provider.send_notification(message)
        
        # Verify normal behavior
        assert success is True
        assert len(provider.send_calls) == 1
        assert provider.dry_run_sends == 0
        assert provider.actual_sends == 1
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_dispatcher_respects_dry_run_mode(
        self, 
        dry_run_providers: dict[str, DryRunMockProvider]
    ) -> None:
        """Test that the dispatcher respects dry-run mode."""
        # Setup dry-run provider
        provider = dry_run_providers["dry_run_enabled"]
        
        # Create dispatcher and register provider instance
        dispatcher = AsyncDispatcher(max_workers=2, queue_size=10)
        dispatcher.register_provider("dry_run_mock", provider)
        await dispatcher.start()
        
        try:
            # Create test message
            message = Message(
                title="Dispatcher Test",
                content="Testing dispatcher dry-run behavior",
                priority="normal",
                tags=["test", "dispatcher"]
            )
            
            # Dispatch message
            result = await dispatcher.dispatch_message(
                message=message,
                providers=["dry_run_mock"],
                priority=1
            )
            
            # Verify dispatch succeeded
            assert result.status.name in ["SUCCESS", "PARTIAL_SUCCESS"]
            
            # Verify dry-run behavior
            assert provider.dry_run_sends == 1
            assert provider.actual_sends == 0
            
        finally:
            await dispatcher.stop()
    
    @pytest.mark.integration
    def test_cli_dry_run_flag_propagation(self) -> None:
        """Test that CLI dry-run flag is properly propagated."""
        from click.testing import CliRunner
        
        runner = CliRunner()
        
        with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
            mock_instance = MagicMock()
            mock_runner.return_value = mock_instance
            
            # Test dry-run flag
            result = runner.invoke(cli, ['--dry-run', '--once'])
            
            assert result.exit_code == 0
            mock_runner.assert_called_once()
            call_args = mock_runner.call_args
            assert call_args is not None
            assert call_args.kwargs['dry_run'] is True
            assert call_args.kwargs['run_once'] is True
    
    @pytest.mark.integration
    def test_cli_dry_run_short_flag_propagation(self) -> None:
        """Test that CLI dry-run short flag is properly propagated."""
        from click.testing import CliRunner
        
        runner = CliRunner()
        
        with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
            mock_instance = MagicMock()
            mock_runner.return_value = mock_instance
            
            # Test dry-run short flag
            result = runner.invoke(cli, ['-d', '--once'])
            
            assert result.exit_code == 0
            mock_runner.assert_called_once()
            call_args = mock_runner.call_args
            assert call_args is not None
            assert call_args.kwargs['dry_run'] is True
    
    @pytest.mark.integration
    def test_config_dry_run_setting(self) -> None:
        """Test that configuration dry-run setting is respected."""
        # Test basic monitoring config with dry-run
        monitoring_config = MonitoringConfig(
            interval=30,
            detection_timeout=60,
            dry_run=True
        )
        assert monitoring_config.dry_run is True
        
        # Test default dry-run setting
        default_config = MonitoringConfig()
        assert default_config.dry_run is False
    
    @pytest.mark.integration
    def test_application_runner_dry_run_mode(self) -> None:
        """Test ApplicationRunner dry-run mode behavior."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            _ = f.write("""
monitoring:
  interval: 30
  detection_timeout: 60
  dry_run: true

process:
  name: "mover"
  paths:
    - "/usr/local/sbin/mover"

notifications:
  enabled_providers: []
  events: ["started", "completed"]
""")
            config_path = Path(f.name)
        
        try:
            # Create runner with dry-run enabled
            runner = ApplicationRunner(
                config_path=config_path,
                dry_run=True,
                log_level="INFO",
                run_once=True
            )
            
            # Verify dry-run mode is set
            assert runner.dry_run is True
            assert runner.run_once is True
            
            # Test run method (basic implementation)
            # This will be expanded when full application logic is implemented
            _ = runner.run()  # Should not raise exceptions
            
        finally:
            config_path.unlink()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_dry_run_with_multiple_providers(self) -> None:
        """Test dry-run behavior with multiple notification providers."""
        # Create multiple providers with different dry-run settings
        providers = {
            "dry_run_1": DryRunMockProvider({"dry_run": True}, "dry_run_1"),
            "dry_run_2": DryRunMockProvider({"dry_run": True}, "dry_run_2"),
            "normal": DryRunMockProvider({"dry_run": False}, "normal"),
        }

        # Create dispatcher and register providers
        dispatcher = AsyncDispatcher(max_workers=3, queue_size=10)
        for name, provider in providers.items():
            dispatcher.register_provider(name, provider)

        await dispatcher.start()

        try:
            # Create test message
            message = Message(
                title="Multi-Provider Test",
                content="Testing multiple providers with dry-run",
                priority="normal",
                tags=["test", "multi_provider"]
            )

            # Dispatch to all providers
            result = await dispatcher.dispatch_message(
                message=message,
                providers=list(providers.keys()),
                priority=1
            )

            # Verify dispatch succeeded
            assert result.status.name in ["SUCCESS", "PARTIAL_SUCCESS"]

            # Verify dry-run behavior for each provider
            assert providers["dry_run_1"].dry_run_sends == 1
            assert providers["dry_run_1"].actual_sends == 0

            assert providers["dry_run_2"].dry_run_sends == 1
            assert providers["dry_run_2"].actual_sends == 0

            assert providers["normal"].dry_run_sends == 0
            assert providers["normal"].actual_sends == 1

        finally:
            await dispatcher.stop()
