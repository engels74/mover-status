"""
Tests for the configuration manager module.
"""

# pyright: reportGeneralTypeIssues=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# This directive is necessary because the tests access TypedDict fields in a way
# that is valid at runtime but that the static type checker cannot verify.
# We also disable unknown variable and argument type reporting for test data.

import os
import yaml
import pytest

from mover_status.config.config_manager import MoverStatusConfig

# Import the modules to test
from mover_status.config.default_config import DEFAULT_CONFIG
from mover_status.notification.providers.telegram.defaults import TELEGRAM_DEFAULTS
from mover_status.notification.providers.discord.defaults import DISCORD_DEFAULTS

# This will be implemented
from mover_status.config.config_manager import ConfigManager
from mover_status.config.validation_error import ValidationError


class TestConfigManager:
    """Test cases for the configuration manager."""

    def test_init_with_default_path(self) -> None:
        """Test that the ConfigManager can be initialized with a default path."""
        config_manager = ConfigManager()
        assert config_manager.config_path is None
        assert isinstance(config_manager.config, MoverStatusConfig)
        # Default config should be loaded
        # We can't directly compare the objects, so we compare their dictionaries
        assert config_manager.config.to_dict() == ConfigManager.get_default_config().to_dict()

    def test_init_with_custom_path(self, temp_file: str) -> None:
        """Test that the ConfigManager can be initialized with a custom path."""
        config_manager = ConfigManager(config_path=temp_file)
        assert config_manager.config_path == temp_file
        assert isinstance(config_manager.config, MoverStatusConfig)

    def test_get_default_config(self) -> None:
        """Test that the default configuration is correctly assembled."""
        default_config = ConfigManager.get_default_config()

        # Check that the default config is a dictionary
        assert isinstance(default_config, MoverStatusConfig)

        # Check that the core default config is included
        for key in DEFAULT_CONFIG:
            assert key in default_config

        # Check that provider defaults are included in notification section
        assert "providers" in default_config["notification"]
        assert "telegram" in default_config["notification"]["providers"]
        assert "discord" in default_config["notification"]["providers"]

        # Check that provider defaults are correctly merged
        for key, value in TELEGRAM_DEFAULTS.items():
            if key != "name" and key != "enabled":  # These are handled differently
                assert default_config["notification"]["providers"]["telegram"][key] == value

        for key, value in DISCORD_DEFAULTS.items():
            if key != "name" and key != "enabled":  # These are handled differently
                assert default_config["notification"]["providers"]["discord"][key] == value

    def test_load_from_yaml_file(self, temp_dir: str) -> None:
        """Test loading configuration from a YAML file."""
        # Create a test YAML file
        config_path = os.path.join(temp_dir, "config.yaml")
        test_config = {
            "notification": {
                "notification_increment": 10,
                "providers": {
                    "telegram": {
                        "enabled": True,
                        "bot_token": "test_token",
                        "chat_id": "test_chat_id"
                    }
                }
            },
            "monitoring": {
                "poll_interval": 5
            }
        }

        with open(config_path, "w") as f:
            yaml.dump(test_config, f)

        # Load the configuration
        config_manager = ConfigManager(config_path=config_path)
        _ = config_manager.load()

        # Check that the configuration was loaded correctly
        assert config_manager.config["notification"]["notification_increment"] == 10
        assert config_manager.config["notification"]["providers"]["telegram"]["enabled"] is True
        assert config_manager.config["notification"]["providers"]["telegram"]["bot_token"] == "test_token"
        assert config_manager.config["notification"]["providers"]["telegram"]["chat_id"] == "test_chat_id"
        assert config_manager.config["monitoring"]["poll_interval"] == 5

        # Check that default values are still present for keys not in the file
        assert "debug" in config_manager.config
        assert "messages" in config_manager.config

    def test_merge_with_defaults(self) -> None:
        """Test merging user configuration with defaults."""
        # Create a test configuration
        user_config = {
            "notification": {
                "notification_increment": 10,
                "providers": {
                    "telegram": {
                        "enabled": True,
                        "bot_token": "test_token"
                    }
                }
            }
        }

        # Create a ConfigManager and merge with defaults
        config_manager = ConfigManager()
        merged_config = config_manager.merge_with_defaults(user_config)

        # Check that user values override defaults
        assert merged_config["notification"]["notification_increment"] == 10
        assert merged_config["notification"]["providers"]["telegram"]["enabled"] is True
        assert merged_config["notification"]["providers"]["telegram"]["bot_token"] == "test_token"

        # Check that default values are still present for keys not in user config
        assert "monitoring" in merged_config
        assert "debug" in merged_config
        assert "messages" in merged_config

        # Check that nested default values are preserved
        assert "chat_id" in merged_config["notification"]["providers"]["telegram"]
        assert "discord" in merged_config["notification"]["providers"]

    def test_handle_missing_file(self) -> None:
        """Test handling a missing configuration file."""
        # Create a ConfigManager with a non-existent file
        config_manager = ConfigManager(config_path="non_existent_file.yaml")

        # Load should not raise an exception but use defaults
        _ = config_manager.load()

        # Check that the default configuration was loaded
        # We can't directly compare the objects, so we compare their dictionaries
        assert config_manager.config.to_dict() == ConfigManager.get_default_config().to_dict()

    def test_handle_invalid_yaml(self, temp_file: str) -> None:
        """Test handling an invalid YAML file."""
        # Create an invalid YAML file
        with open(temp_file, "w") as f:
            _ = f.write("invalid: yaml: content: - [")

        # Create a ConfigManager with the invalid file
        config_manager = ConfigManager(config_path=temp_file)

        # Load should raise a ValueError
        with pytest.raises(ValueError):
            _ = config_manager.load()

    def test_get_config_value(self, temp_dir: str) -> None:
        """Test getting a configuration value by key."""
        # Create a test YAML file
        config_path = os.path.join(temp_dir, "config.yaml")
        test_config = {
            "notification": {
                "notification_increment": 10,
                "providers": {
                    "telegram": {
                        "enabled": True,
                        "bot_token": "test_token",
                        "chat_id": "test_chat_id"
                    }
                }
            }
        }

        with open(config_path, "w") as f:
            yaml.dump(test_config, f)

        # Load the configuration
        config_manager = ConfigManager(config_path=config_path)
        _ = config_manager.load()

        # Test getting values with dot notation
        assert config_manager.get("notification.notification_increment") == 10
        assert config_manager.get("notification.providers.telegram.enabled") is True
        assert config_manager.get("notification.providers.telegram.bot_token") == "test_token"

        # Test getting a non-existent value
        assert config_manager.get("non.existent.key") is None
        assert config_manager.get("non.existent.key", "default") == "default"

        # Test getting a value with an invalid key
        assert config_manager.get("") is None
        assert config_manager.get(None) is None

    def test_save_config(self, temp_dir: str) -> None:
        """Test saving configuration to a YAML file."""
        # Create a ConfigManager with a test configuration
        config_path = os.path.join(temp_dir, "config.yaml")
        config_manager = ConfigManager(config_path=config_path)

        # Create a modified configuration
        config_dict = config_manager.config.to_dict()
        config_dict["notification"]["notification_increment"] = 10
        config_dict["notification"]["providers"]["telegram"]["enabled"] = True
        config_dict["notification"]["providers"]["telegram"]["bot_token"] = "test_token"

        # Update the configuration
        config_manager.config = MoverStatusConfig.from_dict(config_dict)

        # Save the configuration
        config_manager.save()

        # Check that the file was created
        assert os.path.exists(config_path)

        # Load the configuration from the file
        with open(config_path, "r") as f:
            saved_config = yaml.safe_load(f)

        # Check that the saved configuration matches the expected values
        assert saved_config["notification"]["notification_increment"] == 10
        assert saved_config["notification"]["providers"]["telegram"]["enabled"] is True
        assert saved_config["notification"]["providers"]["telegram"]["bot_token"] == "test_token"

    def test_validate_required_fields(self, temp_dir: str) -> None:
        """Test validation of required fields in the configuration."""
        # Create a ConfigManager with a test configuration
        config_path = os.path.join(temp_dir, "config.yaml")
        config_manager = ConfigManager(config_path=config_path)

        # Create a configuration with missing required fields
        invalid_config = {
            "notification": {
                # Missing notification_increment
                "providers": {
                    "telegram": {
                        "enabled": True,
                        # Missing bot_token
                        "chat_id": "test_chat_id"
                    }
                }
            },
            # Missing monitoring section
        }

        # Set the invalid configuration
        config_manager.config = MoverStatusConfig.from_dict(invalid_config)

        # Validation should raise a ValidationError
        with pytest.raises(ValidationError) as excinfo:
            config_manager.validate_config()

        # Check that the error message contains information about the missing fields
        error_message = str(excinfo.value)
        assert "notification.notification_increment" in error_message
        assert "notification.providers.telegram.bot_token" in error_message
        assert "monitoring" in error_message

    def test_validate_field_types(self, temp_dir: str) -> None:
        """Test validation of field types in the configuration."""
        # Create a ConfigManager with a test configuration
        config_path = os.path.join(temp_dir, "config.yaml")
        config_manager = ConfigManager(config_path=config_path)

        # Create a configuration with incorrect field types
        invalid_config = {
            "notification": {
                "notification_increment": "25",  # Should be an integer
                "enabled_providers": "telegram",  # Should be a list
                "providers": {
                    "telegram": {
                        "enabled": "true",  # Should be a boolean
                        "bot_token": 12345,  # Should be a string
                        "chat_id": "test_chat_id"
                    }
                }
            },
            "monitoring": {
                "poll_interval": "1",  # Should be an integer
                "mover_executable": 12345,  # Should be a string
                "cache_directory": "/mnt/cache"
            }
        }

        # Set the invalid configuration
        config_manager.config = MoverStatusConfig.from_dict(invalid_config)

        # Validation should raise a ValidationError
        with pytest.raises(ValidationError) as excinfo:
            config_manager.validate_config()

        # Check that the error message contains information about the incorrect types
        error_message = str(excinfo.value)
        assert "notification.notification_increment" in error_message
        assert "integer" in error_message
        assert "notification.enabled_providers" in error_message
        assert "list" in error_message
        assert "notification.providers.telegram.enabled" in error_message
        assert "boolean" in error_message
        assert "notification.providers.telegram.bot_token" in error_message
        assert "string" in error_message
        assert "monitoring.poll_interval" in error_message
        assert "integer" in error_message
        assert "monitoring.mover_executable" in error_message
        assert "string" in error_message

    def test_validate_invalid_values(self, temp_dir: str) -> None:
        """Test validation of invalid values in the configuration."""
        # Create a ConfigManager with a test configuration
        config_path = os.path.join(temp_dir, "config.yaml")
        config_manager = ConfigManager(config_path=config_path)

        # Create a configuration with invalid values
        invalid_config = {
            "notification": {
                "notification_increment": -10,  # Should be positive
                "enabled_providers": ["invalid_provider"],  # Should be a valid provider
                "providers": {
                    "telegram": {
                        "enabled": True,
                        "bot_token": "",  # Should not be empty when enabled
                        "chat_id": ""  # Should not be empty when enabled
                    }
                }
            },
            "monitoring": {
                "poll_interval": 0,  # Should be positive
                "mover_executable": "invalid_path",  # Should be an absolute path
                "cache_directory": "invalid_path"  # Should be an absolute path
            }
        }

        # Set the invalid configuration
        config_manager.config = MoverStatusConfig.from_dict(invalid_config)

        # Validation should raise a ValidationError
        with pytest.raises(ValidationError) as excinfo:
            config_manager.validate_config()

        # Check that the error message contains information about the invalid values
        error_message = str(excinfo.value)
        assert "notification.notification_increment" in error_message
        assert "positive" in error_message
        assert "notification.enabled_providers" in error_message
        assert "invalid_provider" in error_message
        assert "notification.providers.telegram.bot_token" in error_message
        assert "empty" in error_message
        assert "notification.providers.telegram.chat_id" in error_message
        assert "empty" in error_message
        assert "monitoring.poll_interval" in error_message
        assert "positive" in error_message
        assert "monitoring.mover_executable" in error_message
        assert "absolute path" in error_message
        assert "monitoring.cache_directory" in error_message
        assert "absolute path" in error_message

    def test_validate_valid_config(self, temp_dir: str) -> None:
        """Test validation of a valid configuration."""
        # Create a ConfigManager with a test configuration
        config_path = os.path.join(temp_dir, "config.yaml")
        config_manager = ConfigManager(config_path=config_path)

        # Create a valid configuration
        valid_config = {
            "notification": {
                "notification_increment": 25,
                "enabled_providers": ["telegram"],
                "providers": {
                    "telegram": {
                        "enabled": True,
                        "bot_token": "test_token",
                        "chat_id": "test_chat_id"
                    }
                }
            },
            "monitoring": {
                "poll_interval": 1,
                "mover_executable": "/usr/local/sbin/mover",
                "cache_directory": "/mnt/cache"
            },
            "messages": {
                "completion": "Moving has been completed!"
            },
            "paths": {
                "exclude": []
            },
            "debug": {
                "dry_run": False,
                "enable_debug": True
            }
        }

        # Set the valid configuration
        config_manager.config = MoverStatusConfig.from_dict(valid_config)

        # Validation should not raise an exception
        config_manager.validate_config()

        # Test that validation is called during load
        with open(config_path, "w") as f:
            yaml.dump(valid_config, f)

        # Load should not raise an exception
        _ = config_manager.load()
