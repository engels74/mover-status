"""
Configuration validator for the Mover Status Monitor.

This module provides the ConfigValidator class which validates configuration
data against registered schemas in the ConfigRegistry.
"""

from typing import final
from collections.abc import Mapping

from mover_status.config.registry import ConfigRegistry, RegistryError
from mover_status.config.schema import SchemaValidationError, ConfigValue


@final
class ValidationError(Exception):
    """
    Exception raised when configuration validation fails.

    This exception includes information about the validation errors,
    such as missing required fields, incorrect field types, or invalid values.
    """

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        """
        Initialize the ValidationError.

        Args:
            message: The error message.
            errors: Optional list of specific validation errors.
        """
        self.errors: list[str] = errors or []
        error_details = "\n - " + "\n - ".join(self.errors) if self.errors else ""
        super().__init__(f"{message}{error_details}")


@final
class ConfigValidator:
    """
    Validates configuration data against registered schemas.

    This class provides configuration validation functionality by working with
    the ConfigRegistry to validate provider configurations against their
    registered schemas.
    """

    def __init__(self, registry: ConfigRegistry) -> None:
        """
        Initialize the ConfigValidator.

        Args:
            registry: The ConfigRegistry containing registered schemas.
        """
        self.registry = registry

    def validate(self, config: Mapping[str, object]) -> dict[str, dict[str, ConfigValue]]:
        """
        Validate a configuration against registered schemas.

        This method validates each provider configuration section against its
        registered schema. It supports dynamic validation based on the providers
        that are currently registered in the registry.

        Args:
            config: The configuration to validate. Should be a mapping where
                   keys are provider names and values are provider configurations.

        Returns:
            The validated configuration with defaults applied. Each provider
            configuration is validated and defaults are applied according to
            the registered schema.

        Raises:
            ValidationError: If the configuration is invalid. This includes
                           cases where a provider is not registered or where
                           the provider configuration fails schema validation.
        """
        validated_config: dict[str, dict[str, ConfigValue]] = {}
        validation_errors: list[str] = []

        # Validate each provider configuration
        for provider_name, provider_config in config.items():
            try:
                # Check if the provider has a registered schema
                if not self.registry.has_schema(provider_name):
                    validation_errors.append(
                        f"No schema registered for provider '{provider_name}'"
                    )
                    continue

                # Validate the provider configuration
                if not isinstance(provider_config, Mapping):
                    validation_errors.append(
                        f"Configuration for provider '{provider_name}' must be a mapping, "
                        + f"got {type(provider_config).__name__}"
                    )
                    continue

                # Cast to the expected type for validation
                # We know provider_config is a Mapping at this point
                provider_config_dict: dict[str, ConfigValue] = {}
                for key, value in provider_config.items():  # pyright: ignore[reportUnknownVariableType]
                    provider_config_dict[str(key)] = value  # pyright: ignore[reportUnknownArgumentType]

                validated_provider_config = self.registry.validate_config(
                    provider_name, provider_config_dict
                )
                validated_config[provider_name] = validated_provider_config

            except RegistryError as e:
                validation_errors.append(f"Registry error for provider '{provider_name}': {e}")
            except SchemaValidationError as e:
                # Extract detailed error information
                provider_errors = [f"Provider '{provider_name}': {error}" for error in e.errors]
                validation_errors.extend(provider_errors)
            except Exception as e:
                validation_errors.append(
                    f"Unexpected error validating provider '{provider_name}': {e}"
                )

        # If there are validation errors, raise a ValidationError
        if validation_errors:
            raise ValidationError("Configuration validation failed", validation_errors)

        return validated_config

    def validate_provider(
        self,
        provider_name: str,
        config: Mapping[str, ConfigValue]
    ) -> dict[str, ConfigValue]:
        """
        Validate a single provider configuration against its schema.

        Args:
            provider_name: The name of the provider.
            config: The provider configuration to validate.

        Returns:
            The validated configuration with defaults applied.

        Raises:
            ValidationError: If the provider configuration is invalid.
        """
        try:
            if not self.registry.has_schema(provider_name):
                raise ValidationError(f"No schema registered for provider '{provider_name}'")

            return self.registry.validate_config(provider_name, config)

        except RegistryError as e:
            raise ValidationError(f"Registry error for provider '{provider_name}': {e}")
        except SchemaValidationError as e:
            raise ValidationError(
                f"Schema validation failed for provider '{provider_name}'",
                e.errors
            )

    def get_registered_providers(self) -> list[str]:
        """
        Get a list of all registered provider names.

        Returns:
            A list of provider names that have registered schemas.
        """
        return self.registry.get_registered_providers()

    def has_provider_schema(self, provider_name: str) -> bool:
        """
        Check if a provider has a registered schema.

        Args:
            provider_name: The name of the provider to check.

        Returns:
            True if the provider has a registered schema, False otherwise.
        """
        return self.registry.has_schema(provider_name)
