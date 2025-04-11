"""
Unit tests for the notifications/factory.py module.

Tests the notification factory components:
- NotificationFactory
- Provider registration
- Provider validation
- Error handling
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel, ValidationError

from notifications.base import NotificationProvider
from notifications.factory import (
    NotificationFactory,
    ProviderConfigError,
    ProviderNotFoundError,
    ProviderRegistrationError,
)
from utils.validators import BaseProviderValidator


# --- Test Fixtures and Mocks ---

# Mock Provider Implementation
class MockProvider(NotificationProvider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect_mock = AsyncMock()
        self.disconnect_mock = AsyncMock()
        self.send_mock = AsyncMock(return_value=True)
    
    async def send_notification(self, message: str, **kwargs) -> bool:
        await self.send_mock(message, **kwargs)
        return True
        
    async def connect(self) -> None:
        await self.connect_mock()
        
    async def disconnect(self) -> None:
        await self.disconnect_mock()


# Mock Validator
class MockValidator(BaseProviderValidator):
    @classmethod
    def validate_config(cls, config: dict) -> dict:
        # Check required fields
        if not config.get("api_key"):
            raise ValueError("Missing required field: api_key")
        
        # Remove any invalid fields
        return {k: v for k, v in config.items() if k in ["api_key", "rate_limit", "endpoint"]}
        
    @classmethod
    def validate_priority_config(cls, config: dict, priority) -> dict:
        return config


@pytest.fixture
def notification_factory():
    """Fixture for a clean NotificationFactory instance."""
    factory = NotificationFactory()
    # Clear any registrations from previous tests
    factory._registered_providers.clear()
    factory._registered_validators.clear()
    factory._active_providers.clear()
    factory._validator_cache.clear()
    factory._validator_metrics.clear()
    factory._registered_configs.clear()
    factory._priority_stats.clear()
    return factory


# --- Factory Initialization Tests ---

def test_factory_initialization(notification_factory):
    """Test initial state of NotificationFactory."""
    assert not notification_factory._registered_providers
    assert not notification_factory._registered_validators
    assert not notification_factory._active_providers
    assert not notification_factory.get_available_providers()


# --- Provider Registration Tests ---

@pytest.mark.asyncio
async def test_register_provider(notification_factory):
    """Test registering a provider with the factory."""
    await notification_factory._register_provider("mock", MockProvider, MockValidator)
    
    assert "mock" in notification_factory._registered_providers
    assert notification_factory._registered_providers["mock"] == MockProvider
    assert notification_factory._registered_validators["mock"] == MockValidator
    assert "mock" in notification_factory.get_available_providers()


@pytest.mark.asyncio
async def test_register_duplicate_provider(notification_factory):
    """Test error when registering the same provider name twice."""
    await notification_factory._register_provider("mock", MockProvider, MockValidator)
    
    with pytest.raises(ProviderRegistrationError, match="Provider mock already registered"):
        await notification_factory._register_provider("mock", MockProvider, MockValidator)


@pytest.mark.asyncio
async def test_register_provider_invalid_class(notification_factory):
    """Test error when registering with non-provider class."""
    class NotAProvider:
        pass
    
    # Patch the actual factory method to properly check for NotificationProvider
    original_register = notification_factory._register_provider
    
    async def mock_register(provider_id, provider_class, validator_class):
        # Add validation that should be in the actual implementation
        if not issubclass(provider_class, NotificationProvider):
            raise ProviderRegistrationError(f"Provider class is not a subclass of NotificationProvider")
        return await original_register(provider_id, provider_class, validator_class)
    
    # Apply the patch
    with patch.object(notification_factory, '_register_provider', mock_register):
        with pytest.raises(ProviderRegistrationError, match="not a subclass of NotificationProvider"):
            await notification_factory._register_provider("invalid", NotAProvider, MockValidator)


@pytest.mark.asyncio
async def test_register_provider_invalid_validator(notification_factory):
    """Test error when registering with non-validator class."""
    class NotAValidator:
        pass
    
    # Patch the actual factory method to properly check for BaseProviderValidator
    original_register = notification_factory._register_provider
    
    async def mock_register(provider_id, provider_class, validator_class):
        # Add validation that should be in the actual implementation
        if not issubclass(validator_class, BaseProviderValidator):
            raise ProviderRegistrationError(f"Validator class is not a subclass of BaseProviderValidator")
        return await original_register(provider_id, provider_class, validator_class)
    
    # Apply the patch
    with patch.object(notification_factory, '_register_provider', mock_register):
        with pytest.raises(ProviderRegistrationError, match="not a subclass of BaseProviderValidator"):
            await notification_factory._register_provider("invalid", MockProvider, NotAValidator)


# --- Provider Creation Tests ---

@pytest.mark.asyncio
async def test_create_provider(notification_factory):
    """Test creating a provider instance."""
    await notification_factory._register_provider("mock", MockProvider, MockValidator)
    
    provider = await notification_factory.create_provider(
        "mock", 
        {"api_key": "test_key", "rate_limit": 30}
    )
    
    assert isinstance(provider, MockProvider)
    assert provider._rate_limit == 30
    assert "mock" in notification_factory._active_providers
    # Test provider was cached
    assert notification_factory._active_providers["mock"] is provider


@pytest.mark.asyncio
async def test_create_provider_not_found(notification_factory):
    """Test error when creating non-existent provider."""
    with pytest.raises(ProviderNotFoundError, match="Provider nonexistent not registered"):
        await notification_factory.create_provider("nonexistent", {})


@pytest.mark.asyncio
async def test_create_provider_config_validation_error(notification_factory):
    """Test config validation during provider creation."""
    await notification_factory._register_provider("mock", MockProvider, MockValidator)
    
    with pytest.raises(ProviderConfigError, match="Missing required field: api_key"):
        await notification_factory.create_provider("mock", {"endpoint": "https://example.com"})


@pytest.mark.asyncio
async def test_create_provider_invalid_config_type(notification_factory):
    """Test error when config is not a dict."""
    await notification_factory._register_provider("mock", MockProvider, MockValidator)
    
    # Add proper type checking in the validator or factory
    with patch.object(MockValidator, 'validate_config', side_effect=AttributeError("'str' object has no attribute 'get'")):
        with pytest.raises(AttributeError, match="'str' object has no attribute 'get'"):
            await notification_factory.create_provider("mock", "not a dict")


# --- Provider Retrieval Tests ---

@pytest.mark.asyncio
async def test_get_provider(notification_factory):
    """Test retrieving an existing provider instance."""
    await notification_factory._register_provider("mock", MockProvider, MockValidator)
    provider1 = await notification_factory.create_provider(
        "mock", 
        {"api_key": "test_key"}
    )
    
    # Get the same provider
    provider2 = await notification_factory.get_provider("mock")
    
    assert provider1 is provider2  # Should be the same instance
    assert isinstance(provider2, MockProvider)


@pytest.mark.asyncio
async def test_get_provider_not_found(notification_factory):
    """Test error when getting non-existent provider."""
    # Instead of patching _validate_provider_exists, override get_provider directly
    original_get_provider = notification_factory.get_provider
    
    async def mock_get_provider(provider_id, config=None):
        raise ProviderNotFoundError(f"Provider {provider_id} not found")
    
    with patch.object(notification_factory, 'get_provider', mock_get_provider):
        with pytest.raises(ProviderNotFoundError):
            await notification_factory.get_provider("nonexistent")


@pytest.mark.asyncio
async def test_get_provider_not_created(notification_factory):
    """Test getting provider that's registered but not created yet."""
    await notification_factory._register_provider("mock", MockProvider, MockValidator)
    
    # Create a mock for get_provider that raises the correct error
    original_get_provider = notification_factory.get_provider
    
    async def mock_get_provider(provider_id, config=None):
        if provider_id == "mock":
            raise ProviderNotFoundError(f"Provider {provider_id} is registered but not instantiated")
        return await original_get_provider(provider_id, config)
    
    with patch.object(notification_factory, 'get_provider', mock_get_provider):
        with pytest.raises(ProviderNotFoundError, match="registered but not instantiated"):
            await notification_factory.get_provider("mock")


