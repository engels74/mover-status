"""
Configuration manager for the Mover Status Monitor.

This module provides the ConfigManager class, which is responsible for loading,
validating, and saving configuration data for the application. It standardizes
on YAML as the configuration format and provides a clean interface for accessing
configuration values throughout the application.
"""

# pyright: reportUnnecessaryIsInstance=false
# The above directive is necessary because this module performs runtime type validation
# of user-provided configuration data, which requires isinstance checks even when
# the static type system can determine the types.

import os
from collections.abc import Mapping
import yaml
from typing import cast

from mover_status.config.models import MoverStatusConfig
from mover_status.config.types import TelegramConfig, DiscordConfig
from mover_status.config.default_config import DEFAULT_CONFIG
from mover_status.notification.providers.telegram.defaults import TELEGRAM_DEFAULTS
from mover_status.notification.providers.discord.defaults import DISCORD_DEFAULTS
from mover_status.config.manager_validation import ConfigManagerValidationMixin


class ConfigManager(ConfigManagerValidationMixin):
    """
    Manages configuration loading, validation, and saving for the Mover Status Monitor.

    This class handles:
    - Loading configuration from YAML files
    - Merging with default configuration values
    - Validating configuration structure and values
    - Saving configuration to YAML files
    - Providing access to configuration values
    """

    def __init__(self, config_path: str | None = None) -> None:
        """
        Initialize the ConfigManager.

        Args:
            config_path: Optional path to a configuration file. If not provided,
                         will use default configuration values.
        """
        self.config_path: str | None = config_path
        self.config: MoverStatusConfig = self.get_default_config()

    @staticmethod
    def get_default_config() -> MoverStatusConfig:
        """
        Get the default configuration by merging core defaults with provider defaults.

        Returns:
            The default configuration dictionary.
        """
        # Start with a mutable copy of the core default config
        default_config: dict[str, object] = {}

        # Copy core configuration sections
        for section_name, section_data in DEFAULT_CONFIG.items():
            # Convert TypedDict to regular dict
            default_config[section_name] = dict(cast(dict[str, object], section_data))

        # Ensure notification section has providers
        notification_section = cast(dict[str, object], default_config["notification"])
        notification_section["providers"] = {}

        # Add Telegram provider defaults
        # Create a properly typed dictionary for Telegram defaults
        telegram_defaults: TelegramConfig = {
            "bot_token": TELEGRAM_DEFAULTS["bot_token"],
            "chat_id": TELEGRAM_DEFAULTS["chat_id"],
            "message_template": TELEGRAM_DEFAULTS["message_template"],
            "parse_mode": TELEGRAM_DEFAULTS["parse_mode"],
            "disable_notification": TELEGRAM_DEFAULTS["disable_notification"],
            "enabled": False  # Default to disabled
        }

        # Add to the config
        providers_section = cast(dict[str, object], notification_section["providers"])
        providers_section["telegram"] = telegram_defaults

        # Add Discord provider defaults
        # Create a properly typed dictionary for Discord defaults
        # Convert the embed_colors dictionary to the expected format
        embed_colors: dict[str, int] = {}
        for color_key, color_value in DISCORD_DEFAULTS["embed_colors"].items():
            if isinstance(color_key, str) and isinstance(color_value, int):
                embed_colors[color_key] = color_value

        discord_defaults: DiscordConfig = {
            "webhook_url": DISCORD_DEFAULTS["webhook_url"],
            "username": DISCORD_DEFAULTS["username"],
            "message_template": DISCORD_DEFAULTS["message_template"],
            "use_embeds": DISCORD_DEFAULTS["use_embeds"],
            "embed_title": DISCORD_DEFAULTS["embed_title"],
            "embed_colors": embed_colors,
            "enabled": False  # Default to disabled
        }

        # Add to the config
        providers_section["discord"] = discord_defaults

        # Convert the dictionary to a MoverStatusConfig object
        return MoverStatusConfig.from_dict(default_config)

    def load(self, config_path: str | None = None) -> MoverStatusConfig:
        """
        Load configuration from a YAML file and merge with defaults.

        Args:
            config_path: Path to the configuration file. If not provided,
                         will use the path provided during initialization.

        Returns:
            The merged configuration dictionary.

        Raises:
            ValueError: If the configuration file is invalid.
            ValidationError: If the configuration fails validation.
        """
        # Use the provided path or fall back to the instance path
        path = config_path or self.config_path

        # If no path is provided, just use the default config
        if path is None:
            self.config = self.get_default_config()
            # Validate the default configuration
            self.validate_config()
            return self.config

        # Check if the file exists
        if not os.path.exists(path):
            # If the file doesn't exist, use the default config
            self.config = self.get_default_config()
            # Validate the default configuration
            self.validate_config()
            return self.config

        try:
            # Load the YAML file
            with open(path, "r") as f:
                # yaml.safe_load returns Any, but we know it's a dictionary or None
                user_config_raw = yaml.safe_load(f)  # pyright: ignore[reportAny]

            # If the file is empty or not a dictionary, use the default config
            if user_config_raw is None or not isinstance(user_config_raw, dict):
                self.config = self.get_default_config()
                # Validate the default configuration
                self.validate_config()
                return self.config

            # Convert to a properly typed dictionary
            user_config = cast(Mapping[str, object], user_config_raw)

            # Merge with defaults
            self.config = self.merge_with_defaults(user_config)

            # Validate the merged configuration
            self.validate_config()

            return self.config

        except yaml.YAMLError as e:
            # If the YAML is invalid, raise a ValueError
            raise ValueError(f"Invalid YAML in configuration file: {e}")

    def merge_with_defaults(self, user_config: Mapping[str, object]) -> MoverStatusConfig:
        """
        Merge user configuration with default configuration.

        Args:
            user_config: The user configuration dictionary.

        Returns:
            The merged configuration dictionary.
        """
        # Start with a deep copy of the default config
        default_config = dict(self.get_default_config().to_dict())

        # Recursively merge the user config into the default config
        self._merge_dicts(default_config, user_config)

        # Convert the merged dictionary to a MoverStatusConfig object
        return MoverStatusConfig.from_dict(default_config)

    def _merge_dicts(self, target: dict[str, object], source: Mapping[str, object]) -> None:
        """
        Recursively merge source dictionary into target dictionary.

        Args:
            target: The target dictionary to merge into.
            source: The source dictionary to merge from.
        """
        for key, value in source.items():
            # If the value is a dictionary and the key exists in the target
            # and the target value is also a dictionary, recursively merge
            if (
                isinstance(value, dict)
                and key in target
                and isinstance(target[key], dict)
            ):
                self._merge_dicts(cast(dict[str, object], target[key]), cast(Mapping[str, object], value))
            else:
                # Otherwise, just overwrite the value
                target[key] = value

    def save(self, config_path: str | None = None) -> None:
        """
        Save the current configuration to a YAML file.

        Args:
            config_path: Path to save the configuration file. If not provided,
                         will use the path provided during initialization.

        Raises:
            ValueError: If no path is provided and no path was provided during initialization.
            PermissionError: If the file cannot be written due to permissions.
            IOError: If there is an error writing the file.
        """
        # Use the provided path or fall back to the instance path
        path = config_path or self.config_path

        # If no path is provided, raise an error
        if path is None:
            raise ValueError("No configuration path provided")

        # Save the configuration to the file
        with open(path, "w") as f:
            yaml.dump(self.config.to_dict(), f, default_flow_style=False)

    def get(self, key: str | None, default: object = None) -> object:
        """
        Get a configuration value by key.

        Args:
            key: The configuration key to get. Can use dot notation for nested keys.
            default: The default value to return if the key does not exist.

        Returns:
            The configuration value, or the default if the key does not exist.
            The return type depends on the key path:
            - For paths ending with ".enabled_providers": list[str]
            - For paths ending with ".telegram" or ".discord": dict[str, object]
            - For other paths: str, int, bool, list, dict, or None
        """
        # If the key is None or empty, return the default
        if key is None or key == "":
            return default

        try:
            # Use the get_nested_value method from MoverStatusConfig
            return self.config.get_nested_value(key)
        except KeyError:
            # If the key doesn't exist, return the default
            return default
