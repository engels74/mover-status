"""Test cases for the monitoring orchestrator lifecycle management system."""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from mover_status.core.monitor.lifecycle import (
    LifecycleManager,
    ComponentLifecycle,
    LifecycleState,
    LifecycleEvent,
    LifecycleHook,
    StartupError,
    HealthCheckManager,
    ConfigHotReloader,
    ResourceCleanupManager,
    DependencyOrderer,
    VersionManager,
)
from mover_status.core.monitor.orchestrator import (
    MonitorOrchestrator,
    ComponentRegistry,
    Component,
    ComponentType,
    ComponentStatus,
)
from mover_status.config.models.main import AppConfig


class TestLifecycleState:
    """Test cases for lifecycle state enumeration."""
    
    def test_lifecycle_states_exist(self) -> None:
        """Test that all required lifecycle states are defined."""
        assert LifecycleState.UNINITIALIZED
        assert LifecycleState.INITIALIZING
        assert LifecycleState.INITIALIZED
        assert LifecycleState.STARTING
        assert LifecycleState.RUNNING
        assert LifecycleState.STOPPING
        assert LifecycleState.STOPPED
        assert LifecycleState.ERROR
        assert LifecycleState.RELOADING
    
    def test_lifecycle_state_transitions(self) -> None:
        """Test valid lifecycle state transitions."""
        # Test initial state
        assert LifecycleState.UNINITIALIZED.name == "UNINITIALIZED"
        
        # Test state ordering
        states = list(LifecycleState)
        assert len(states) == 9
        assert LifecycleState.UNINITIALIZED in states
        assert LifecycleState.ERROR in states


class TestLifecycleEvent:
    """Test cases for lifecycle event system."""
    
    def test_lifecycle_event_creation(self) -> None:
        """Test lifecycle event creation and properties."""
        event = LifecycleEvent(
            event_type="startup",
            component_name="test_component",
            timestamp=1234567890.0,
            data={"key": "value"}
        )
        
        assert event.event_type == "startup"
        assert event.component_name == "test_component"
        assert event.timestamp == 1234567890.0
        assert event.data == {"key": "value"}
    
    def test_lifecycle_event_serialization(self) -> None:
        """Test lifecycle event serialization."""
        event = LifecycleEvent(
            event_type="shutdown",
            component_name="test_component",
            timestamp=1234567890.0
        )
        
        serialized = event.to_dict()
        assert isinstance(serialized, dict)
        assert serialized["event_type"] == "shutdown"
        assert serialized["component_name"] == "test_component"
        assert serialized["timestamp"] == 1234567890.0


class TestLifecycleHook:
    """Test cases for lifecycle hook system."""
    
    def test_lifecycle_hook_creation(self) -> None:
        """Test lifecycle hook creation."""
        async def test_hook() -> None:
            pass
        
        hook = LifecycleHook(
            name="test_hook",
            callback=test_hook,
            priority=10,
            timeout=30.0
        )
        
        assert hook.name == "test_hook"
        assert hook.callback == test_hook
        assert hook.priority == 10
        assert hook.timeout == 30.0
    
    @pytest.mark.asyncio
    async def test_lifecycle_hook_execution(self) -> None:
        """Test lifecycle hook execution."""
        executed = False
        
        async def test_hook() -> None:
            nonlocal executed
            executed = True
        
        hook = LifecycleHook(
            name="test_hook",
            callback=test_hook,
            priority=10
        )
        
        await hook.execute()
        assert executed
    
    @pytest.mark.asyncio
    async def test_lifecycle_hook_timeout(self) -> None:
        """Test lifecycle hook timeout handling."""
        async def slow_hook() -> None:
            await asyncio.sleep(1.0)
        
        hook = LifecycleHook(
            name="slow_hook",
            callback=slow_hook,
            timeout=0.1
        )
        
        with pytest.raises(asyncio.TimeoutError):
            await hook.execute()