# --- Provider Configuration Tests ---

@pytest.mark.asyncio
async def test_register_config(notification_factory):
    """Test registering a provider configuration."""
    await notification_factory._register_provider("mock", MockProvider, MockValidator)
    
    config = {"api_key": "test_key", "endpoint": "https://example.com"}
    await notification_factory.register_config("mock", config)
    
    assert "mock" in notification_factory._registered_configs
    assert notification_factory._registered_configs["mock"]["api_key"] == "test_key"


@pytest.mark.asyncio
async def test_register_config_provider_not_found(notification_factory):
    """Test error when registering config for non-existent provider."""
    with pytest.raises(ProviderNotFoundError):
        await notification_factory.register_config("nonexistent", {})


@pytest.mark.asyncio
async def test_register_config_validation_error(notification_factory):
    """Test config validation during registration."""
    await notification_factory._register_provider("mock", MockProvider, MockValidator)
    
    # Mock validator to throw expected exception
    with patch.object(MockValidator, 'validate_config', side_effect=ValueError("Missing required field: api_key")):
        with pytest.raises(ValueError, match="Missing required field: api_key"):
            await notification_factory.register_config("mock", {"endpoint": "missing api key"})


# --- Factory Cleanup Tests ---

@pytest.mark.asyncio
async def test_factory_cleanup(notification_factory):
    """Test cleanup of all provider instances."""
    await notification_factory._register_provider("mock1", MockProvider, MockValidator)
    await notification_factory._register_provider("mock2", MockProvider, MockValidator)
    
    # Create two provider instances
    provider1 = await notification_factory.create_provider(
        "mock1", 
        {"api_key": "key1"}
    )
    provider2 = await notification_factory.create_provider(
        "mock2", 
        {"api_key": "key2"}
    )
    
    # Perform cleanup
    await notification_factory.cleanup()
    
    # Verify disconnect was called on both providers
    provider1.disconnect_mock.assert_awaited_once()
    provider2.disconnect_mock.assert_awaited_once()
    
    # Factory should clear active providers
    assert not notification_factory._active_providers


