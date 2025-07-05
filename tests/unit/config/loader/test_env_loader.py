"""Tests for environment variable configuration loader."""

from __future__ import annotations

import os
from unittest.mock import patch
import pytest

from mover_status.config.loader.env_loader import EnvLoader
from mover_status.config.exceptions import EnvLoadError


class TestEnvLoader:
    """Test suite for EnvLoader class."""

    def test_load_simple_env_vars(self) -> None:
        """Test loading simple environment variables."""
        loader = EnvLoader(prefix="TEST_")
        
        test_env = {
            "TEST_KEY1": "value1",
            "TEST_KEY2": "value2",
            "OTHER_KEY": "ignored",
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            result = loader.load()
            
        expected = {
            "key1": "value1",
            "key2": "value2",
        }
        assert result == expected

    def test_load_nested_env_vars_with_underscores(self) -> None:
        """Test loading nested environment variables using underscores."""
        loader = EnvLoader(prefix="APP_")
        
        test_env = {
            "APP_MONITORING_INTERVAL": "60",
            "APP_PROCESS_NAME": "mover",
            "APP_PROVIDERS_DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/123",
            "APP_PROVIDERS_TELEGRAM_BOT_TOKEN": "12345:token",
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            result = loader.load()
            
        # With full underscore-to-dot conversion, this creates nested structure
        expected = {
            "monitoring": {
                "interval": "60",
            },
            "process": {
                "name": "mover",
            },
            "providers": {
                "discord": {
                    "webhook": {
                        "url": "https://discord.com/api/webhooks/123",
                    },
                },
                "telegram": {
                    "bot": {
                        "token": "12345:token",
                    },
                },
            },
        }
        assert result == expected

    def test_load_nested_env_vars_with_dots(self) -> None:
        """Test loading nested environment variables using dots."""
        loader = EnvLoader(prefix="APP_", separator=".")
        
        test_env = {
            "APP_monitoring.interval": "60",
            "APP_process.name": "mover",
            "APP_providers.discord.webhook_url": "https://discord.com/api/webhooks/123",
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            result = loader.load()
            
        expected = {
            "monitoring": {
                "interval": "60",
            },
            "process": {
                "name": "mover",
            },
            "providers": {
                "discord": {
                    "webhook_url": "https://discord.com/api/webhooks/123",
                },
            },
        }
        assert result == expected

    def test_load_with_type_conversion(self) -> None:
        """Test automatic type conversion for environment variables."""
        loader = EnvLoader(prefix="APP_", convert_types=True)
        
        test_env = {
            "APP_MONITORING_INTERVAL": "60",        # int
            "APP_MONITORING_DRY_RUN": "true",       # bool
            "APP_PROGRESS_THRESHOLD": "1.5",       # float
            "APP_PROCESS_NAME": "mover",            # str
            "APP_PROVIDERS_TELEGRAM_CHAT_IDS": "[123, 456]",  # list
            "APP_PROVIDERS_DISCORD_EMBED_COLORS": '{"started": 65280}',  # dict
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            result = loader.load()
            
        expected = {
            "monitoring": {
                "interval": 60,
                "dry": {
                    "run": True,
                },
            },
            "progress": {
                "threshold": 1.5,
            },
            "process": {
                "name": "mover",
            },
            "providers": {
                "telegram": {
                    "chat": {
                        "ids": [123, 456],
                    },
                },
                "discord": {
                    "embed": {
                        "colors": {"started": 65280},
                    },
                },
            },
        }
        assert result == expected

    def test_load_with_custom_mappings(self) -> None:
        """Test loading with custom environment variable mappings."""
        loader = EnvLoader(
            prefix="APP_",
            mappings={
                "DATABASE_URL": "database.url",
                "LOG_LEVEL": "logging.level",
                "NOTIFICATION_WEBHOOK": "providers.discord.webhook_url",
            }
        )
        
        test_env = {
            "DATABASE_URL": "postgresql://localhost/db",
            "LOG_LEVEL": "INFO",
            "NOTIFICATION_WEBHOOK": "https://discord.com/api/webhooks/123",
            "APP_MONITORING_INTERVAL": "30",
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            result = loader.load()
            
        expected = {
            "database": {
                "url": "postgresql://localhost/db",
            },
            "logging": {
                "level": "INFO",
            },
            "providers": {
                "discord": {
                    "webhook_url": "https://discord.com/api/webhooks/123",
                },
            },
            "monitoring": {
                "interval": "30",
            },
        }
        assert result == expected

    def test_load_no_matching_env_vars(self) -> None:
        """Test loading when no environment variables match the prefix."""
        loader = EnvLoader(prefix="NONEXISTENT_")
        
        test_env = {
            "OTHER_KEY": "value",
            "ANOTHER_KEY": "value2",
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            result = loader.load()
            
        assert result == {}

    def test_load_empty_env_vars(self) -> None:
        """Test loading empty environment variables."""
        loader = EnvLoader(prefix="APP_")
        
        test_env = {
            "APP_EMPTY_VALUE": "",
            "APP_VALID_VALUE": "test",
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            result = loader.load()
            
        expected = {
            "empty": {
                "value": "",
            },
            "valid": {
                "value": "test",
            },
        }
        assert result == expected

    def test_load_case_sensitivity(self) -> None:
        """Test that environment variable names are case-sensitive."""
        loader = EnvLoader(prefix="APP_")
        
        test_env = {
            "APP_KEY": "value1",
            "app_key": "value2",
            "App_Key": "value3",
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            result = loader.load()
            
        expected = {
            "key": "value1",
        }
        assert result == expected

    def test_load_override_precedence(self) -> None:
        """Test that custom mappings take precedence over prefix-based loading."""
        loader = EnvLoader(
            prefix="APP_",
            mappings={
                "APP_KEY": "custom.path",
            }
        )
        
        test_env = {
            "APP_KEY": "custom_value",
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            result = loader.load()
            
        expected = {
            "custom": {
                "path": "custom_value",
            },
        }
        assert result == expected

    def test_load_invalid_json_with_conversion(self) -> None:
        """Test that invalid JSON in environment variables raises error when type conversion is enabled."""
        loader = EnvLoader(prefix="APP_", convert_types=True)
        
        test_env = {
            "APP_INVALID_JSON": '[invalid json}',
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            with pytest.raises(EnvLoadError) as exc_info:
                _ = loader.load()
            
            assert "Failed to parse JSON" in str(exc_info.value)
            assert "APP_INVALID_JSON" in str(exc_info.value)

    def test_load_boolean_conversion(self) -> None:
        """Test various boolean value conversions."""
        loader = EnvLoader(prefix="APP_", convert_types=True)
        
        test_env = {
            "APP_TRUE1": "true",
            "APP_TRUE2": "True",
            "APP_TRUE3": "TRUE",
            "APP_TRUE4": "1",
            "APP_TRUE5": "yes",
            "APP_TRUE6": "on",
            "APP_FALSE1": "false",
            "APP_FALSE2": "False", 
            "APP_FALSE3": "FALSE",
            "APP_FALSE4": "0",
            "APP_FALSE5": "no",
            "APP_FALSE6": "off",
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            result = loader.load()
            
        # All true values should be True
        for key in ["true1", "true2", "true3", "true4", "true5", "true6"]:
            assert result[key] is True
            
        # All false values should be False
        for key in ["false1", "false2", "false3", "false4", "false5", "false6"]:
            assert result[key] is False

    def test_load_numeric_conversion(self) -> None:
        """Test numeric value conversions."""
        loader = EnvLoader(prefix="APP_", convert_types=True)
        
        test_env = {
            "APP_INTPOS": "42",
            "APP_INTNEG": "-10",
            "APP_FLOATPOS": "3.14",
            "APP_FLOATNEG": "-2.5",
            "APP_FLOATSCI": "1.5e3",
            "APP_NOTNUMERIC": "not_a_number",
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            result = loader.load()
            
        assert result["intpos"] == 42
        assert result["intneg"] == -10
        assert result["floatpos"] == 3.14
        assert result["floatneg"] == -2.5
        assert result["floatsci"] == 1500.0
        assert result["notnumeric"] == "not_a_number"  # Should remain as string

    def test_load_with_different_prefix(self) -> None:
        """Test loading with different prefixes."""
        loader1 = EnvLoader(prefix="APP1_")
        loader2 = EnvLoader(prefix="APP2_")
        
        test_env = {
            "APP1_KEY": "value1",
            "APP2_KEY": "value2",
            "OTHER_KEY": "ignored",
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            result1 = loader1.load()
            result2 = loader2.load()
            
        assert result1 == {"key": "value1"}
        assert result2 == {"key": "value2"}

    def test_load_deep_nesting(self) -> None:
        """Test loading deeply nested environment variables."""
        loader = EnvLoader(prefix="APP_")
        
        test_env = {
            "APP_LEVEL1_LEVEL2_LEVEL3_LEVEL4_VALUE": "deep_value",
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            result = loader.load()
            
        expected = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "value": "deep_value",
                        },
                    },
                },
            },
        }
        assert result == expected

    def test_load_array_indices(self) -> None:
        """Test loading array-like environment variables."""
        loader = EnvLoader(prefix="APP_")
        
        test_env = {
            "APP_ARRAY_0": "item1",
            "APP_ARRAY_1": "item2", 
            "APP_ARRAY_2": "item3",
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            result = loader.load()
            
        expected = {
            "array": {
                "0": "item1",
                "1": "item2",
                "2": "item3",
            },
        }
        assert result == expected

    def test_load_merge_with_existing_structure(self) -> None:
        """Test that environment variables merge properly with existing nested structures."""
        loader = EnvLoader(prefix="APP_")
        
        test_env = {
            "APP_CONFIG_KEY1": "value1",
            "APP_CONFIG_KEY2": "value2",
            "APP_CONFIG_NESTED_DEEP": "deep_value",
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            result = loader.load()
            
        expected = {
            "config": {
                "key1": "value1",
                "key2": "value2",
                "nested": {
                    "deep": "deep_value",
                },
            },
        }
        assert result == expected

    def test_load_empty_prefix_key(self) -> None:
        """Test that empty config keys after prefix are skipped."""
        loader = EnvLoader(prefix="APP_")
        
        test_env = {
            "APP_": "should_be_ignored",  # Empty key after prefix
            "APP_VALID": "valid_value",
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            result = loader.load()
            
        expected = {
            "valid": "valid_value",
        }
        assert result == expected

    def test_load_custom_mapping_without_type_conversion(self) -> None:
        """Test custom mappings work without type conversion."""
        loader = EnvLoader(
            prefix="APP_",
            convert_types=False,
            mappings={
                "CUSTOM_VAR": "custom.mapping",
            }
        )
        
        test_env = {
            "CUSTOM_VAR": "42",  # Should remain string without conversion
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            result = loader.load()
            
        expected = {
            "custom": {
                "mapping": "42",  # String, not int
            },
        }
        assert result == expected

    def test_load_empty_value_with_type_conversion(self) -> None:
        """Test that empty values are handled correctly with type conversion."""
        loader = EnvLoader(prefix="APP_", convert_types=True)
        
        test_env = {
            "APP_EMPTY": "",
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            result = loader.load()
            
        expected = {
            "empty": "",  # Should remain empty string
        }
        assert result == expected

    def test_load_custom_mapping_with_type_conversion(self) -> None:
        """Test custom mappings work with type conversion."""
        loader = EnvLoader(
            prefix="APP_",
            convert_types=True,
            mappings={
                "CUSTOM_NUMBER": "config.number",
            }
        )
        
        test_env = {
            "CUSTOM_NUMBER": "42",  # Should be converted to int
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            result = loader.load()
            
        expected = {
            "config": {
                "number": 42,  # Should be converted to int
            },
        }
        assert result == expected

    def test_load_override_existing_non_dict_value(self) -> None:
        """Test that non-dict values are overridden when creating nested structures."""
        loader = EnvLoader(prefix="APP_")
        
        # First set a simple value, then try to create a nested structure under it
        test_env = {
            "APP_CONFIG": "simple_value",
            "APP_CONFIG_NESTED": "nested_value",
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            result = loader.load()
            
        # The simple value should be overridden by a dict to allow nesting
        expected = {
            "config": {
                "nested": "nested_value",
            },
        }
        assert result == expected