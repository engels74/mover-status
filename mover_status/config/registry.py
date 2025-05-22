"""
Configuration registry for the Mover Status Monitor.

This module provides a registry system for managing provider-specific
configuration schemas. It allows providers to register their schemas
dynamically and provides validation capabilities.
"""

from typing import final
from collections.abc import Mapping

from mover_status.config.schema import ConfigSchema, ConfigValue


@final
class RegistryError(Exception):
    """
    Exception raised when registry operations fail.
    
    This exception is raised for various registry-related errors such as
    attempting to register duplicate schemas, accessing non-existent schemas,
    or other registry operation failures.
    """
    pass


@final
class ConfigRegistry:
    """
    Registry for managing provider configuration schemas.
    
    The ConfigRegistry provides a centralized way to register, retrieve,
    and validate provider-specific configuration schemas. It supports
    dynamic provider discovery and schema management.
    """
    
    def __init__(self) -> None:
        """Initialize the configuration registry."""
        self._schemas: dict[str, ConfigSchema] = {}
    
    def register_schema(self, provider_name: str, schema: ConfigSchema) -> None:
        """
        Register a configuration schema for a provider.
        
        Args:
            provider_name: The name of the provider.
            schema: The configuration schema for the provider.
            
        Raises:
            RegistryError: If a schema for the provider is already registered.
        """
        if provider_name in self._schemas:
            raise RegistryError(f"Schema for provider '{provider_name}' is already registered")
        
        self._schemas[provider_name] = schema
    
    def unregister_schema(self, provider_name: str) -> None:
        """
        Unregister a configuration schema for a provider.
        
        Args:
            provider_name: The name of the provider.
            
        Raises:
            RegistryError: If no schema is registered for the provider.
        """
        if provider_name not in self._schemas:
            raise RegistryError(f"Schema for provider '{provider_name}' not found")
        
        del self._schemas[provider_name]
    
    def has_schema(self, provider_name: str) -> bool:
        """
        Check if a schema is registered for a provider.
        
        Args:
            provider_name: The name of the provider.
            
        Returns:
            True if a schema is registered for the provider, False otherwise.
        """
        return provider_name in self._schemas
    
    def get_schema(self, provider_name: str) -> ConfigSchema:
        """
        Get the configuration schema for a provider.
        
        Args:
            provider_name: The name of the provider.
            
        Returns:
            The configuration schema for the provider.
            
        Raises:
            RegistryError: If no schema is registered for the provider.
        """
        if provider_name not in self._schemas:
            raise RegistryError(f"Schema for provider '{provider_name}' not found")
        
        return self._schemas[provider_name]
    
    def get_all_schemas(self) -> dict[str, ConfigSchema]:
        """
        Get all registered configuration schemas.
        
        Returns:
            A dictionary mapping provider names to their configuration schemas.
        """
        return self._schemas.copy()
    
    def get_registered_providers(self) -> list[str]:
        """
        Get a list of all registered provider names.
        
        Returns:
            A list of provider names that have registered schemas.
        """
        return list(self._schemas.keys())
    
    def validate_config(
        self, 
        provider_name: str, 
        config: Mapping[str, ConfigValue]
    ) -> dict[str, ConfigValue]:
        """
        Validate a configuration against a registered schema.
        
        Args:
            provider_name: The name of the provider.
            config: The configuration to validate.
            
        Returns:
            The validated configuration with defaults applied.
            
        Raises:
            RegistryError: If no schema is registered for the provider.
            SchemaValidationError: If the configuration is invalid.
        """
        if provider_name not in self._schemas:
            raise RegistryError(f"Schema for provider '{provider_name}' not found")
        
        schema = self._schemas[provider_name]
        return schema.validate(config)
    
    def clear(self) -> None:
        """
        Clear all registered schemas.
        
        This method removes all registered schemas from the registry.
        """
        self._schemas.clear()