class TestComponentLifecycle:
    """Test cases for component lifecycle management."""
    
    def test_component_lifecycle_creation(self) -> None:
        """Test component lifecycle creation."""
        component = Mock(spec=Component)
        component.name = "test_component"
        component.type = ComponentType.DETECTOR
        
        lifecycle = ComponentLifecycle(component)
        
        assert lifecycle.component == component
        assert lifecycle.state == LifecycleState.UNINITIALIZED
        assert lifecycle.dependencies == []
        assert lifecycle.startup_hooks == []
        assert lifecycle.shutdown_hooks == []
    
    @pytest.mark.asyncio
    async def test_component_lifecycle_startup(self) -> None:
        """Test component lifecycle startup process."""
        component = Mock(spec=Component)
        component.name = "test_component"
        component.type = ComponentType.DETECTOR
        component.status = ComponentStatus.ACTIVE
        
        lifecycle = ComponentLifecycle(component)
        
        # Add startup hook
        hook_executed = False
        
        async def startup_hook() -> None:
            nonlocal hook_executed
            hook_executed = True
        
        lifecycle.add_startup_hook("test_hook", startup_hook)
        
        # Test startup
        await lifecycle.startup()
        
        assert lifecycle.state == LifecycleState.RUNNING
        assert hook_executed
    
    @pytest.mark.asyncio
    async def test_component_lifecycle_shutdown(self) -> None:
        """Test component lifecycle shutdown process."""
        component = Mock(spec=Component)
        component.name = "test_component"
        component.type = ComponentType.DETECTOR
        component.status = ComponentStatus.ACTIVE
        
        lifecycle = ComponentLifecycle(component)
        lifecycle.state = LifecycleState.RUNNING
        
        # Add shutdown hook
        hook_executed = False
        
        async def shutdown_hook() -> None:
            nonlocal hook_executed
            hook_executed = True
        
        lifecycle.add_shutdown_hook("test_hook", shutdown_hook)
        
        # Test shutdown
        await lifecycle.shutdown()
        
        assert lifecycle.state == LifecycleState.STOPPED
        assert hook_executed
    
    @pytest.mark.asyncio
    async def test_component_lifecycle_error_handling(self) -> None:
        """Test component lifecycle error handling."""
        component = Mock(spec=Component)
        component.name = "test_component"
        component.type = ComponentType.DETECTOR
        
        lifecycle = ComponentLifecycle(component)
        
        # Add failing startup hook
        async def failing_hook() -> None:
            raise RuntimeError("Hook failed")
        
        lifecycle.add_startup_hook("failing_hook", failing_hook)
        
        # Test startup with error
        with pytest.raises(StartupError):
            await lifecycle.startup()
        
        assert lifecycle.state == LifecycleState.ERROR


class TestDependencyOrderer:
    """Test cases for component dependency ordering."""

    def test_dependency_orderer_creation(self) -> None:
        """Test dependency orderer creation."""
        orderer = DependencyOrderer()
        assert orderer.components == []
        assert orderer.dependency_graph == {}

    def test_add_component_dependency(self) -> None:
        """Test adding component dependencies."""
        orderer = DependencyOrderer()

        component_a = Mock(spec=Component)
        component_a.name = "component_a"
        component_b = Mock(spec=Component)
        component_b.name = "component_b"

        orderer.add_component(component_a)
        orderer.add_component(component_b)
        orderer.add_dependency("component_b", "component_a")  # B depends on A

        assert len(orderer.components) == 2
        assert "component_b" in orderer.dependency_graph
        assert "component_a" in orderer.dependency_graph["component_b"]

    def test_topological_sort(self) -> None:
        """Test topological sorting of components."""
        orderer = DependencyOrderer()

        # Create components: A -> B -> C (C depends on B, B depends on A)
        component_a = Mock(spec=Component)
        component_a.name = "component_a"
        component_b = Mock(spec=Component)
        component_b.name = "component_b"
        component_c = Mock(spec=Component)
        component_c.name = "component_c"

        orderer.add_component(component_a)
        orderer.add_component(component_b)
        orderer.add_component(component_c)
        orderer.add_dependency("component_b", "component_a")
        orderer.add_dependency("component_c", "component_b")

        ordered = orderer.get_startup_order()

        # A should come before B, B should come before C
        assert len(ordered) == 3
        assert ordered[0].name == "component_a"
        assert ordered[1].name == "component_b"
        assert ordered[2].name == "component_c"

    def test_circular_dependency_detection(self) -> None:
        """Test circular dependency detection."""
        orderer = DependencyOrderer()

        component_a = Mock(spec=Component)
        component_a.name = "component_a"
        component_b = Mock(spec=Component)
        component_b.name = "component_b"

        orderer.add_component(component_a)
        orderer.add_component(component_b)
        orderer.add_dependency("component_a", "component_b")
        orderer.add_dependency("component_b", "component_a")  # Circular dependency

        with pytest.raises(ValueError, match="Circular dependency detected"):
            _ = orderer.get_startup_order()


