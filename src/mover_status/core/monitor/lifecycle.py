"""Lifecycle management system for monitoring orchestrator components."""

from __future__ import annotations

import asyncio
import logging
import time
import threading
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .orchestrator import MonitorOrchestrator, Component
    from ...config.models.main import AppConfig

logger = logging.getLogger(__name__)


class LifecycleState(Enum):
    """Lifecycle states for components and orchestrator."""
    
    UNINITIALIZED = auto()
    INITIALIZING = auto()
    INITIALIZED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    STOPPED = auto()
    ERROR = auto()
    RELOADING = auto()


class LifecycleError(Exception):
    """Base exception for lifecycle management errors."""
    pass


class StartupError(LifecycleError):
    """Exception raised during component startup."""
    pass


class ShutdownError(LifecycleError):
    """Exception raised during component shutdown."""
    pass


class ConfigReloadError(LifecycleError):
    """Exception raised during configuration reload."""
    pass


@dataclass
class LifecycleEvent:
    """Event representing a lifecycle state change."""
    
    event_type: str
    component_name: str
    timestamp: float
    data: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Convert event to dictionary representation."""
        return {
            "event_type": self.event_type,
            "component_name": self.component_name,
            "timestamp": self.timestamp,
            "data": self.data
        }


@dataclass
class LifecycleHook:
    """Hook for lifecycle events."""
    
    name: str
    callback: Callable[[], Awaitable[None]]
    priority: int = 0
    timeout: float = 30.0
    
    async def execute(self) -> None:
        """Execute the lifecycle hook with timeout."""
        try:
            await asyncio.wait_for(self.callback(), timeout=self.timeout)
        except asyncio.TimeoutError:
            logger.error(f"Lifecycle hook '{self.name}' timed out after {self.timeout}s")
            raise
        except Exception as e:
            logger.error(f"Lifecycle hook '{self.name}' failed: {e}")
            raise


class ComponentLifecycle:
    """Manages the lifecycle of individual components."""
    
    def __init__(self, component: Component) -> None:
        """Initialize component lifecycle manager.
        
        Args:
            component: Component to manage
        """
        self.component: Component = component
        self.state: LifecycleState = LifecycleState.UNINITIALIZED
        self.dependencies: list[str] = []
        self.startup_hooks: list[LifecycleHook] = []
        self.shutdown_hooks: list[LifecycleHook] = []
        self._lock: threading.RLock = threading.RLock()
    
    def add_dependency(self, dependency_name: str) -> None:
        """Add a dependency for this component.
        
        Args:
            dependency_name: Name of the dependency component
        """
        with self._lock:
            if dependency_name not in self.dependencies:
                self.dependencies.append(dependency_name)
    
    def add_startup_hook(self, name: str, callback: Callable[[], Awaitable[None]], 
                        priority: int = 0, timeout: float = 30.0) -> None:
        """Add a startup hook.
        
        Args:
            name: Hook name
            callback: Async callback function
            priority: Hook priority (higher runs first)
            timeout: Hook timeout in seconds
        """
        hook = LifecycleHook(name=name, callback=callback, priority=priority, timeout=timeout)
        with self._lock:
            self.startup_hooks.append(hook)
            self.startup_hooks.sort(key=lambda h: h.priority, reverse=True)
    
    def add_shutdown_hook(self, name: str, callback: Callable[[], Awaitable[None]], 
                         priority: int = 0, timeout: float = 30.0) -> None:
        """Add a shutdown hook.
        
        Args:
            name: Hook name
            callback: Async callback function
            priority: Hook priority (higher runs first)
            timeout: Hook timeout in seconds
        """
        hook = LifecycleHook(name=name, callback=callback, priority=priority, timeout=timeout)
        with self._lock:
            self.shutdown_hooks.append(hook)
            self.shutdown_hooks.sort(key=lambda h: h.priority, reverse=True)
    
    async def startup(self) -> None:
        """Start the component and execute startup hooks."""
        with self._lock:
            if self.state != LifecycleState.UNINITIALIZED:
                logger.warning(f"Component {self.component.name} already started")
                return
            
            self.state = LifecycleState.STARTING
        
        try:
            logger.info(f"Starting component: {self.component.name}")
            
            # Execute startup hooks
            for hook in self.startup_hooks:
                try:
                    await hook.execute()
                    logger.debug(f"Executed startup hook '{hook.name}' for {self.component.name}")
                except Exception as e:
                    logger.error(f"Startup hook '{hook.name}' failed for {self.component.name}: {e}")
                    with self._lock:
                        self.state = LifecycleState.ERROR
                    raise StartupError(f"Startup hook '{hook.name}' failed: {e}") from e
            
            with self._lock:
                self.state = LifecycleState.RUNNING
            
            logger.info(f"Component {self.component.name} started successfully")
            
        except Exception as e:
            with self._lock:
                self.state = LifecycleState.ERROR
            logger.error(f"Failed to start component {self.component.name}: {e}")
            raise StartupError(f"Failed to start component {self.component.name}") from e
    
    async def shutdown(self) -> None:
        """Shutdown the component and execute shutdown hooks."""
        with self._lock:
            if self.state not in (LifecycleState.RUNNING, LifecycleState.ERROR):
                logger.warning(f"Component {self.component.name} not running")
                return
            
            self.state = LifecycleState.STOPPING
        
        try:
            logger.info(f"Stopping component: {self.component.name}")
            
            # Execute shutdown hooks in reverse order
            for hook in reversed(self.shutdown_hooks):
                try:
                    await hook.execute()
                    logger.debug(f"Executed shutdown hook '{hook.name}' for {self.component.name}")
                except Exception as e:
                    logger.error(f"Shutdown hook '{hook.name}' failed for {self.component.name}: {e}")
                    # Continue with other hooks even if one fails
            
            with self._lock:
                self.state = LifecycleState.STOPPED
            
            logger.info(f"Component {self.component.name} stopped successfully")
            
        except Exception as e:
            with self._lock:
                self.state = LifecycleState.ERROR
            logger.error(f"Failed to stop component {self.component.name}: {e}")
            raise ShutdownError(f"Failed to stop component {self.component.name}") from e


class DependencyOrderer:
    """Orders components based on their dependencies using topological sorting."""

    def __init__(self) -> None:
        """Initialize dependency orderer."""
        self.components: list[Component] = []
        self.dependency_graph: dict[str, list[str]] = defaultdict(list)

    def add_component(self, component: Component) -> None:
        """Add a component to the orderer.

        Args:
            component: Component to add
        """
        if component not in self.components:
            self.components.append(component)

    def add_dependency(self, component_name: str, dependency_name: str) -> None:
        """Add a dependency relationship.

        Args:
            component_name: Name of the component that depends on another
            dependency_name: Name of the dependency component
        """
        self.dependency_graph[component_name].append(dependency_name)

    def get_startup_order(self) -> list[Component]:
        """Get components in startup order (dependencies first).

        Returns:
            List of components in startup order

        Raises:
            ValueError: If circular dependencies are detected
        """
        # Create a mapping from name to component
        component_map = {comp.name: comp for comp in self.components}

        # Topological sort using Kahn's algorithm
        in_degree: dict[str, int] = defaultdict(int)

        # Initialize in-degrees for all components
        for component in self.components:
            in_degree[component.name] = 0

        # Calculate in-degrees based on dependencies
        for component_name in self.dependency_graph:
            for _ in self.dependency_graph[component_name]:
                in_degree[component_name] += 1

        # Initialize queue with components that have no dependencies
        queue: list[str] = []
        for component in self.components:
            if in_degree[component.name] == 0:
                queue.append(component.name)

        result: list[Component] = []

        while queue:
            current = queue.pop(0)
            result.append(component_map[current])

            # For each component that depends on the current component
            for dependent_name in self.dependency_graph:
                if current in self.dependency_graph[dependent_name]:
                    in_degree[dependent_name] -= 1
                    if in_degree[dependent_name] == 0:
                        queue.append(dependent_name)

        # Check for circular dependencies
        if len(result) != len(self.components):
            raise ValueError("Circular dependency detected")

        return result

    def get_shutdown_order(self) -> list[Component]:
        """Get components in shutdown order (reverse of startup order).

        Returns:
            List of components in shutdown order
        """
        return list(reversed(self.get_startup_order()))


class HealthCheckManager:
    """Manages health checks for components."""

    def __init__(self, check_interval: float = 30.0, timeout: float = 10.0) -> None:
        """Initialize health check manager.

        Args:
            check_interval: Interval between health checks in seconds
            timeout: Timeout for individual health checks in seconds
        """
        self.health_checks: dict[str, Callable[[], Awaitable[bool]]] = {}
        self.check_interval: float = check_interval
        self.timeout: float = timeout
        self._running: bool = False
        self._task: asyncio.Task[None] | None = None

    def register_health_check(self, component_name: str,
                            health_check: Callable[[], Awaitable[bool]]) -> None:
        """Register a health check for a component.

        Args:
            component_name: Name of the component
            health_check: Async function that returns True if healthy
        """
        self.health_checks[component_name] = health_check
        logger.debug(f"Registered health check for component: {component_name}")

    async def run_health_check(self, component_name: str) -> bool:
        """Run health check for a specific component.

        Args:
            component_name: Name of the component

        Returns:
            True if healthy, False otherwise
        """
        if component_name not in self.health_checks:
            logger.warning(f"No health check registered for component: {component_name}")
            return False

        try:
            health_check = self.health_checks[component_name]
            result = await asyncio.wait_for(health_check(), timeout=self.timeout)
            logger.debug(f"Health check for {component_name}: {'healthy' if result else 'unhealthy'}")
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Health check for {component_name} timed out")
            return False
        except Exception as e:
            logger.error(f"Health check for {component_name} failed: {e}")
            return False

    async def run_all_health_checks(self) -> dict[str, bool]:
        """Run health checks for all registered components.

        Returns:
            Dictionary mapping component names to health status
        """
        results: dict[str, bool] = {}

        for component_name in self.health_checks:
            results[component_name] = await self.run_health_check(component_name)

        return results

    async def start_monitoring(self) -> None:
        """Start continuous health monitoring."""
        if self._running:
            logger.warning("Health monitoring already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())
        logger.info("Started health monitoring")

    async def stop_monitoring(self) -> None:
        """Stop continuous health monitoring."""
        if not self._running:
            return

        self._running = False
        if self._task:
            _ = self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped health monitoring")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                results = await self.run_all_health_checks()

                # Log unhealthy components
                unhealthy = [name for name, healthy in results.items() if not healthy]
                if unhealthy:
                    logger.warning(f"Unhealthy components detected: {unhealthy}")

                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)


class ConfigHotReloader:
    """Manages hot reloading of configuration files."""

    def __init__(self, config_path: Path) -> None:
        """Initialize config hot reloader.

        Args:
            config_path: Path to the configuration file
        """
        self.config_path: Path = config_path
        self.reload_callbacks: list[Callable[[AppConfig], Awaitable[None]]] = []
        self.watching: bool = False
        self._last_modified: float = 0.0
        self._task: asyncio.Task[None] | None = None

    def register_reload_callback(self, callback: Callable[[AppConfig], Awaitable[None]]) -> None:
        """Register a callback for configuration reloads.

        Args:
            callback: Async callback function that receives the new config
        """
        self.reload_callbacks.append(callback)
        logger.debug("Registered config reload callback")

    async def start_watching(self) -> None:
        """Start watching the configuration file for changes."""
        if self.watching:
            logger.warning("Config file watching already started")
            return

        self.watching = True
        if self.config_path.exists():
            self._last_modified = self.config_path.stat().st_mtime

        self._task = asyncio.create_task(self._watch_loop())
        logger.info(f"Started watching config file: {self.config_path}")

    async def stop_watching(self) -> None:
        """Stop watching the configuration file."""
        if not self.watching:
            return

        self.watching = False
        if self._task:
            _ = self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped watching config file")

    async def _watch_loop(self) -> None:
        """Main file watching loop."""
        while self.watching:
            try:
                if self.config_path.exists():
                    current_modified = self.config_path.stat().st_mtime
                    if current_modified > self._last_modified:
                        logger.info("Configuration file changed, triggering reload")
                        self._last_modified = current_modified
                        await self._trigger_reload()

                await asyncio.sleep(1.0)  # Check every second

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in config watch loop: {e}")
                await asyncio.sleep(5.0)  # Wait longer on error

    async def _trigger_reload(self) -> None:
        """Trigger configuration reload."""
        try:
            new_config = self._load_config()

            for callback in self.reload_callbacks:
                try:
                    await callback(new_config)
                except Exception as e:
                    logger.error(f"Config reload callback failed: {e}")

            logger.info("Configuration reloaded successfully")

        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            raise ConfigReloadError(f"Failed to reload configuration: {e}") from e

    def _load_config(self) -> AppConfig:
        """Load configuration from file.

        Returns:
            Loaded configuration
        """
        # This is a placeholder - in real implementation, would use the config loader
        from ...config.models.main import AppConfig
        from ...config.models.monitoring import ProcessConfig
        return AppConfig(process=ProcessConfig(name="mover", paths=["/mnt/user"]))


class ResourceCleanupManager:
    """Manages cleanup of system resources."""

    def __init__(self) -> None:
        """Initialize resource cleanup manager."""
        self.cleanup_handlers: list[tuple[str, Callable[[], Awaitable[None]]]] = []
        self.resources: dict[str, object] = {}

    def register_cleanup_handler(self, resource_name: str,
                                cleanup_handler: Callable[[], Awaitable[None]]) -> None:
        """Register a cleanup handler for a resource.

        Args:
            resource_name: Name of the resource
            cleanup_handler: Async cleanup function
        """
        self.cleanup_handlers.append((resource_name, cleanup_handler))
        logger.debug(f"Registered cleanup handler for resource: {resource_name}")

    def register_resource(self, name: str, resource: object) -> None:
        """Register a resource for tracking.

        Args:
            name: Resource name
            resource: Resource object
        """
        self.resources[name] = resource
        logger.debug(f"Registered resource: {name}")

    async def cleanup_resource(self, resource_name: str) -> None:
        """Clean up a specific resource.

        Args:
            resource_name: Name of the resource to clean up
        """
        for name, handler in self.cleanup_handlers:
            if name == resource_name:
                try:
                    await handler()
                    logger.debug(f"Cleaned up resource: {resource_name}")
                except Exception as e:
                    logger.error(f"Failed to clean up resource {resource_name}: {e}")
                break

        # Remove from tracked resources
        if resource_name in self.resources:
            del self.resources[resource_name]

    async def cleanup_all(self) -> None:
        """Clean up all registered resources."""
        logger.info("Starting cleanup of all resources")

        # Clean up in reverse order of registration
        for resource_name, handler in reversed(self.cleanup_handlers):
            try:
                await handler()
                logger.debug(f"Cleaned up resource: {resource_name}")
            except Exception as e:
                logger.error(f"Failed to clean up resource {resource_name}: {e}")

        # Clear all tracked resources
        self.resources.clear()
        logger.info("Completed cleanup of all resources")


class VersionManager:
    """Manages version information and compatibility."""

    def __init__(self) -> None:
        """Initialize version manager."""
        self.current_version: str | None = None
        self.version_history: list[dict[str, object]] = []

    def set_version(self, version: str) -> None:
        """Set the current version.

        Args:
            version: Version string
        """
        self.current_version = version
        self.version_history.append({
            "version": version,
            "timestamp": time.time()
        })
        logger.info(f"Set version to: {version}")

    def is_version_compatible(self, version1: str, version2: str) -> bool:
        """Check if two versions are compatible.

        Args:
            version1: First version
            version2: Second version

        Returns:
            True if versions are compatible
        """
        # Simple compatibility check - same major version
        try:
            v1_parts = version1.split('.')
            v2_parts = version2.split('.')

            if len(v1_parts) >= 1 and len(v2_parts) >= 1:
                return v1_parts[0] == v2_parts[0]

            return False
        except Exception:
            return False

    def rollback_to_previous(self) -> str | None:
        """Rollback to the previous version.

        Returns:
            Previous version string, or None if no previous version
        """
        if len(self.version_history) < 2:
            return None

        # Remove current version and get previous
        _ = self.version_history.pop()
        previous = self.version_history[-1]
        version_obj = previous.get("version")
        if isinstance(version_obj, str):
            self.current_version = version_obj
        else:
            self.current_version = None

        logger.info(f"Rolled back to version: {self.current_version}")
        return self.current_version


class LifecycleEventBus:
    """Event bus for lifecycle events."""

    def __init__(self) -> None:
        """Initialize lifecycle event bus."""
        self.subscribers: list[Callable[[LifecycleEvent], Awaitable[None]]] = []

    def subscribe(self, callback: Callable[[LifecycleEvent], Awaitable[None]]) -> None:
        """Subscribe to lifecycle events.

        Args:
            callback: Async callback function
        """
        self.subscribers.append(callback)

    async def publish(self, event: LifecycleEvent) -> None:
        """Publish a lifecycle event.

        Args:
            event: Event to publish
        """
        for subscriber in self.subscribers:
            try:
                await subscriber(event)
            except Exception as e:
                logger.error(f"Lifecycle event subscriber failed: {e}")


class LifecycleManager:
    """Main lifecycle manager for the monitoring orchestrator."""

    def __init__(self, orchestrator: MonitorOrchestrator) -> None:
        """Initialize lifecycle manager.

        Args:
            orchestrator: Orchestrator instance to manage
        """
        self.orchestrator: MonitorOrchestrator = orchestrator
        self.state: LifecycleState = LifecycleState.UNINITIALIZED

        # Initialize subsystems
        self.dependency_orderer: DependencyOrderer = DependencyOrderer()
        self.health_check_manager: HealthCheckManager = HealthCheckManager()
        self.config_reloader: ConfigHotReloader | None = None
        self.cleanup_manager: ResourceCleanupManager = ResourceCleanupManager()
        self.version_manager: VersionManager = VersionManager()
        self.event_bus: LifecycleEventBus = LifecycleEventBus()

        # Component lifecycles
        self.component_lifecycles: dict[str, ComponentLifecycle] = {}

        # Lock for thread safety
        self._lock: threading.RLock = threading.RLock()

    async def startup(self) -> None:
        """Start the orchestrator and all components."""
        with self._lock:
            if self.state != LifecycleState.UNINITIALIZED:
                logger.warning("Lifecycle manager already started")
                return

            self.state = LifecycleState.STARTING

        try:
            logger.info("Starting lifecycle manager")

            # Initialize component lifecycles
            await self._initialize_component_lifecycles()

            # Start components in dependency order
            await self._start_components()

            # Start health monitoring
            await self.health_check_manager.start_monitoring()

            # Start config watching if configured
            if self.config_reloader:
                await self.config_reloader.start_watching()

            with self._lock:
                self.state = LifecycleState.RUNNING

            # Publish startup event
            event = LifecycleEvent(
                event_type="orchestrator_started",
                component_name="lifecycle_manager",
                timestamp=time.time()
            )
            await self.event_bus.publish(event)

            logger.info("Lifecycle manager started successfully")

        except Exception as e:
            with self._lock:
                self.state = LifecycleState.ERROR
            logger.error(f"Failed to start lifecycle manager: {e}")
            raise StartupError(f"Failed to start lifecycle manager: {e}") from e

    async def shutdown(self) -> None:
        """Shutdown the orchestrator and all components."""
        with self._lock:
            if self.state not in (LifecycleState.RUNNING, LifecycleState.ERROR):
                logger.warning("Lifecycle manager not running")
                return

            self.state = LifecycleState.STOPPING

        try:
            logger.info("Stopping lifecycle manager")

            # Stop config watching
            if self.config_reloader:
                await self.config_reloader.stop_watching()

            # Stop health monitoring
            await self.health_check_manager.stop_monitoring()

            # Stop components in reverse dependency order
            await self._stop_components()

            # Clean up resources
            await self.cleanup_manager.cleanup_all()

            with self._lock:
                self.state = LifecycleState.STOPPED

            # Publish shutdown event
            event = LifecycleEvent(
                event_type="orchestrator_stopped",
                component_name="lifecycle_manager",
                timestamp=time.time()
            )
            await self.event_bus.publish(event)

            logger.info("Lifecycle manager stopped successfully")

        except Exception as e:
            with self._lock:
                self.state = LifecycleState.ERROR
            logger.error(f"Failed to stop lifecycle manager: {e}")
            raise ShutdownError(f"Failed to stop lifecycle manager: {e}") from e

    async def reload_configuration(self, new_config: AppConfig) -> None:
        """Reload configuration.

        Args:
            new_config: New configuration to apply
        """
        with self._lock:
            if self.state != LifecycleState.RUNNING:
                logger.warning("Cannot reload config - lifecycle manager not running")
                return

            self.state = LifecycleState.RELOADING

        try:
            logger.info("Reloading configuration")

            # Publish config reload event
            event = LifecycleEvent(
                event_type="config_reloading",
                component_name="lifecycle_manager",
                timestamp=time.time(),
                data={"config": new_config}
            )
            await self.event_bus.publish(event)

            # TODO: Apply configuration changes to components

            with self._lock:
                self.state = LifecycleState.RUNNING

            logger.info("Configuration reloaded successfully")

        except Exception as e:
            with self._lock:
                self.state = LifecycleState.ERROR
            logger.error(f"Failed to reload configuration: {e}")
            raise ConfigReloadError(f"Failed to reload configuration: {e}") from e

    async def run_health_checks(self) -> dict[str, bool]:
        """Run health checks for all components.

        Returns:
            Dictionary mapping component names to health status
        """
        return await self.health_check_manager.run_all_health_checks()

    def set_config_path(self, config_path: Path) -> None:
        """Set configuration file path for hot reloading.

        Args:
            config_path: Path to configuration file
        """
        self.config_reloader = ConfigHotReloader(config_path)

        # Register reload callback
        self.config_reloader.register_reload_callback(self.reload_configuration)

    async def _initialize_component_lifecycles(self) -> None:
        """Initialize lifecycle management for all components."""
        components = self.orchestrator.registry.get_all_components()

        for component in components:
            lifecycle = ComponentLifecycle(component)
            self.component_lifecycles[component.name] = lifecycle

            # Add component to dependency orderer
            self.dependency_orderer.add_component(component)

            # Register default health check
            async def default_health_check() -> bool:
                return component.status.name == "ACTIVE"

            self.health_check_manager.register_health_check(
                component.name,
                default_health_check
            )

        logger.info(f"Initialized {len(components)} component lifecycles")

    async def _start_components(self) -> None:
        """Start components in dependency order."""
        try:
            ordered_components = self.dependency_orderer.get_startup_order()

            for component in ordered_components:
                lifecycle = self.component_lifecycles[component.name]
                await lifecycle.startup()

                # Publish component started event
                event = LifecycleEvent(
                    event_type="component_started",
                    component_name=component.name,
                    timestamp=time.time()
                )
                await self.event_bus.publish(event)

            logger.info(f"Started {len(ordered_components)} components")

        except Exception as e:
            logger.error(f"Failed to start components: {e}")
            raise

    async def _stop_components(self) -> None:
        """Stop components in reverse dependency order."""
        try:
            ordered_components = self.dependency_orderer.get_shutdown_order()

            for component in ordered_components:
                lifecycle = self.component_lifecycles[component.name]
                await lifecycle.shutdown()

                # Publish component stopped event
                event = LifecycleEvent(
                    event_type="component_stopped",
                    component_name=component.name,
                    timestamp=time.time()
                )
                await self.event_bus.publish(event)

            logger.info(f"Stopped {len(ordered_components)} components")

        except Exception as e:
            logger.error(f"Failed to stop components: {e}")
            raise
