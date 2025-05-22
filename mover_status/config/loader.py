"""
Configuration loader for the Mover Status Monitor.

This module provides the ConfigLoader class which handles loading configuration
from YAML files, merging with defaults, and validating against registered schemas.
"""

import os
from typing import final, cast
from collections.abc import Mapping

import yaml

from mover_status.config.registry import ConfigRegistry, RegistryError
from mover_status.config.schema import SchemaValidationError, ConfigValue


@final
class LoaderError(Exception):
    """
    Exception raised when configuration loading fails.

    This exception includes information about the loading errors,
    such as file not found, invalid YAML, validation failures, or other issues.
    """

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        """
        Initialize the LoaderError.

        Args:
            message: The error message.
            errors: Optional list of specific loading errors.
        """
        self.errors: list[str] = errors or []
        error_details = "\n - " + "\n - ".join(self.errors) if self.errors else ""
        super().__init__(f"{message}{error_details}")


@final
class ConfigLoader:
    """
    Configuration loader for loading and validating configuration files.

    The ConfigLoader handles loading configuration from YAML files,
    merging with defaults from registered schemas, and validating
    the final configuration against provider schemas.
    """

    def __init__(self, registry: ConfigRegistry) -> None:
        """
        Initialize the configuration loader.

        Args:
            registry: The configuration registry containing provider schemas.
        """
        self.registry = registry

    def load_from_file(self, file_path: str) -> dict[str, dict[str, ConfigValue]]:
        """
        Load configuration from a YAML file.

        Args:
            file_path: Path to the configuration file.

        Returns:
            The loaded and validated configuration.

        Raises:
            LoaderError: If the file cannot be loaded or configuration is invalid.
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                # Return empty configuration for missing files
                return {}

            # Load the YAML file
            with open(file_path, "r") as f:
                # yaml.safe_load inherently returns Any since YAML can contain any data type
                raw_config: object = yaml.safe_load(f)  # pyright: ignore[reportAny]

            # Handle empty or None content
            if raw_config is None:
                return {}

            # Ensure we have a dictionary
            if not isinstance(raw_config, dict):
                # Type narrowing: after isinstance check, raw_config is known to not be dict
                raw_config_type_name = type(raw_config).__name__
                raise LoaderError(f"Configuration file must contain a dictionary, got {raw_config_type_name}")

            # Cast to proper type and load/validate the configuration
            typed_config = cast(Mapping[str, object], raw_config)
            return self._load_and_validate(typed_config)

        except yaml.YAMLError as e:
            raise LoaderError(f"Invalid YAML in configuration file: {e}")
        except OSError as e:
            raise LoaderError(f"Error reading configuration file: {e}")

    def load_from_string(self, yaml_content: str) -> dict[str, dict[str, ConfigValue]]:
        """
        Load configuration from a YAML string.

        Args:
            yaml_content: YAML content as a string.

        Returns:
            The loaded and validated configuration.

        Raises:
            LoaderError: If the YAML is invalid or configuration fails validation.
        """
        try:
            # Parse the YAML content
            # yaml.safe_load inherently returns Any since YAML can contain any data type
            raw_config: object = yaml.safe_load(yaml_content)  # pyright: ignore[reportAny]

            # Handle empty or None content
            if raw_config is None:
                return {}

            # Ensure we have a dictionary
            if not isinstance(raw_config, dict):
                # Type narrowing: after isinstance check, raw_config is known to not be dict
                raw_config_type_name = type(raw_config).__name__
                raise LoaderError(f"Configuration must be a dictionary, got {raw_config_type_name}")

            # Cast to proper type and load/validate the configuration
            typed_config = cast(Mapping[str, object], raw_config)
            return self._load_and_validate(typed_config)

        except yaml.YAMLError as e:
            raise LoaderError(f"Invalid YAML content: {e}")

    def merge_with_defaults(self, user_config: Mapping[str, object]) -> dict[str, dict[str, ConfigValue]]:
        """
        Merge user configuration with defaults from registered schemas.

        Args:
            user_config: The user configuration to merge.

        Returns:
            The merged and validated configuration.

        Raises:
            LoaderError: If configuration validation fails.
        """
        return self._load_and_validate(user_config)

    def _load_and_validate(self, raw_config: Mapping[str, object]) -> dict[str, dict[str, ConfigValue]]:
        """
        Load and validate configuration against registered schemas.

        Args:
            raw_config: The raw configuration dictionary.

        Returns:
            The validated configuration with defaults applied.

        Raises:
            LoaderError: If configuration validation fails.
        """
        validated_config: dict[str, dict[str, ConfigValue]] = {}
        validation_errors: list[str] = []

        # Get all registered schemas
        all_schemas = self.registry.get_all_schemas()

        # Process each provider that has a registered schema
        for provider_name, _schema in all_schemas.items():
            try:
                # Get the provider configuration from raw config
                provider_config = raw_config.get(provider_name, {})

                # Ensure provider config is a dictionary
                if not isinstance(provider_config, dict):
                    error_msg = (
                        f"Configuration for provider '{provider_name}' must be a dictionary, "
                        f"got {type(provider_config).__name__}"
                    )
                    validation_errors.append(error_msg)
                    continue

                # Validate and merge with defaults
                validated_provider_config = self.registry.validate_config(
                    provider_name,
                    provider_config  # pyright: ignore[reportUnknownArgumentType]
                )
                validated_config[provider_name] = validated_provider_config

            except (RegistryError, SchemaValidationError) as e:
                validation_errors.append(f"Provider '{provider_name}': {e}")

        # If there were validation errors, raise an exception
        if validation_errors:
            raise LoaderError(
                f"Configuration validation failed",
                validation_errors
            )

        return validated_config