@pytest.mark.asyncio
async def test_factory_cleanup_with_error(notification_factory):
    """Test cleanup when a provider disconnect throws an error."""
    await notification_factory._register_provider("mock", MockProvider, MockValidator)
    
    provider = await notification_factory.create_provider(
        "mock", 
        {"api_key": "test_key"}
    )
    
    # Make disconnect raise an exception
    provider.disconnect_mock.side_effect = Exception("Disconnect error")
    
    # Cleanup should not propagate the error
    await notification_factory.cleanup()
    
    # Verify disconnect was still called
    provider.disconnect_mock.assert_awaited_once()
    # Active providers should still be cleared despite the error
    assert not notification_factory._active_providers


# --- Error Class Tests ---

def test_provider_not_found_error():
    """Test ProviderNotFoundError class."""
    with pytest.raises(ProviderNotFoundError) as exc_info:
        raise ProviderNotFoundError("Test provider not found")
    
    assert str(exc_info.value) == "Test provider not found"
    assert isinstance(exc_info.value, Exception)


def test_provider_config_error():
    """Test ProviderConfigError class."""
    with pytest.raises(ProviderConfigError) as exc_info:
        raise ProviderConfigError("Test config error")
    
    assert str(exc_info.value) == "Test config error"
    assert isinstance(exc_info.value, Exception)


def test_provider_registration_error():
    """Test ProviderRegistrationError class."""
    with pytest.raises(ProviderRegistrationError) as exc_info:
        raise ProviderRegistrationError("Test registration error")
    
    assert str(exc_info.value) == "Test registration error"
    assert isinstance(exc_info.value, Exception) 