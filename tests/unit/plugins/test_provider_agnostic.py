"""Tests to verify the system is truly provider-agnostic."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import Mock, patch

import pytest

from mover_status.config.models.providers import ProviderConfig
from mover_status.app.runner import ApplicationRunner
from mover_status.plugins.loader.loader import PluginLoader
from mover_status.plugins.loader.discovery import PluginDiscovery, PluginInfo
from mover_status.notifications.base.registry import ProviderMetadata
from mover_status.notifications.base.provider import NotificationProvider

if TYPE_CHECKING:
    from unittest.mock import MagicMock


class TestProviderAgnosticSystem:
    """Test that the plugin system is truly provider-agnostic."""
    
    def test_provider_config_supports_dynamic_providers(self) -> None:
        """Test that ProviderConfig can handle any provider dynamically."""
        # Test with custom provider configurations
        config_data = {
            "telegram": {"bot_token": "test_token", "chat_ids": [123]},
            "discord": {"webhook_url": "https://discord.com/api/webhooks/123/abc"},
            "custom_provider": {"api_key": "test_key", "endpoint": "https://api.custom.com"},
            "another_provider": {"username": "test", "password": "secret"}
        }
        
        provider_config = ProviderConfig.model_validate(config_data)
        
        # Should be able to get configuration for any provider
        telegram_config = provider_config.get_provider_config("telegram")
        assert telegram_config is not None
        assert telegram_config["bot_token"] == "test_token"
        
        discord_config = provider_config.get_provider_config("discord")
        assert discord_config is not None
        assert discord_config["webhook_url"] == "https://discord.com/api/webhooks/123/abc"
        
        custom_config = provider_config.get_provider_config("custom_provider")
        assert custom_config is not None
        assert custom_config["api_key"] == "test_key"
        
        another_config = provider_config.get_provider_config("another_provider")
        assert another_config is not None
        assert another_config["username"] == "test"
        
        # Should return None for non-existent providers
        assert provider_config.get_provider_config("nonexistent") is None
    
    def test_provider_config_lists_all_providers(self) -> None:
        """Test that ProviderConfig can list all configured providers."""
        config_data = {
            "telegram": {"bot_token": "test", "chat_ids": [123]},
            "discord": {"webhook_url": "https://test.com"},
            "slack": {"webhook_url": "https://slack.com"},
            "email": {"smtp_server": "smtp.test.com"}
        }
        
        provider_config = ProviderConfig.model_validate(config_data)
        configured_providers = provider_config.list_configured_providers()
        
        # Should include all providers
        assert "telegram" in configured_providers
        assert "discord" in configured_providers
        assert "slack" in configured_providers
        assert "email" in configured_providers
    
    def test_plugin_discovery_finds_any_provider(self) -> None:
        """Test that plugin discovery can find providers without hardcoding."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create a custom provider plugin directory
            custom_plugin_dir = temp_path / "custom_provider"
            custom_plugin_dir.mkdir()
            
            # Create __init__.py
            _ = (custom_plugin_dir / "__init__.py").write_text("")
            
            # Create provider.py with a mock provider class
            provider_py = '''
from mover_status.notifications.base.provider import NotificationProvider

PLUGIN_METADATA = {
    "name": "custom_provider",
    "description": "Custom test provider",
    "version": "1.0.0",
    "author": "Test"
}

class CustomProvider(NotificationProvider):
    def __init__(self, config):
        super().__init__(config)
    
    async def send_notification(self, message):
        return True
    
    def validate_config(self):
        pass
    
    def get_provider_name(self):
        return "custom_provider"
'''
            _ = (custom_plugin_dir / "provider.py").write_text(provider_py)
            
            # Test discovery
            discovery = PluginDiscovery()
            discovery._search_paths = [temp_path]  # pyright: ignore[reportPrivateUsage] # Direct modification needed for testing
            
            plugins = discovery.discover_plugins()
            
            # Should find the custom provider
            assert "custom_provider" in plugins
            plugin_info = plugins["custom_provider"]
            assert plugin_info.name == "custom_provider"
            assert plugin_info.provider_class is not None
    
    @patch('mover_status.app.runner.ApplicationRunner._setup_components')
    @patch('mover_status.app.runner.ApplicationRunner._setup_logging')
    def test_runner_extracts_any_provider_config(
        self, 
        mock_setup_logging: MagicMock,
        mock_setup_components: MagicMock
    ) -> None:
        """Test that ApplicationRunner can extract configuration for any provider."""
        _ = mock_setup_logging  # Unused parameter
        _ = mock_setup_components  # Unused parameter
        # Create a mock config with various providers
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            _ = config_path.write_text("""
monitoring:
  interval: 30
process:
  name: "test"
  paths: ["/test"]
notifications:
  enabled_providers: ["custom_provider", "another_provider"]
""")
            
            # Mock the config loading to include custom providers
            mock_config = Mock()
            mock_config.notifications.enabled_providers = ["custom_provider", "another_provider"]  # pyright: ignore[reportAny] # Mock object
            mock_config.providers = Mock()
            
            # Mock custom provider configs
            custom_provider_config = Mock()
            custom_provider_config.model_dump.return_value = {"api_key": "test_key"}  # pyright: ignore[reportAny] # Mock object
            
            another_provider_config = Mock()
            another_provider_config.model_dump.return_value = {"endpoint": "https://test.com"}  # pyright: ignore[reportAny] # Mock object
            
            mock_config.providers.get_provider_config.side_effect = lambda name: {  # pyright: ignore[reportUnknownLambdaType,reportAny] # Mock side_effect function
                "custom_provider": {"api_key": "test_key"},
                "another_provider": {"endpoint": "https://test.com"}
            }.get(cast(str, name))
            
            with patch('mover_status.app.runner.ConfigLoader') as mock_loader_class:
                mock_loader = mock_loader_class.return_value  # pyright: ignore[reportAny] # Mock object
                mock_loader.load_complete_config.return_value = {}  # pyright: ignore[reportAny] # Mock object
                
                with patch('mover_status.config.models.main.AppConfig.model_validate', return_value=mock_config):
                    runner = ApplicationRunner(config_path)
                    
                    # Test the configuration extraction
                    provider_configs = runner._extract_provider_configurations(  # pyright: ignore[reportPrivateUsage] # Testing protected method
                        ["custom_provider", "another_provider"]
                    )
                    
                    # Should extract configurations for both providers
                    assert "custom_provider" in provider_configs
                    assert "another_provider" in provider_configs
                    assert provider_configs["custom_provider"]["api_key"] == "test_key"
                    assert provider_configs["another_provider"]["endpoint"] == "https://test.com"
    
    def test_plugin_loader_loads_any_provider(self) -> None:
        """Test that PluginLoader can load any provider without hardcoding."""
        # Create mock plugin infos for various providers
        custom_provider_class = cast(type[NotificationProvider], Mock())
        custom_metadata = ProviderMetadata(
            name="custom_provider",
            description="Custom provider",
            version="1.0.0",
            author="Test",
            provider_class=custom_provider_class
        )
        
        slack_provider_class = cast(type[NotificationProvider], Mock())
        slack_metadata = ProviderMetadata(
            name="slack",
            description="Slack provider", 
            version="1.0.0",
            author="Test",
            provider_class=slack_provider_class
        )
        
        custom_plugin = PluginInfo(
            name="custom_provider",
            path=Mock(),
            module_name="custom.module",
            provider_class=custom_provider_class,
            metadata=custom_metadata
        )
        
        slack_plugin = PluginInfo(
            name="slack",
            path=Mock(),
            module_name="slack.module", 
            provider_class=slack_provider_class,
            metadata=slack_metadata
        )
        
        # Mock discovery
        mock_discovery = Mock()
        mock_discovery.discover_plugins.return_value = {  # pyright: ignore[reportAny] # Mock object
            "custom_provider": custom_plugin,
            "slack": slack_plugin
        }
        
        loader = PluginLoader(discovery=mock_discovery)
        
        # Should be able to load any provider
        results = loader.load_enabled_plugins(["custom_provider", "slack"])
        
        assert results == {"custom_provider": True, "slack": True}
        assert "custom_provider" in loader.loaded_plugins
        assert "slack" in loader.loaded_plugins
    
    def test_no_hardcoded_provider_names_in_runner(self) -> None:
        """Test that runner.py contains no hardcoded provider names."""
        runner_file = Path(__file__).parent.parent.parent.parent / "src" / "mover_status" / "app" / "runner.py"
        content = runner_file.read_text()
        
        # Should not contain hardcoded references to specific providers in conditional logic
        # We allow them in comments and strings, but not in actual code logic
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Skip comments and docstrings
            if line.strip().startswith('#') or '"""' in line or "'''" in line:
                continue
            
            # Check for hardcoded provider conditionals (the old bad pattern)
            if ('== "discord"' in line or '== "telegram"' in line) and 'provider_name' in line:
                pytest.fail(f"Found hardcoded provider conditional on line {i}: {line.strip()}")
    
    def test_configuration_extraction_is_generic(self) -> None:
        """Test that configuration extraction works for any provider name."""
        # Create a mock config with various provider types
        mock_config = Mock()
        
        # Mock providers config
        mock_providers = Mock()
        
        # Set up get_provider_config to return different configs
        def mock_get_provider_config(provider_name: str) -> dict[str, object] | None:
            configs: dict[str, dict[str, object]] = {
                "email": {"smtp_server": "smtp.test.com", "username": "test@test.com"},
                "sms": {"api_key": "sms_key", "phone_numbers": ["+1234567890"]},
                "webhook": {"url": "https://webhook.test.com", "secret": "webhook_secret"},
                "push": {"app_id": "push_app", "auth_key": "push_auth"}
            }
            return configs.get(provider_name)
        
        mock_providers.get_provider_config.side_effect = mock_get_provider_config  # pyright: ignore[reportAny] # Mock object
        mock_config.providers = mock_providers
        
        # Create a minimal runner instance just for testing the method
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            _ = config_path.write_text("monitoring: {}")
            
            with patch('mover_status.app.runner.ConfigLoader'), \
                 patch('mover_status.config.models.main.AppConfig.model_validate', return_value=mock_config), \
                 patch('mover_status.app.runner.ApplicationRunner._setup_logging'):
                
                runner = ApplicationRunner(config_path)
                
                # Test extracting configurations for various providers
                provider_configs = runner._extract_provider_configurations([  # pyright: ignore[reportPrivateUsage] # Testing protected method
                    "email", "sms", "webhook", "push"
                ])
                
                # Should extract all configurations without hardcoding
                assert len(provider_configs) == 4
                assert provider_configs["email"]["smtp_server"] == "smtp.test.com"
                assert provider_configs["sms"]["api_key"] == "sms_key"
                assert provider_configs["webhook"]["url"] == "https://webhook.test.com"
                assert provider_configs["push"]["app_id"] == "push_app"


class TestBackwardCompatibility:
    """Test that the changes maintain backward compatibility."""
    
    def test_existing_discord_telegram_still_work(self) -> None:
        """Test that existing Discord and Telegram configurations still work."""
        from mover_status.config.models.providers import DiscordConfig, TelegramConfig
        
        # Test with the old-style configuration
        provider_config = ProviderConfig(
            discord=DiscordConfig(webhook_url="https://discord.com/api/webhooks/123/abc"),
            telegram=TelegramConfig(bot_token="123:abc", chat_ids=[123456])
        )
        
        # Should still be able to get configurations
        discord_config = provider_config.get_provider_config("discord")
        assert discord_config is not None
        assert discord_config["webhook_url"] == "https://discord.com/api/webhooks/123/abc"
        
        telegram_config = provider_config.get_provider_config("telegram")
        assert telegram_config is not None
        assert telegram_config["bot_token"] == "123:abc"
        assert telegram_config["chat_ids"] == [123456]
        
        # Should list both providers
        configured = provider_config.list_configured_providers()
        assert "discord" in configured
        assert "telegram" in configured