class TestHealthCheckManager:
    """Test cases for health check management."""

    def test_health_check_manager_creation(self) -> None:
        """Test health check manager creation."""
        manager = HealthCheckManager()
        assert manager.health_checks == {}
        assert manager.check_interval == 30.0
        assert manager.timeout == 10.0

    def test_register_health_check(self) -> None:
        """Test registering health checks."""
        manager = HealthCheckManager()

        async def test_health_check() -> bool:
            return True

        manager.register_health_check("test_component", test_health_check)

        assert "test_component" in manager.health_checks
        assert manager.health_checks["test_component"] == test_health_check

    @pytest.mark.asyncio
    async def test_run_health_check(self) -> None:
        """Test running individual health checks."""
        manager = HealthCheckManager()

        async def healthy_check() -> bool:
            return True

        async def unhealthy_check() -> bool:
            return False

        manager.register_health_check("healthy_component", healthy_check)
        manager.register_health_check("unhealthy_component", unhealthy_check)

        # Test healthy component
        result = await manager.run_health_check("healthy_component")
        assert result is True

        # Test unhealthy component
        result = await manager.run_health_check("unhealthy_component")
        assert result is False

    @pytest.mark.asyncio
    async def test_run_all_health_checks(self) -> None:
        """Test running all health checks."""
        manager = HealthCheckManager()

        async def healthy_check() -> bool:
            return True

        async def unhealthy_check() -> bool:
            return False

        manager.register_health_check("healthy_component", healthy_check)
        manager.register_health_check("unhealthy_component", unhealthy_check)

        results = await manager.run_all_health_checks()

        assert len(results) == 2
        assert results["healthy_component"] is True
        assert results["unhealthy_component"] is False

    @pytest.mark.asyncio
    async def test_health_check_timeout(self) -> None:
        """Test health check timeout handling."""
        manager = HealthCheckManager(timeout=0.1)

        async def slow_check() -> bool:
            await asyncio.sleep(1.0)
            return True

        manager.register_health_check("slow_component", slow_check)

        result = await manager.run_health_check("slow_component")
        assert result is False  # Should return False on timeout


class TestConfigHotReloader:
    """Test cases for configuration hot reloading."""

    def test_config_hot_reloader_creation(self) -> None:
        """Test config hot reloader creation."""
        config_path = Path("test_config.yaml")
        reloader = ConfigHotReloader(config_path)

        assert reloader.config_path == config_path
        assert reloader.reload_callbacks == []
        assert reloader.watching is False

    def test_register_reload_callback(self) -> None:
        """Test registering reload callbacks."""
        config_path = Path("test_config.yaml")
        reloader = ConfigHotReloader(config_path)

        async def test_callback(config: AppConfig) -> None:  # pyright: ignore[reportUnusedParameter]
            pass

        reloader.register_reload_callback(test_callback)

        assert len(reloader.reload_callbacks) == 1
        assert reloader.reload_callbacks[0] == test_callback

    @pytest.mark.asyncio
    async def test_config_reload_trigger(self) -> None:
        """Test configuration reload triggering."""
        config_path = Path("test_config.yaml")
        reloader = ConfigHotReloader(config_path)

        callback_called = False
        received_config = None

        async def test_callback(config: AppConfig) -> None:
            nonlocal callback_called, received_config
            callback_called = True
            received_config = config

        reloader.register_reload_callback(test_callback)

        # Mock config loading
        mock_config = Mock(spec=AppConfig)
        with patch.object(reloader, '_load_config', return_value=mock_config):
            await reloader._trigger_reload()  # pyright: ignore[reportPrivateUsage]

        assert callback_called
        assert received_config == mock_config


