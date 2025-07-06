"""Tests for the Provider Registry System."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from typing import TYPE_CHECKING, override

from mover_status.notifications.base.registry import (
    ProviderRegistry,
    ProviderRegistryError,
    ProviderMetadata,
    ProviderDiscovery,
    ProviderLifecycleManager,
)
from mover_status.notifications.base.provider import NotificationProvider
from mover_status.notifications.models.message import Message

if TYPE_CHECKING:
    from collections.abc import Mapping


class MockProvider(NotificationProvider):
    """Mock provider for testing."""
    
    def __init__(self, config: Mapping[str, object]) -> None:
        super().__init__(config)
        self.send_calls: list[Message] = []
        self.validate_calls: list[bool] = []
        
    @override
    async def send_notification(self, message: Message) -> bool:
        """Mock send notification."""
        self.send_calls.append(message)
        return True
        
    @override
    def validate_config(self) -> None:
        """Mock validate config."""
        self.validate_calls.append(True)
        
    @override
    def get_provider_name(self) -> str:
        """Mock get provider name."""
        return "mock"


class FailingProvider(NotificationProvider):
    """Provider that fails validation for testing."""
    
    def __init__(self, config: Mapping[str, object]) -> None:
        super().__init__(config)
        
    @override
    async def send_notification(self, message: Message) -> bool:
        """Mock send notification."""
        return False
        
    @override
    def validate_config(self) -> None:
        """Mock validate config that fails."""
        raise ValueError("Invalid configuration")
        
    @override
    def get_provider_name(self) -> str:
        """Mock get provider name."""
        return "failing"


class TestProviderMetadata:
    """Test ProviderMetadata class."""
    
    def test_metadata_creation(self) -> None:
        """Test creating provider metadata."""
        metadata = ProviderMetadata(
            name="test",
            description="Test provider",
            version="1.0.0",
            author="Test Author",
            provider_class=MockProvider,
            config_schema={"type": "object"}
        )
        
        assert metadata.name == "test"
        assert metadata.description == "Test provider"
        assert metadata.version == "1.0.0"
        assert metadata.author == "Test Author"
        assert metadata.provider_class == MockProvider
        assert metadata.config_schema == {"type": "object"}
        assert metadata.enabled is True
        assert metadata.priority == 0
        assert metadata.tags == []
        assert metadata.dependencies == []
        
    def test_metadata_equality(self) -> None:
        """Test metadata equality comparison."""
        metadata1 = ProviderMetadata(
            name="test",
            description="Test provider",
            version="1.0.0",
            author="Test Author",
            provider_class=MockProvider
        )
        metadata2 = ProviderMetadata(
            name="test",
            description="Test provider",
            version="1.0.0",
            author="Test Author",
            provider_class=MockProvider
        )
        
        assert metadata1 == metadata2
        
    def test_metadata_inequality(self) -> None:
        """Test metadata inequality comparison."""
        metadata1 = ProviderMetadata(
            name="test1",
            description="Test provider",
            version="1.0.0",
            author="Test Author",
            provider_class=MockProvider
        )
        metadata2 = ProviderMetadata(
            name="test2",
            description="Test provider",
            version="1.0.0",
            author="Test Author",
            provider_class=MockProvider
        )
        
        assert metadata1 != metadata2
        
    def test_metadata_string_representation(self) -> None:
        """Test metadata string representation."""
        metadata = ProviderMetadata(
            name="test",
            description="Test provider",
            version="1.0.0",
            author="Test Author",
            provider_class=MockProvider
        )
        
        repr_str = str(metadata)
        assert "test" in repr_str
        assert "1.0.0" in repr_str


class TestProviderRegistry:
    """Test ProviderRegistry class."""
    
    def test_registry_initialization(self) -> None:
        """Test registry initialization."""
        registry = ProviderRegistry()
        
        assert len(registry._providers) == 0  # pyright: ignore[reportPrivateUsage]
        assert len(registry._metadata) == 0  # pyright: ignore[reportPrivateUsage]
        assert len(registry._instances) == 0  # pyright: ignore[reportPrivateUsage]
        
    def test_register_provider(self) -> None:
        """Test registering a provider."""
        registry = ProviderRegistry()
        metadata = ProviderMetadata(
            name="test",
            description="Test provider",
            version="1.0.0",
            author="Test Author",
            provider_class=MockProvider
        )
        
        registry.register("test", MockProvider, metadata)

        assert registry.provider_exists("test")
        assert registry.get_provider_metadata("test") == metadata
        
    def test_register_duplicate_provider(self) -> None:
        """Test registering a duplicate provider raises error."""
        registry = ProviderRegistry()
        metadata = ProviderMetadata(
            name="test",
            description="Test provider",
            version="1.0.0",
            author="Test Author",
            provider_class=MockProvider
        )
        
        registry.register("test", MockProvider, metadata)
        
        with pytest.raises(ProviderRegistryError, match="Provider 'test' is already registered"):
            registry.register("test", MockProvider, metadata)
            
    def test_register_provider_with_force(self) -> None:
        """Test registering a provider with force overwrites existing."""
        registry = ProviderRegistry()
        metadata1 = ProviderMetadata(
            name="test",
            description="Test provider 1",
            version="1.0.0",
            author="Test Author",
            provider_class=MockProvider
        )
        metadata2 = ProviderMetadata(
            name="test",
            description="Test provider 2",
            version="2.0.0",
            author="Test Author",
            provider_class=MockProvider
        )
        
        registry.register("test", MockProvider, metadata1)
        registry.register("test", MockProvider, metadata2, force=True)

        assert registry.get_provider_metadata("test") == metadata2
        
    def test_unregister_provider(self) -> None:
        """Test unregistering a provider."""
        registry = ProviderRegistry()
        metadata = ProviderMetadata(
            name="test",
            description="Test provider",
            version="1.0.0",
            author="Test Author",
            provider_class=MockProvider
        )
        
        registry.register("test", MockProvider, metadata)
        registry.unregister("test")

        assert not registry.provider_exists("test")
        assert registry.get_provider_metadata("test") is None
        
    def test_unregister_nonexistent_provider(self) -> None:
        """Test unregistering a nonexistent provider raises error."""
        registry = ProviderRegistry()
        
        with pytest.raises(ProviderRegistryError, match="Provider 'nonexistent' is not registered"):
            registry.unregister("nonexistent")
            
    def test_create_provider(self) -> None:
        """Test creating a provider instance."""
        registry = ProviderRegistry()
        metadata = ProviderMetadata(
            name="test",
            description="Test provider",
            version="1.0.0",
            author="Test Author",
            provider_class=MockProvider
        )
        
        registry.register("test", MockProvider, metadata)
        
        config = {"enabled": True, "setting": "value"}
        provider = registry.create_provider("test", config)
        
        assert isinstance(provider, MockProvider)
        assert provider.config == config
        assert provider.enabled is True
        
    def test_create_provider_with_caching(self) -> None:
        """Test creating a provider instance with caching."""
        registry = ProviderRegistry()
        metadata = ProviderMetadata(
            name="test",
            description="Test provider",
            version="1.0.0",
            author="Test Author",
            provider_class=MockProvider
        )
        
        registry.register("test", MockProvider, metadata)
        
        config = {"enabled": True, "setting": "value"}
        provider1 = registry.create_provider("test", config, cache=True)
        provider2 = registry.create_provider("test", config, cache=True)
        
        assert provider1 is provider2
        
    def test_create_provider_without_caching(self) -> None:
        """Test creating a provider instance without caching."""
        registry = ProviderRegistry()
        metadata = ProviderMetadata(
            name="test",
            description="Test provider",
            version="1.0.0",
            author="Test Author",
            provider_class=MockProvider
        )
        
        registry.register("test", MockProvider, metadata)
        
        config = {"enabled": True, "setting": "value"}
        provider1 = registry.create_provider("test", config, cache=False)
        provider2 = registry.create_provider("test", config, cache=False)
        
        assert provider1 is not provider2
        
    def test_create_nonexistent_provider(self) -> None:
        """Test creating a nonexistent provider raises error."""
        registry = ProviderRegistry()
        
        with pytest.raises(ProviderRegistryError, match="Provider 'nonexistent' is not registered"):
            _ = registry.create_provider("nonexistent", {})
            
    def test_list_providers(self) -> None:
        """Test listing providers."""
        registry = ProviderRegistry()
        metadata1 = ProviderMetadata(
            name="test1",
            description="Test provider 1",
            version="1.0.0",
            author="Test Author",
            provider_class=MockProvider
        )
        metadata2 = ProviderMetadata(
            name="test2",
            description="Test provider 2",
            version="2.0.0",
            author="Test Author",
            provider_class=MockProvider
        )
        
        registry.register("test1", MockProvider, metadata1)
        registry.register("test2", MockProvider, metadata2)
        
        providers = registry.list_providers()
        assert len(providers) == 2
        assert "test1" in providers
        assert "test2" in providers
        
    def test_list_providers_with_filter(self) -> None:
        """Test listing providers with filter."""
        registry = ProviderRegistry()
        metadata1 = ProviderMetadata(
            name="test1",
            description="Test provider 1",
            version="1.0.0",
            author="Test Author",
            provider_class=MockProvider,
            enabled=True
        )
        metadata2 = ProviderMetadata(
            name="test2",
            description="Test provider 2",
            version="2.0.0",
            author="Test Author",
            provider_class=MockProvider,
            enabled=False
        )
        
        registry.register("test1", MockProvider, metadata1)
        registry.register("test2", MockProvider, metadata2)
        
        enabled_providers = registry.list_providers(enabled_only=True)
        assert len(enabled_providers) == 1
        assert "test1" in enabled_providers
        assert "test2" not in enabled_providers
        
    def test_get_provider_metadata(self) -> None:
        """Test getting provider metadata."""
        registry = ProviderRegistry()
        metadata = ProviderMetadata(
            name="test",
            description="Test provider",
            version="1.0.0",
            author="Test Author",
            provider_class=MockProvider
        )
        
        registry.register("test", MockProvider, metadata)
        
        retrieved_metadata = registry.get_provider_metadata("test")
        assert retrieved_metadata == metadata
        
    def test_get_nonexistent_provider_metadata(self) -> None:
        """Test getting metadata for nonexistent provider."""
        registry = ProviderRegistry()
        
        assert registry.get_provider_metadata("nonexistent") is None
        
    def test_provider_exists(self) -> None:
        """Test checking if provider exists."""
        registry = ProviderRegistry()
        metadata = ProviderMetadata(
            name="test",
            description="Test provider",
            version="1.0.0",
            author="Test Author",
            provider_class=MockProvider
        )
        
        registry.register("test", MockProvider, metadata)
        
        assert registry.provider_exists("test") is True
        assert registry.provider_exists("nonexistent") is False


class TestProviderDiscovery:
    """Test ProviderDiscovery class."""
    
    def test_discovery_initialization(self) -> None:
        """Test discovery initialization."""
        discovery = ProviderDiscovery()

        assert len(discovery.get_search_paths()) == 0
        
    def test_add_search_path(self) -> None:
        """Test adding search path."""
        discovery = ProviderDiscovery()

        discovery.add_search_path("/test/path")

        assert discovery.has_search_path("/test/path")
        
    def test_remove_search_path(self) -> None:
        """Test removing search path."""
        discovery = ProviderDiscovery()

        discovery.add_search_path("/test/path")
        discovery.remove_search_path("/test/path")

        assert not discovery.has_search_path("/test/path")
        
    def test_discover_providers_empty(self) -> None:
        """Test discovering providers with no search paths."""
        discovery = ProviderDiscovery()
        
        providers = discovery.discover_providers()
        
        assert len(providers) == 0
        
    def test_auto_register_providers(self) -> None:
        """Test auto-registering discovered providers."""
        discovery = ProviderDiscovery()
        registry = ProviderRegistry()
        
        # Mock discovered providers
        mock_providers = {
            "mock1": (MockProvider, ProviderMetadata(
                name="mock1",
                description="Mock provider 1",
                version="1.0.0",
                author="Test",
                provider_class=MockProvider
            ))
        }
        
        discovery.discover_providers = MagicMock(return_value=mock_providers)
        
        count = discovery.auto_register_providers(registry)
        
        assert count == 1
        assert registry.provider_exists("mock1")


class TestProviderLifecycleManager:
    """Test ProviderLifecycleManager class."""
    
    def test_lifecycle_manager_initialization(self) -> None:
        """Test lifecycle manager initialization."""
        manager = ProviderLifecycleManager()

        assert len(manager.get_active_providers()) == 0
        assert manager.get_startup_hook_count() == 0
        assert manager.get_shutdown_hook_count() == 0
        
    def test_add_startup_hook(self) -> None:
        """Test adding startup hook."""
        manager = ProviderLifecycleManager()

        async def startup_hook() -> None:
            pass

        manager.add_startup_hook(startup_hook)

        assert manager.get_startup_hook_count() == 1
        
    def test_add_shutdown_hook(self) -> None:
        """Test adding shutdown hook."""
        manager = ProviderLifecycleManager()

        async def shutdown_hook() -> None:
            pass

        manager.add_shutdown_hook(shutdown_hook)

        assert manager.get_shutdown_hook_count() == 1
        
    @pytest.mark.asyncio
    async def test_startup_provider(self) -> None:
        """Test starting up a provider."""
        manager = ProviderLifecycleManager()
        provider = MockProvider({"enabled": True})
        
        startup_called = False
        
        async def startup_hook() -> None:
            nonlocal startup_called
            startup_called = True
            
        manager.add_startup_hook(startup_hook)
        
        await manager.startup_provider("test", provider)

        assert manager.is_provider_active("test")
        assert startup_called is True
        
    @pytest.mark.asyncio
    async def test_shutdown_provider(self) -> None:
        """Test shutting down a provider."""
        manager = ProviderLifecycleManager()
        provider = MockProvider({"enabled": True})
        
        shutdown_called = False
        
        async def shutdown_hook() -> None:
            nonlocal shutdown_called
            shutdown_called = True
            
        manager.add_shutdown_hook(shutdown_hook)
        
        await manager.startup_provider("test", provider)
        await manager.shutdown_provider("test")

        assert not manager.is_provider_active("test")
        assert shutdown_called is True
        
    @pytest.mark.asyncio
    async def test_shutdown_all_providers(self) -> None:
        """Test shutting down all providers."""
        manager = ProviderLifecycleManager()
        provider1 = MockProvider({"enabled": True})
        provider2 = MockProvider({"enabled": True})
        
        shutdown_count = 0
        
        async def shutdown_hook() -> None:
            nonlocal shutdown_count
            shutdown_count += 1
            
        manager.add_shutdown_hook(shutdown_hook)
        
        await manager.startup_provider("test1", provider1)
        await manager.startup_provider("test2", provider2)
        
        await manager.shutdown_all_providers()

        assert len(manager.get_active_providers()) == 0
        assert shutdown_count == 2
        
    def test_get_active_providers(self) -> None:
        """Test getting active providers."""
        manager = ProviderLifecycleManager()
        
        active_providers = manager.get_active_providers()
        
        assert len(active_providers) == 0
        
    def test_is_provider_active(self) -> None:
        """Test checking if provider is active."""
        manager = ProviderLifecycleManager()
        
        assert manager.is_provider_active("test") is False