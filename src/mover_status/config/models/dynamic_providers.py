"""Dynamic provider configuration models that support any provider."""

from __future__ import annotations

from typing import cast
from pydantic import Field, field_validator, ConfigDict, ValidationInfo

from .base import BaseConfig


class DynamicProviderConfig(BaseConfig):
    """Dynamic provider configuration that can hold any provider's config."""
    
    model_config: ConfigDict = ConfigDict(extra='allow')  # Allow additional fields
    
    enabled: bool = Field(
        default=True,
        description="Whether this provider is enabled"
    )
    
    # All other fields are dynamic and will be validated by the provider itself
    
    def __init__(self, **data: object) -> None:
        """Initialize with any additional fields."""
        super().__init__(**data)  # pyright: ignore[reportArgumentType] # pydantic base allows arbitrary kwargs
    
    def get_provider_config(self, provider_name: str) -> dict[str, object]: 
        """Get configuration for a specific provider.
        
        Args:
            provider_name: Name of the provider
            
        Returns:
            Configuration dictionary for the provider
        """
        _ = provider_name  # Parameter not used but required for interface compatibility
        # Return all fields as configuration
        return self.model_dump()


class FlexibleProviderConfig(BaseConfig):
    """Flexible provider configuration container that supports any provider."""
    
    model_config: ConfigDict = ConfigDict(extra='allow')  # Allow any additional provider configs
    
    def __init__(self, **data: object) -> None:
        """Initialize with dynamic provider configurations."""
        super().__init__(**data)  # pyright: ignore[reportArgumentType] # pydantic base allows arbitrary kwargs
    
    def get_provider_config(self, provider_name: str) -> dict[str, object] | None:
        """Get configuration for a specific provider.
        
        Args:
            provider_name: Name of the provider
            
        Returns:
            Configuration dictionary for the provider, or None if not found
        """
        provider_config = getattr(self, provider_name, None)
        
        if provider_config is not None:
            if hasattr(provider_config, 'model_dump'):  # pyright: ignore[reportAny] # dynamic attribute check
                return cast(dict[str, object], provider_config.model_dump())  # pyright: ignore[reportAny] # dynamic method call
            elif hasattr(provider_config, 'dict'):  # pyright: ignore[reportAny] # dynamic attribute check
                return cast(dict[str, object], provider_config.dict())  # pyright: ignore[reportAny] # dynamic method call
            elif isinstance(provider_config, dict):
                return cast(dict[str, object], provider_config)
            else:
                # Try to convert to dict
                try:
                    return dict(provider_config) if provider_config else None  # pyright: ignore[reportAny] # dynamic conversion
                except (TypeError, ValueError):
                    return None
        
        return None
    
    def has_provider_config(self, provider_name: str) -> bool:
        """Check if configuration exists for a provider.
        
        Args:
            provider_name: Name of the provider
            
        Returns:
            True if configuration exists, False otherwise
        """
        return hasattr(self, provider_name) and getattr(self, provider_name) is not None
    
    def list_configured_providers(self) -> list[str]:
        """List all providers that have configurations.
        
        Returns:
            List of provider names with configurations
        """
        # Get all attributes that don't start with underscore and aren't methods
        providers: list[str] = []
        for attr_name in dir(self):
            if not attr_name.startswith('_') and not callable(getattr(self, attr_name)):  # pyright: ignore[reportAny] # dynamic attribute check
                attr_value = getattr(self, attr_name)  # pyright: ignore[reportAny] # dynamic attribute access
                if attr_value is not None:
                    providers.append(attr_name)
        
        return providers
    
    def add_provider_config(self, provider_name: str, config: dict[str, object] | DynamicProviderConfig) -> None:
        """Add configuration for a new provider dynamically.
        
        Args:
            provider_name: Name of the provider
            config: Configuration for the provider
        """
        if isinstance(config, dict):
            config_obj = DynamicProviderConfig(**config)
        else:
            config_obj = config
            
        setattr(self, provider_name, config_obj)
    
    @field_validator('*', mode='before')
    @classmethod
    def validate_provider_configs(cls, v: object, info: ValidationInfo) -> object | DynamicProviderConfig:
        """Validate provider configurations dynamically."""
        # If it's a dict, convert to DynamicProviderConfig
        if isinstance(v, dict) and hasattr(info, 'field_name') and info.field_name and not info.field_name.startswith('_'):
            return DynamicProviderConfig(**v)  # pyright: ignore[reportUnknownArgumentType] # dynamic dict conversion
        return v  # pyright: ignore[reportUnknownVariableType] # return value could be various types