class TestResourceCleanupManager:
    """Test cases for resource cleanup management."""

    def test_resource_cleanup_manager_creation(self) -> None:
        """Test resource cleanup manager creation."""
        manager = ResourceCleanupManager()
        assert manager.cleanup_handlers == []
        assert manager.resources == {}

    def test_register_cleanup_handler(self) -> None:
        """Test registering cleanup handlers."""
        manager = ResourceCleanupManager()

        async def test_cleanup() -> None:
            pass

        manager.register_cleanup_handler("test_resource", test_cleanup)

        assert len(manager.cleanup_handlers) == 1
        assert manager.cleanup_handlers[0][0] == "test_resource"
        assert manager.cleanup_handlers[0][1] == test_cleanup

    @pytest.mark.asyncio
    async def test_cleanup_all_resources(self) -> None:
        """Test cleaning up all resources."""
        manager = ResourceCleanupManager()

        cleanup_called = []

        async def cleanup_a() -> None:
            cleanup_called.append("a")

        async def cleanup_b() -> None:
            cleanup_called.append("b")

        manager.register_cleanup_handler("resource_a", cleanup_a)
        manager.register_cleanup_handler("resource_b", cleanup_b)

        await manager.cleanup_all()

        assert len(cleanup_called) == 2
        assert "a" in cleanup_called
        assert "b" in cleanup_called

    @pytest.mark.asyncio
    async def test_cleanup_specific_resource(self) -> None:
        """Test cleaning up specific resources."""
        manager = ResourceCleanupManager()

        cleanup_called = []

        async def cleanup_a() -> None:
            cleanup_called.append("a")

        async def cleanup_b() -> None:
            cleanup_called.append("b")

        manager.register_cleanup_handler("resource_a", cleanup_a)
        manager.register_cleanup_handler("resource_b", cleanup_b)

        await manager.cleanup_resource("resource_a")

        assert len(cleanup_called) == 1
        assert cleanup_called[0] == "a"


class TestVersionManager:
    """Test cases for version management."""

    def test_version_manager_creation(self) -> None:
        """Test version manager creation."""
        manager = VersionManager()
        assert manager.current_version is None
        assert manager.version_history == []

    def test_set_version(self) -> None:
        """Test setting version."""
        manager = VersionManager()

        manager.set_version("1.0.0")

        assert manager.current_version == "1.0.0"
        assert len(manager.version_history) == 1
        assert manager.version_history[0]["version"] == "1.0.0"

    def test_version_comparison(self) -> None:
        """Test version comparison."""
        manager = VersionManager()

        assert manager.is_version_compatible("1.0.0", "1.0.1")
        assert manager.is_version_compatible("1.0.0", "1.1.0")
        assert not manager.is_version_compatible("1.0.0", "2.0.0")

    def test_version_rollback(self) -> None:
        """Test version rollback."""
        manager = VersionManager()

        manager.set_version("1.0.0")
        manager.set_version("1.1.0")
        manager.set_version("1.2.0")

        # Rollback to previous version
        rolled_back = manager.rollback_to_previous()

        assert rolled_back == "1.1.0"
        assert manager.current_version == "1.1.0"


