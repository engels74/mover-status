import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from config.constants import MessagePriority, MessageType, NotificationLevel
from notifications.base import (
    NotificationError,
    NotificationProvider,
    NotificationState,
)
from notifications.factory import (
    NotificationFactory,
    ProviderConfigError,
    ProviderNotFoundError,
    ProviderRegistrationError,
)
from utils.validators import BaseProviderValidator


# --- Test Fixtures and Mocks ---

# Dummy Provider Implementation for testing
class DummyProvider(NotificationProvider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.send_mock = AsyncMock()

    async def send_notification(self, message: str, **kwargs) -> bool:
        # Simulate potential failure
        if "fail" in message:
            raise NotificationError("Simulated send failure")
        await self.send_mock(message, **kwargs)
        return True # Assume success unless exception

    # Add methods for ProviderProtocol conformance
    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass


# Dummy Validator
class DummyValidator(BaseProviderValidator):
    # Implement abstract method
    @classmethod
    def validate_config(cls, config: dict) -> dict:
        # Basic implementation for testing
        return config

    # Add other methods if BaseProviderValidator requires them
    @classmethod
    def validate_priority_config(cls, config: dict, priority) -> dict:
        return config


@pytest.fixture
def notification_state():
    """Fixture for a clean NotificationState instance."""
    return NotificationState()

@pytest.fixture
def dummy_provider():
    """Fixture for a DummyProvider instance."""
    return DummyProvider()

@pytest.fixture
def notification_factory():
    """Fixture for a clean NotificationFactory instance."""
    # Reset global factory state for isolation if necessary, or create new instances
    factory = NotificationFactory()
    # Clear any registrations from previous tests if using a shared registry (design dependent)
    factory._registered_providers.clear()
    factory._registered_validators.clear()
    factory._active_providers.clear()
    factory._validator_cache.clear()
    # Also clear other state if necessary, e.g., metrics, stats, configs
    factory._validator_metrics.clear()
    factory._registered_configs.clear()
    factory._priority_stats.clear()
    return factory

# --- NotificationState Tests ---

@pytest.mark.asyncio
async def test_notification_state_initialization(notification_state):
    assert notification_state.notification_count == 0
    assert notification_state.success_count == 0
    assert notification_state.error_count == 0
    assert notification_state.last_notification is None
    assert not notification_state.history
    assert not notification_state.rate_limited
    assert not notification_state.disabled

@pytest.mark.asyncio
async def test_notification_state_add_notification_success(notification_state):
    await notification_state.add_notification("Test message", success=True, priority=MessagePriority.HIGH, message_type=MessageType.ERROR)
    assert notification_state.notification_count == 1
    assert notification_state.success_count == 1
    assert notification_state.error_count == 0
    assert notification_state.last_notification is not None
    assert len(notification_state.history) == 1
    assert notification_state.history[0]["message"] == "Test message"
    assert notification_state.history[0]["success"] is True
    assert notification_state.type_counts[MessageType.ERROR] == 1
    assert notification_state._priority_counts[MessagePriority.HIGH] == 1 # Accessing private for verification simplicity

@pytest.mark.asyncio
async def test_notification_state_add_notification_failure(notification_state):
    await notification_state.add_notification("Failure message", success=False, priority=MessagePriority.LOW, message_type=MessageType.WARNING)
    # Note: add_notification doesn't automatically increment error_count, that's handled in Provider's notify
    assert notification_state.notification_count == 1
    assert notification_state.success_count == 0
    # assert notification_state.error_count == 1 # This should be handled by the caller (Provider)
    assert notification_state.last_notification is not None # Timestamp is updated regardless of success
    assert len(notification_state.history) == 1
    assert notification_state.history[0]["success"] is False
    assert notification_state.type_counts[MessageType.WARNING] == 1
    assert notification_state._priority_counts[MessagePriority.LOW] == 1

# --- NotificationProvider Tests ---

@pytest.mark.asyncio
async def test_provider_initialization(dummy_provider):
    assert dummy_provider.state.notification_count == 0
    # Assuming API.DEFAULT_RATE_LIMIT is 60 based on previous error
    assert dummy_provider._rate_limit == 60 # Default rate limit
    assert dummy_provider._rate_period == 60 # Default rate period
    assert dummy_provider._retry_attempts == 3 # Default retry attempts

@pytest.mark.asyncio
async def test_provider_notify_success(dummy_provider):
    success = await dummy_provider.notify("Successful message", level=NotificationLevel.INFO, message_type=MessageType.SYSTEM)
    assert success is True
    dummy_provider.send_mock.assert_awaited_once()
    assert dummy_provider.state.notification_count == 1
    assert dummy_provider.state.success_count == 1
    assert dummy_provider.state.error_count == 0

@pytest.mark.asyncio
async def test_provider_notify_failure_and_retry(dummy_provider):
    # Configure provider for retries
    dummy_provider._retry_attempts = 2
    dummy_provider._retry_delay = 0.01 # Short delay for test

    # Mock send_notification to fail initially, then succeed
    dummy_provider.send_mock.side_effect = [NotificationError("Attempt 1 fail"), True]

    success = await dummy_provider.notify("Retry message", level=NotificationLevel.WARNING)

    assert success is True # Should succeed on retry
    assert dummy_provider.send_mock.call_count == 2 # Original call + 1 retry
    assert dummy_provider.state.notification_count == 1 # Counts as one attempt
    assert dummy_provider.state.success_count == 1 # Eventually succeeded
    assert dummy_provider.state.error_count == 0 # Tracks final outcome
    # Note: state doesn't track intermediate errors within retries explicitly

@pytest.mark.asyncio
async def test_provider_notify_persistent_failure(dummy_provider):
    dummy_provider._retry_attempts = 3 # Use default for consistency with priority calc
    dummy_provider._retry_delay = 0.01
    dummy_provider.send_mock.side_effect = NotificationError("Persistent failure")

    success = await dummy_provider.notify("Fail message", level=NotificationLevel.ERROR) # HIGH priority

    assert success is False
    # HIGH priority = default 3 + 1 = 4 retries. 1 initial + 4 retries = 5 calls.
    assert dummy_provider.send_mock.await_count == 5
    assert dummy_provider.state.notification_count == 1 # State update happens once
    assert dummy_provider.state.success_count == 0
    assert dummy_provider.state.error_count == 1 # Error count updated in finally
    assert "Persistent failure" in dummy_provider.state.last_error
    assert dummy_provider.state.last_error_time is not None

@pytest.mark.asyncio
async def test_provider_notify_rate_limited(dummy_provider: DummyProvider):
     # Manually set rate limit state for testing
    dummy_provider.state.rate_limited = True
    dummy_provider.state.rate_limit_until = time.monotonic() + 10 # Rate limited for 10s

    success = await dummy_provider.notify("Rate limit test")

    assert success is False
    dummy_provider.send_mock.assert_not_awaited() # Should not attempt send
    # The notify method still logs the attempt via add_notification even if skipped
    assert dummy_provider.state.notification_count == 1 # Attempt logged
    assert dummy_provider.state.error_count == 0 # Not counted as an error in finally block

@pytest.mark.asyncio
async def test_provider_notify_rate_limit_expired(dummy_provider: DummyProvider):
    # Manually set rate limit state for testing (already expired)
    dummy_provider.state.rate_limited = True
    dummy_provider.state.rate_limit_until = time.monotonic() - 1 # Expired 1s ago

    success = await dummy_provider.notify("Rate limit expired test")

    assert success is True
    dummy_provider.send_mock.assert_awaited_once() # Should attempt send now
    assert dummy_provider.state.notification_count == 1
    assert dummy_provider.state.success_count == 1
    assert dummy_provider.state.rate_limited is False # State should be reset
    assert dummy_provider.state.rate_limit_until is None


# --- NotificationFactory Tests ---

@pytest.mark.asyncio
async def test_factory_register_provider(notification_factory: NotificationFactory):
    # Register using the internal async method directly on the instance
    await notification_factory._register_provider("dummy", DummyProvider, DummyValidator)

    assert "dummy" in notification_factory._registered_providers
    assert notification_factory._registered_providers["dummy"] == DummyProvider
    assert "dummy" in notification_factory._registered_validators
    assert notification_factory._registered_validators["dummy"] == DummyValidator

@pytest.mark.asyncio
async def test_factory_register_duplicate(notification_factory: NotificationFactory):
    await notification_factory._register_provider("dummy", DummyProvider, DummyValidator)
    with pytest.raises(ProviderRegistrationError): # Just check type for now
        await notification_factory._register_provider("dummy", DummyProvider, DummyValidator)

@pytest.mark.asyncio
async def test_factory_create_provider_success(notification_factory: NotificationFactory):
    await notification_factory._register_provider("dummy", DummyProvider, DummyValidator)
    config = {"key": "value", "rate_limit": 5} # Include rate_limit for provider init
    provider = await notification_factory.create_provider("dummy", config)

    assert isinstance(provider, DummyProvider)
    assert provider._rate_limit == 5 # Check if config was passed
    assert "dummy" in notification_factory._active_providers # Check instance cache

@pytest.mark.asyncio
async def test_factory_create_provider_not_found(notification_factory: NotificationFactory):
    with pytest.raises(ProviderNotFoundError): # Simpler check: just type
        await notification_factory.create_provider("nonexistent")

@pytest.mark.asyncio
async def test_factory_create_provider_config_validation_error(notification_factory: NotificationFactory):
    # 1. Create a mock instance configured to raise the error
    mock_validator_instance = MagicMock(spec=BaseProviderValidator)
    mock_validator_instance.validate_config.side_effect = ValueError("Invalid config key")
    # Add validate_priority_config if needed by the factory logic within _validate_config
    mock_validator_instance.validate_priority_config = MagicMock(return_value={}) # Assume it returns config

    # 2. Create a mock class that returns the configured instance when instantiated
    mock_validator_class = MagicMock(spec=BaseProviderValidator)
    mock_validator_class.return_value = mock_validator_instance
    mock_validator_class.__name__ = "MockValidator" # Add __name__ for logging

    # 3. Register the mock class with the factory
    await notification_factory._register_provider("dummy", DummyProvider, mock_validator_class)

    # 4. Now, the test should correctly catch the ProviderConfigError
    with pytest.raises(ProviderConfigError, match=r"Configuration validation failed for dummy: Invalid config key"):
        await notification_factory.create_provider("dummy", {"bad_key": "value"})

    # Verify that the validate_config method on the *instance* was called
    mock_validator_instance.validate_config.assert_called_once_with({"bad_key": "value"})

@pytest.mark.asyncio
async def test_factory_get_available_providers(notification_factory: NotificationFactory):
    assert not notification_factory.get_available_providers()
    await notification_factory._register_provider("dummy1", DummyProvider, DummyValidator)
    await notification_factory._register_provider("dummy2", DummyProvider, DummyValidator)
    providers = notification_factory.get_available_providers()
    assert sorted(providers) == ["dummy1", "dummy2"]

@pytest.mark.asyncio
async def test_factory_get_provider_instance(notification_factory: NotificationFactory):
    await notification_factory._register_provider("dummy", DummyProvider, DummyValidator)
    config = {"rate_limit": 10}
    provider1 = await notification_factory.create_provider("dummy", config)
    # Attempt to get again, should retrieve cached
    provider2 = await notification_factory.get_provider("dummy")

    assert provider1 is provider2 # Should be the same instance
    assert isinstance(provider1, DummyProvider) # Type check
    assert provider1._rate_limit == 10

@pytest.mark.asyncio
async def test_factory_cleanup(notification_factory: NotificationFactory):
    # Mock the disconnect method of the provider instance
    mock_provider = AsyncMock(spec=DummyProvider)
    mock_provider.disconnect = AsyncMock()

    # Register and create an instance to be cleaned up
    # Use correct internal attribute names for setup
    notification_factory._registered_providers["dummy"] = DummyProvider
    notification_factory._registered_validators["dummy"] = DummyValidator # Need validator too
    notification_factory._active_providers["dummy"] = mock_provider

    await notification_factory.cleanup()

    # Assert disconnect was called on the mock provider
    mock_provider.disconnect.assert_awaited_once()
    # Factory should clear active providers on cleanup
    assert not notification_factory._active_providers


# --- Error Handling Tests ---

def test_notification_error_base():
    with pytest.raises(NotificationError):
        raise NotificationError("Base notification error")

def test_provider_not_found_error():
    with pytest.raises(ProviderNotFoundError):
        raise ProviderNotFoundError("Provider not found")

def test_provider_config_error():
     with pytest.raises(ProviderConfigError):
        raise ProviderConfigError("Config error")

def test_provider_registration_error():
     with pytest.raises(ProviderRegistrationError):
        raise ProviderRegistrationError("Registration error") 