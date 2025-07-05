"""Integration tests for the complete configuration system."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from mover_status.config.loader.yaml_loader import YamlLoader
from mover_status.config.loader.env_loader import EnvLoader
from mover_status.config.manager.config_merger import ConfigMerger
from mover_status.config.models.main import AppConfig
from mover_status.config.models.monitoring import ProcessConfig
from mover_status.config.models.providers import TelegramConfig, DiscordConfig, ProviderConfig
from mover_status.config.exceptions import ConfigValidationError


class TestConfigurationSystemIntegration:
    """Integration tests for the complete configuration system."""

    def test_yaml_to_pydantic_integration(self) -> None:
        """Test loading YAML configuration and validating with Pydantic models."""
        yaml_config = {
            "monitoring": {
                "interval": 60,
                "detection_timeout": 600,
                "dry_run": False,
            },
            "process": {
                "name": "mover",
                "path": "/usr/local/sbin/mover",
            },
            "progress": {
                "min_change_threshold": 10.0,
                "estimation_window": 20,
                "exclusions": ["/tmp", "/var/tmp"],
            },
            "notifications": {
                "enabled_providers": ["telegram"],
                "events": ["started", "completed"],
            },
            "logging": {
                "level": "DEBUG",
                "format": "%(levelname)s: %(message)s",
            },
            "providers": {
                "telegram": {
                    "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                    "chat_ids": [123456789],
                },
            },
        }
        
        # Create temporary YAML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(yaml_config, f)
            temp_path = Path(f.name)
        
        try:
            # Load YAML
            loader = YamlLoader()
            loaded_config = loader.load(temp_path)
            
            # Validate with Pydantic
            app_config = AppConfig.model_validate(loaded_config)
            
            # Verify configuration
            assert app_config.monitoring.interval == 60
            assert app_config.process.name == "mover"
            assert app_config.progress.min_change_threshold == 10.0
            assert app_config.notifications.enabled_providers == ["telegram"]
            assert app_config.logging.level == "DEBUG"
            assert app_config.providers.telegram is not None
            assert app_config.providers.telegram.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
            
        finally:
            temp_path.unlink()

    def test_env_override_integration(self) -> None:
        """Test environment variable overrides with Pydantic validation."""
        base_config = {
            "process": {
                "name": "mover",
                "path": "/usr/local/sbin/mover",
            },
            "monitoring": {
                "interval": 30,
            },
            "providers": {
                "telegram": {
                    "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                    "chat_ids": [123456789],
                },
            },
        }
        
        env_vars = {
            "MOVER_STATUS_MONITORING_INTERVAL": "60",
            "MOVER_STATUS_MONITORING_DRY_RUN": "true",
            "MOVER_STATUS_PROVIDERS_TELEGRAM_CHAT_IDS": "[987654321, 123456789]",
        }
        
        with patch.dict(os.environ, env_vars):
            # Load environment overrides
            env_loader = EnvLoader(convert_types=True)
            env_config = env_loader.load()
            
            # Merge configurations
            merger = ConfigMerger()
            merged_config = merger.merge(base_config, env_config)
            
            # Validate with Pydantic
            app_config = AppConfig.model_validate(merged_config)
            
            # Verify overrides took effect
            assert app_config.monitoring.interval == 60  # Overridden
            assert app_config.monitoring.dry_run is True  # Overridden
            assert app_config.providers.telegram is not None
            assert 987654321 in app_config.providers.telegram.chat_ids  # Overridden

    def test_complete_configuration_pipeline(self) -> None:
        """Test the complete configuration loading pipeline."""
        # Base YAML configuration
        yaml_config = {
            "process": {
                "name": "rsync",
                "path": "/usr/bin/rsync",
            },
            "monitoring": {
                "interval": 30,
                "detection_timeout": 300,
            },
            "notifications": {
                "enabled_providers": ["telegram", "discord"],
                "events": ["started", "progress", "completed", "failed"],
            },
            "providers": {
                "telegram": {
                    "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                    "chat_ids": [123456789],
                },
                "discord": {
                    "webhook_url": "https://discord.com/api/webhooks/123/abc",
                },
            },
        }
        
        # Environment overrides
        env_vars = {
            "MOVER_STATUS_MONITORING_INTERVAL": "45",
            "MOVER_STATUS_MONITORING_DRY_RUN": "true",
            "MOVER_STATUS_NOTIFICATIONS_EVENTS": '["started", "completed"]',
            "MOVER_STATUS_PROVIDERS_TELEGRAM_CHAT_IDS": "[987654321]",
        }
        
        # Create temporary YAML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(yaml_config, f)
            temp_path = Path(f.name)
        
        try:
            with patch.dict(os.environ, env_vars):
                # Step 1: Load YAML configuration
                yaml_loader = YamlLoader()
                yaml_data = yaml_loader.load(temp_path)
                
                # Step 2: Load environment overrides
                env_loader = EnvLoader(convert_types=True)
                env_data = env_loader.load()
                
                # Step 3: Merge configurations (env overrides yaml)
                merger = ConfigMerger()
                merged_data = merger.merge(yaml_data, env_data)
                
                # Step 4: Validate with Pydantic
                app_config = AppConfig.model_validate(merged_data)
                
                # Verify final configuration
                assert app_config.process.name == "rsync"  # From YAML
                assert app_config.monitoring.interval == 45  # From env override
                assert app_config.monitoring.dry_run is True  # From env override
                assert app_config.notifications.events == ["started", "completed"]  # From env override
                assert app_config.providers.telegram is not None
                assert app_config.providers.telegram.chat_ids == [987654321]  # From env override
                assert app_config.providers.discord is not None
                assert app_config.providers.discord.webhook_url == "https://discord.com/api/webhooks/123/abc"  # From YAML
                
        finally:
            temp_path.unlink()

    def test_configuration_validation_errors_integration(self) -> None:
        """Test configuration validation errors in the complete pipeline."""
        # Invalid configuration (missing required process field)
        invalid_config = {
            "monitoring": {
                "interval": 30,
            },
            # Missing required "process" field
        }
        
        # Create temporary YAML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(invalid_config, f)
            temp_path = Path(f.name)
        
        try:
            # Load YAML
            yaml_loader = YamlLoader()
            yaml_data = yaml_loader.load(temp_path)
            
            # Attempt to validate with Pydantic (should fail)
            with pytest.raises(Exception) as exc_info:  # Could be ValidationError or ConfigValidationError
                AppConfig.model_validate(yaml_data)
            
            # Verify it's a validation error
            assert "process" in str(exc_info.value).lower()
            
        finally:
            temp_path.unlink()

    def test_provider_consistency_validation_integration(self) -> None:
        """Test provider consistency validation in the complete pipeline."""
        # Configuration with enabled provider but no provider config
        inconsistent_config = {
            "process": {
                "name": "mover",
                "path": "/usr/bin/mover",
            },
            "notifications": {
                "enabled_providers": ["telegram"],  # Enabled but not configured
            },
            "providers": {
                # No telegram configuration
            },
        }
        
        # Create temporary YAML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(inconsistent_config, f)
            temp_path = Path(f.name)
        
        try:
            # Load and validate
            yaml_loader = YamlLoader()
            yaml_data = yaml_loader.load(temp_path)
            
            # Should fail validation due to inconsistency
            with pytest.raises(Exception) as exc_info:
                AppConfig.model_validate(yaml_data)
            
            # Verify it's the expected validation error
            assert "telegram" in str(exc_info.value).lower()
            assert "not configured" in str(exc_info.value).lower()
            
        finally:
            temp_path.unlink()

    def test_complex_nested_override_integration(self) -> None:
        """Test complex nested configuration overrides."""
        base_config = {
            "process": {
                "name": "mover",
                "path": "/usr/bin/mover",
            },
            "providers": {
                "telegram": {
                    "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                    "chat_ids": [123456789],
                    "format": {
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                    "templates": {
                        "started": "Original started template",
                        "progress": "Original progress template",
                    },
                },
            },
        }
        
        env_vars = {
            "MOVER_STATUS_PROVIDERS_TELEGRAM_FORMAT_PARSE_MODE": "Markdown",
            "MOVER_STATUS_PROVIDERS_TELEGRAM_TEMPLATES_STARTED": "Overridden started template",
        }
        
        with patch.dict(os.environ, env_vars):
            # Load environment overrides
            env_loader = EnvLoader(convert_types=True)
            env_config = env_loader.load()
            
            # Merge configurations
            merger = ConfigMerger()
            merged_config = merger.merge(base_config, env_config)
            
            # Validate with Pydantic
            app_config = AppConfig.model_validate(merged_config)
            
            # Verify nested overrides
            assert app_config.providers.telegram is not None
            assert app_config.providers.telegram.format.parse_mode == "Markdown"  # Overridden
            assert app_config.providers.telegram.format.disable_web_page_preview is True  # Preserved
            assert app_config.providers.telegram.templates.started == "Overridden started template"  # Overridden
            assert app_config.providers.telegram.templates.progress == "Original progress template"  # Preserved

    def test_multiple_configuration_sources_integration(self) -> None:
        """Test merging multiple configuration sources with proper precedence."""
        # Default configuration
        defaults = {
            "monitoring": {
                "interval": 30,
                "detection_timeout": 300,
                "dry_run": False,
            },
            "process": {
                "name": "mover",
                "path": "/usr/bin/mover",
            },
        }
        
        # File configuration
        file_config = {
            "monitoring": {
                "interval": 60,  # Override default
                "detection_timeout": 600,  # Override default
            },
            "notifications": {
                "enabled_providers": ["telegram"],  # New field
            },
        }
        
        # Environment configuration
        env_config = {
            "monitoring": {
                "interval": 90,  # Override file and default
            },
            "logging": {
                "level": "DEBUG",  # New field
            },
        }
        
        # Merge all sources (precedence: env > file > defaults)
        merger = ConfigMerger()
        merged_config = merger.merge_multiple([defaults, file_config, env_config])
        
        # Validate with Pydantic
        app_config = AppConfig.model_validate(merged_config)
        
        # Verify precedence rules
        assert app_config.monitoring.interval == 90  # From env (highest precedence)
        assert app_config.monitoring.detection_timeout == 600  # From file
        assert app_config.monitoring.dry_run is False  # From defaults
        assert app_config.notifications.enabled_providers == ["telegram"]  # From file
        assert app_config.logging.level == "DEBUG"  # From env


class TestEndToEndConfigurationScenarios:
    """End-to-end tests for real-world configuration scenarios."""

    def test_production_configuration_scenario(self) -> None:
        """Test a realistic production configuration scenario."""
        # Production YAML configuration
        production_config = {
            "monitoring": {
                "interval": 60,
                "detection_timeout": 900,
                "dry_run": False,
            },
            "process": {
                "name": "mover",
                "path": "/usr/local/sbin/mover",
            },
            "progress": {
                "min_change_threshold": 1.0,
                "estimation_window": 20,
                "exclusions": [
                    "/.Trash-*",
                    "/lost+found",
                    "/tmp",
                    "/var/tmp",
                    "/proc",
                    "/sys",
                ],
            },
            "notifications": {
                "enabled_providers": ["telegram", "discord"],
                "events": ["started", "progress", "completed", "failed"],
                "rate_limits": {
                    "progress": 600,  # 10 minutes
                    "status": 120,    # 2 minutes
                },
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file_path": "/var/log/mover-status.log",
            },
            "providers": {
                "telegram": {
                    "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                    "chat_ids": [-1001234567890],
                    "format": {
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                        "disable_notification": False,
                    },
                    "notifications": {
                        "events": ["started", "completed", "failed"],
                    },
                },
                "discord": {
                    "webhook_url": "https://discord.com/api/webhooks/123456789/abcdefghijk",
                    "embeds": {
                        "enabled": True,
                        "title": "Mover Status Update",
                        "footer": "Production Mover Monitor",
                        "timestamp": True,
                        "colors": {
                            "started": 0x3498DB,
                            "progress": 0xF39C12,
                            "completed": 0x2ECC71,
                            "failed": 0xE74C3C,
                        },
                    },
                    "notifications": {
                        "events": ["started", "completed", "failed"],
                        "mentions": {
                            "users": ["123456789"],
                            "roles": ["admin"],
                            "everyone": False,
                        },
                    },
                },
            },
        }

        # Environment overrides for production deployment
        production_env = {
            "MOVER_STATUS_MONITORING_DRY_RUN": "false",
            "MOVER_STATUS_LOGGING_LEVEL": "WARNING",
            "TELEGRAM_BOT_TOKEN": "987654:XYZ-PROD9876def54321-uvw98x7y6z5a4b3c2d1e",
            "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/987654321/production-webhook",
        }

        # Custom environment mappings for sensitive data
        env_mappings = {
            "TELEGRAM_BOT_TOKEN": "providers.telegram.bot_token",
            "DISCORD_WEBHOOK_URL": "providers.discord.webhook_url",
        }

        # Create temporary YAML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(production_config, f)
            temp_path = Path(f.name)

        try:
            with patch.dict(os.environ, production_env):
                # Load configuration pipeline
                yaml_loader = YamlLoader()
                yaml_data = yaml_loader.load(temp_path)

                env_loader = EnvLoader(
                    convert_types=True,
                    mappings=env_mappings,
                )
                env_data = env_loader.load()

                merger = ConfigMerger()
                final_config = merger.merge(yaml_data, env_data)

                # Validate final configuration
                app_config = AppConfig.model_validate(final_config)

                # Verify production settings
                assert app_config.monitoring.interval == 60
                assert app_config.monitoring.dry_run is False
                assert app_config.logging.level == "WARNING"  # Overridden by env
                assert app_config.providers.telegram is not None
                assert app_config.providers.telegram.bot_token == "987654:XYZ-PROD9876def54321-uvw98x7y6z5a4b3c2d1e"  # From env
                assert app_config.providers.discord is not None
                assert app_config.providers.discord.webhook_url == "https://discord.com/api/webhooks/987654321/production-webhook"  # From env

        finally:
            temp_path.unlink()

    def test_development_configuration_scenario(self) -> None:
        """Test a development configuration scenario with debugging enabled."""
        dev_config = {
            "monitoring": {
                "interval": 10,  # Faster for development
                "detection_timeout": 60,
                "dry_run": True,  # Safe for development
            },
            "process": {
                "name": "test-mover",
                "path": "/usr/local/bin/test-mover",
            },
            "progress": {
                "min_change_threshold": 0.1,  # More sensitive for testing
                "estimation_window": 5,
            },
            "notifications": {
                "enabled_providers": ["telegram"],  # Only telegram for dev
                "events": ["started", "progress", "completed", "failed"],
            },
            "logging": {
                "level": "DEBUG",
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            },
            "providers": {
                "telegram": {
                    "bot_token": "123456:DEV-TOKEN-ABC123def456ghi789jkl",
                    "chat_ids": [123456789],  # Developer's personal chat
                    "notifications": {
                        "events": ["started", "completed", "failed"],
                    },
                },
            },
        }

        # Validate development configuration
        app_config = AppConfig.model_validate(dev_config)

        # Verify development-specific settings
        assert app_config.monitoring.interval == 10
        assert app_config.monitoring.dry_run is True
        assert app_config.logging.level == "DEBUG"
        assert app_config.notifications.enabled_providers == ["telegram"]
        assert app_config.providers.telegram is not None
        assert app_config.providers.telegram.notifications.events == ["started", "completed", "failed"]
        assert app_config.providers.discord is None  # Not configured for dev

    def test_minimal_configuration_scenario(self) -> None:
        """Test minimal configuration with only required fields."""
        minimal_config = {
            "process": {
                "name": "mover",
                "path": "/usr/bin/mover",
            },
        }

        # Validate minimal configuration
        app_config = AppConfig.model_validate(minimal_config)

        # Verify defaults are applied
        assert app_config.process.name == "mover"
        assert app_config.monitoring.interval == 30  # Default
        assert app_config.monitoring.dry_run is False  # Default
        assert app_config.notifications.enabled_providers == []  # Default
        assert app_config.logging.level == "INFO"  # Default
        assert app_config.providers.telegram is None  # Default
        assert app_config.providers.discord is None  # Default

    def test_configuration_with_all_providers_scenario(self) -> None:
        """Test configuration with all available providers configured."""
        full_provider_config = {
            "process": {
                "name": "backup-sync",
                "path": "/opt/backup/bin/sync",
            },
            "notifications": {
                "enabled_providers": ["telegram", "discord"],
                "events": ["started", "progress", "completed", "failed"],
            },
            "providers": {
                "telegram": {
                    "bot_token": "123456:FULL-CONFIG-TOKEN-abcdef123456",
                    "chat_ids": [-1001234567890, 123456789],
                    "format": {
                        "parse_mode": "MarkdownV2",
                        "disable_web_page_preview": False,
                        "disable_notification": False,
                    },
                    "templates": {
                        "started": "🚀 *Backup Started*\\n\\nProcess: {process_name}",
                        "progress": "📊 *Progress Update*\\n\\nCompleted: {progress}%",
                        "completed": "✅ *Backup Completed*\\n\\nDuration: {duration}",
                        "failed": "❌ *Backup Failed*\\n\\nError: {error}",
                    },
                    "notifications": {
                        "events": ["started", "progress", "completed", "failed"],
                    },
                },
                "discord": {
                    "webhook_url": "https://discord.com/api/webhooks/123456789/full-config-webhook",
                    "embeds": {
                        "enabled": True,
                        "title": "Backup Status Update",
                        "footer": "Backup Monitor v1.0",
                        "timestamp": True,
                        "colors": {
                            "started": 0x00FF00,
                            "progress": 0xFFFF00,
                            "completed": 0x0000FF,
                            "failed": 0xFF0000,
                        },
                    },
                    "notifications": {
                        "events": ["started", "progress", "completed", "failed"],
                        "mentions": {
                            "users": ["123456789", "987654321"],
                            "roles": ["backup-admin", "system-admin"],
                            "everyone": False,
                        },
                    },
                },
            },
        }

        # Validate full provider configuration
        app_config = AppConfig.model_validate(full_provider_config)

        # Verify all providers are properly configured
        assert app_config.notifications.enabled_providers == ["telegram", "discord"]

        # Telegram configuration
        assert app_config.providers.telegram is not None
        assert len(app_config.providers.telegram.chat_ids) == 2
        assert app_config.providers.telegram.format.parse_mode == "MarkdownV2"
        assert "🚀" in app_config.providers.telegram.templates.started

        # Discord configuration
        assert app_config.providers.discord is not None
        assert app_config.providers.discord.embeds.enabled is True
        assert app_config.providers.discord.embeds.colors.started == 0x00FF00
        assert len(app_config.providers.discord.notifications.mentions.users) == 2
        assert "backup-admin" in app_config.providers.discord.notifications.mentions.roles