class TestLifecycleManager:
    """Test cases for the main lifecycle manager."""

    def test_lifecycle_manager_creation(self) -> None:
        """Test lifecycle manager creation."""
        orchestrator = Mock(spec=MonitorOrchestrator)
        manager = LifecycleManager(orchestrator)

        assert manager.orchestrator == orchestrator
        assert manager.state == LifecycleState.UNINITIALIZED
        assert isinstance(manager.dependency_orderer, DependencyOrderer)
        assert isinstance(manager.health_check_manager, HealthCheckManager)
        assert isinstance(manager.cleanup_manager, ResourceCleanupManager)
        assert isinstance(manager.version_manager, VersionManager)

    @pytest.mark.asyncio
    async def test_lifecycle_manager_startup(self) -> None:
        """Test lifecycle manager startup process."""
        orchestrator = Mock(spec=MonitorOrchestrator)
        orchestrator.registry = Mock(spec=ComponentRegistry)
        orchestrator.registry.get_all_components.return_value = []

        manager = LifecycleManager(orchestrator)

        await manager.startup()

        assert manager.state == LifecycleState.RUNNING

    @pytest.mark.asyncio
    async def test_lifecycle_manager_shutdown(self) -> None:
        """Test lifecycle manager shutdown process."""
        orchestrator = Mock(spec=MonitorOrchestrator)
        orchestrator.registry = Mock(spec=ComponentRegistry)
        orchestrator.registry.get_all_components.return_value = []

        manager = LifecycleManager(orchestrator)
        manager.state = LifecycleState.RUNNING

        await manager.shutdown()

        assert manager.state == LifecycleState.STOPPED

    @pytest.mark.asyncio
    async def test_lifecycle_manager_with_components(self) -> None:
        """Test lifecycle manager with actual components."""
        orchestrator = Mock(spec=MonitorOrchestrator)
        orchestrator.registry = Mock(spec=ComponentRegistry)

        # Create mock components
        component_a = Mock(spec=Component)
        component_a.name = "component_a"
        component_a.type = ComponentType.DETECTOR
        component_a.status = ComponentStatus.ACTIVE

        component_b = Mock(spec=Component)
        component_b.name = "component_b"
        component_b.type = ComponentType.CALCULATOR
        component_b.status = ComponentStatus.ACTIVE

        orchestrator.registry.get_all_components.return_value = [component_a, component_b]

        manager = LifecycleManager(orchestrator)

        # Test startup
        await manager.startup()
        assert manager.state == LifecycleState.RUNNING

        # Test shutdown
        await manager.shutdown()
        assert manager.state == LifecycleState.STOPPED

    @pytest.mark.asyncio
    async def test_lifecycle_manager_error_handling(self) -> None:
        """Test lifecycle manager error handling."""
        orchestrator = Mock(spec=MonitorOrchestrator)
        orchestrator.registry = Mock(spec=ComponentRegistry)
        orchestrator.registry.get_all_components.side_effect = RuntimeError("Registry error")

        manager = LifecycleManager(orchestrator)

        with pytest.raises(StartupError):
            await manager.startup()

        assert manager.state == LifecycleState.ERROR

    @pytest.mark.asyncio
    async def test_lifecycle_manager_config_reload(self) -> None:
        """Test lifecycle manager configuration reload."""
        orchestrator = Mock(spec=MonitorOrchestrator)
        orchestrator.registry = Mock(spec=ComponentRegistry)
        orchestrator.registry.get_all_components.return_value = []

        manager = LifecycleManager(orchestrator)
        manager.state = LifecycleState.RUNNING

        # Mock config
        new_config = Mock(spec=AppConfig)

        await manager.reload_configuration(new_config)

        # Should remain running after reload
        assert manager.state == LifecycleState.RUNNING

    @pytest.mark.asyncio
    async def test_lifecycle_manager_health_checks(self) -> None:
        """Test lifecycle manager health check integration."""
        orchestrator = Mock(spec=MonitorOrchestrator)
        orchestrator.registry = Mock(spec=ComponentRegistry)
        orchestrator.registry.get_all_components.return_value = []

        manager = LifecycleManager(orchestrator)
        manager.state = LifecycleState.RUNNING

        # Register a health check
        async def test_health_check() -> bool:
            return True

        manager.health_check_manager.register_health_check("test_component", test_health_check)

        # Run health checks
        results = await manager.run_health_checks()

        assert "test_component" in results
        assert results["test_component"] is True
