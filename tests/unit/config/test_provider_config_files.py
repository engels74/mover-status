"""Tests for provider-specific configuration file management."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import cast
from unittest.mock import patch
import pytest
import yaml

from mover_status.config.loader.yaml_loader import YamlLoader
from mover_status.config.loader.env_loader import EnvLoader
from mover_status.config.loader.config_loader import ConfigLoader
from mover_status.config.manager.config_merger import ConfigMerger
from mover_status.config.manager.provider_config_manager import ProviderConfigManager
from mover_status.config.models.main import AppConfig
from mover_status.config.exceptions import ConfigLoadError


class TestProviderConfigFileManager:
    """Test provider-specific configuration file management."""

    def test_load_main_config_with_provider_flags(self) -> None:
        """Test loading main config with provider enablement flags only."""
        main_config: dict[str, object] = {
            "process": {
                "name": "mover",
                "paths": ["/usr/bin/mover"],
            },
            "monitoring": {
                "interval": 30,
            },
            "notifications": {
                "enabled_providers": ["telegram", "discord"],
            },
            "providers": {
                "telegram": {
                    "enabled": True,
                },
                "discord": {
                    "enabled": True,
                },
            },
        }
        
        # Should not contain provider-specific settings in main config
        providers = cast(dict[str, dict[str, object]], main_config["providers"])
        telegram_providers = providers["telegram"]
        discord_providers = providers["discord"]
        assert "bot_token" not in telegram_providers
        assert "webhook_url" not in discord_providers

    def test_load_provider_config_file_telegram(self) -> None:
        """Test loading telegram-specific configuration file."""
        telegram_config = {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_ids": [123456789, -1001234567890],
            "format": {
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            "notifications": {
                "events": ["started", "progress", "completed", "failed"],
            },
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(telegram_config, f)
            temp_path = Path(f.name)
        
        try:
            loader = YamlLoader()
            loaded_config = loader.load(temp_path)
            
            assert cast(str, loaded_config["bot_token"]) == telegram_config["bot_token"]
            assert cast(list[int], loaded_config["chat_ids"]) == telegram_config["chat_ids"]
            format_config = cast(dict[str, object], loaded_config["format"])
            assert format_config["parse_mode"] == "HTML"
        finally:
            temp_path.unlink()

    def test_load_provider_config_file_discord(self) -> None:
        """Test loading discord-specific configuration file."""
        discord_config = {
            "webhook_url": "https://discord.com/api/webhooks/123456789/abcdefghijk",
            "username": "Mover Status Bot",
            "embeds": {
                "enabled": True,
                "colors": {
                    "started": 0x00ff00,
                    "progress": 0x0099ff,
                    "completed": 0x00cc00,
                    "failed": 0xff0000,
                },
            },
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(discord_config, f)
            temp_path = Path(f.name)
        
        try:
            loader = YamlLoader()
            loaded_config = loader.load(temp_path)
            
            assert cast(str, loaded_config["webhook_url"]) == discord_config["webhook_url"]
            assert cast(str, loaded_config["username"]) == discord_config["username"]
            embeds_config = cast(dict[str, object], loaded_config["embeds"])
            colors_config = cast(dict[str, int], embeds_config["colors"])
            assert colors_config["started"] == 0x00ff00
        finally:
            temp_path.unlink()

    def test_auto_create_provider_config_on_enable(self) -> None:
        """Test auto-creation of provider config file when provider is first enabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            manager = ProviderConfigManager(config_dir)
            
            # Enable telegram provider
            telegram_config_path = config_dir / "config_telegram.yaml"
            assert not telegram_config_path.exists()
            
            # Should create default config file
            created_config = manager.ensure_provider_config("telegram")
            
            assert telegram_config_path.exists()
            assert "bot_token" in created_config
            assert created_config["bot_token"] == "YOUR_BOT_TOKEN"  # Default placeholder

    def test_preserve_provider_config_on_disable(self) -> None:
        """Test that provider config files are preserved when provider is disabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            manager = ProviderConfigManager(config_dir)
            
            # Create existing telegram config
            telegram_config_path = config_dir / "config_telegram.yaml"
            existing_config = {
                "bot_token": "123456:EXISTING-TOKEN",
                "chat_ids": [999999999],
            }
            with open(telegram_config_path, 'w') as f:
                yaml.dump(existing_config, f)
            
            # Disable provider (should NOT delete the config file)
            manager.disable_provider("telegram")
            
            # Config file should still exist
            assert telegram_config_path.exists()
            
            # Content should be unchanged
            with open(telegram_config_path, 'r') as f:
                yaml_content: object = yaml.safe_load(f)  # pyright: ignore[reportAny] # yaml.safe_load returns Any
                assert isinstance(yaml_content, dict), "Expected dict from YAML file"
                preserved_config: dict[str, object] = yaml_content  # pyright: ignore[reportUnknownVariableType] # Type narrowed by isinstance check
            assert preserved_config["bot_token"] == "123456:EXISTING-TOKEN"

    def test_merge_main_and_provider_configs(self) -> None:
        """Test merging main config with provider-specific configs."""
        main_config: dict[str, object] = {
            "process": {
                "name": "mover",
                "paths": ["/usr/bin/mover"],
            },
            "notifications": {
                "enabled_providers": ["telegram"],
            },
            "providers": {
                "telegram": {},  # Empty initially, will be populated from provider config
            },
        }
        
        telegram_config: dict[str, object] = {
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "chat_ids": [123456789],
        }
        
        # Merge configs - provider configs should be merged under providers.<provider_name>
        providers = cast(dict[str, dict[str, object]], main_config["providers"])
        telegram_provider = providers["telegram"]
        telegram_provider.update(telegram_config)
        
        # Validate merged config
        app_config = AppConfig.model_validate(main_config)
        assert app_config.providers.telegram is not None
        assert app_config.providers.telegram.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"

    def test_missing_provider_config_file_graceful_handling(self) -> None:
        """Test graceful handling when provider config file is missing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            manager = ProviderConfigManager(config_dir)
            
            # Try to load non-existent provider config
            config = manager.load_provider_config("telegram")
            
            # Should return None or empty config
            assert config is None

    def test_invalid_provider_config_file_error_handling(self) -> None:
        """Test error handling for invalid provider config files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            manager = ProviderConfigManager(config_dir)
            
            # Create invalid YAML file
            invalid_config_path = config_dir / "config_telegram.yaml"
            with open(invalid_config_path, 'w') as f:
                _ = f.write("invalid: yaml: content: [")
            
            # Should raise or handle error gracefully
            with pytest.raises(ConfigLoadError):
                _ = manager.load_provider_config("telegram")

    def test_environment_override_for_provider_configs(self) -> None:
        """Test that environment variables can override provider-specific configs."""
        telegram_config: dict[str, object] = {
            "bot_token": "123456:FILE-TOKEN",
            "chat_ids": [123456789],
        }
        
        env_vars = {
            "MOVER_STATUS_PROVIDERS__TELEGRAM__BOT_TOKEN": "987654:ENV-TOKEN",
        }
        
        with patch.dict(os.environ, env_vars):
            env_loader = EnvLoader(convert_types=True)
            env_config = env_loader.load()
            
            merger = ConfigMerger()
            base: dict[str, object] = {"providers": {"telegram": telegram_config}}
            merged = merger.merge(base, env_config)
            
            # Environment should override file config
            providers_config = cast(dict[str, object], merged["providers"])
            telegram_merged = cast(dict[str, object], providers_config["telegram"])
            assert telegram_merged["bot_token"] == "987654:ENV-TOKEN"
            assert telegram_merged["chat_ids"] == [123456789]  # Unchanged


class TestProviderConfigIntegration:
    """Integration tests for provider-specific configuration system."""

    def test_complete_configuration_pipeline_with_provider_files(self) -> None:
        """Test complete configuration loading with provider-specific files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            
            # Create main config
            main_config: dict[str, object] = {
                "process": {
                    "name": "mover",
                    "paths": ["/usr/bin/mover"],
                },
                "notifications": {
                    "enabled_providers": ["telegram", "discord"],
                },
                "providers": {
                    "telegram": {},  # Empty, will be populated from provider config file
                    "discord": {},   # Empty, will be populated from provider config file
                },
            }
            main_config_path = config_dir / "config.yaml"
            with open(main_config_path, 'w') as f:
                yaml.dump(main_config, f)
            
            # Create telegram config
            telegram_config = {
                "bot_token": "123456:TELEGRAM-TOKEN",
                "chat_ids": [123456789],
            }
            telegram_config_path = config_dir / "config_telegram.yaml"
            with open(telegram_config_path, 'w') as f:
                yaml.dump(telegram_config, f)
            
            # Create discord config
            discord_config = {
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
                "username": "Bot",
            }
            discord_config_path = config_dir / "config_discord.yaml"
            with open(discord_config_path, 'w') as f:
                yaml.dump(discord_config, f)
            
            # Load complete configuration
            loader = ConfigLoader(config_dir)
            config = loader.load_complete_config()
            
            # Validate complete config
            app_config = AppConfig.model_validate(config)
            
            # Check main config
            assert app_config.process.name == "mover"
            assert app_config.notifications.enabled_providers == ["telegram", "discord"]
            
            # Check provider configs were loaded and merged
            assert app_config.providers.telegram is not None
            assert app_config.providers.telegram.bot_token == "123456:TELEGRAM-TOKEN"
            assert app_config.providers.discord is not None
            assert app_config.providers.discord.webhook_url == "https://discord.com/api/webhooks/123/abc"

    def test_unified_config_format_not_supported(self) -> None:
        """Test that unified config format is no longer supported - separate files required."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            
            # Create unified config with provider configs directly in main file (old format)
            unified_config = {
                "process": {
                    "name": "mover",
                    "paths": ["/usr/bin/mover"],
                },
                "notifications": {
                    "enabled_providers": ["telegram"],
                },
                "providers": {
                    "telegram": {
                        "bot_token": "123456:UNIFIED-TOKEN",
                        "chat_ids": [123456789],
                    },
                },
            }
            config_path = config_dir / "config.yaml"
            with open(config_path, 'w') as f:
                yaml.dump(unified_config, f)
            
            # Load with new system - should create separate provider file and override inline config
            loader = ConfigLoader(config_dir)
            config = loader.load_complete_config()
            
            # Should use auto-created provider config, not the inline config
            # Check the raw config before validation (since template has placeholder values)
            providers_config = cast(dict[str, object], config["providers"])
            telegram_config = cast(dict[str, object], providers_config["telegram"])
            
            # Inline config should be overwritten by provider file template
            assert telegram_config["bot_token"] == "YOUR_BOT_TOKEN"  # Default template value
            assert telegram_config["chat_ids"] == ["YOUR_CHAT_ID"]  # Default template value
            
            # Verify that a separate provider config file was created
            telegram_config_path = config_dir / "config_telegram.yaml"
            assert telegram_config_path.exists()

    def test_provider_config_template_generation(self) -> None:
        """Test generation of provider config templates with sensible defaults."""
        manager = ProviderConfigManager(Path("."))
        
        # Test telegram template
        telegram_template = manager.get_provider_template("telegram")
        assert "bot_token" in telegram_template
        assert "chat_ids" in telegram_template
        assert telegram_template["bot_token"] == "YOUR_BOT_TOKEN"
        assert telegram_template["chat_ids"] == ["YOUR_CHAT_ID"]
        
        # Test discord template
        discord_template = manager.get_provider_template("discord")
        assert "webhook_url" in discord_template
        assert discord_template["webhook_url"] == "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN" 