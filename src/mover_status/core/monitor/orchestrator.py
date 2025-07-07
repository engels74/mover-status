"""Monitoring orchestrator for component coordination and workflow management."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, override
from abc import ABC, abstractmethod

from .state_machine import StateMachine, MonitorState
from .event_bus import EventBus, Event, EventPriority, EventTopic
from ..process import ProcessDetector, ProcessInfo
from ..progress import ProgressCalculator
from ...notifications.manager import AsyncDispatcher

logger = logging.getLogger(__name__)


class ComponentType(Enum):
    """Types of components that can be registered."""
    
    DETECTOR = auto()
    CALCULATOR = auto()
    DISPATCHER = auto()
    STATE_MACHINE = auto()
    EVENT_BUS = auto()
    CUSTOM = auto()


class ComponentStatus(Enum):
    """Status of individual components."""
    
    IDLE = auto()
    ACTIVE = auto()
    BUSY = auto()
    ERROR = auto()
    SHUTDOWN = auto()


class WorkflowStatus(Enum):
    """Status of workflow execution."""
    
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class ResourceType(Enum):
    """Types of resources that can be allocated."""
    
    MEMORY = auto()
    CPU = auto()
    DISK = auto()
    NETWORK = auto()
    THREAD = auto()


class AllocationStatus(Enum):
    """Status of resource allocation."""
    
    ALLOCATED = auto()
    INSUFFICIENT = auto()
    FAILED = auto()
    RELEASED = auto()


# Custom exceptions
class OrchestratorError(Exception):
    """Base exception for orchestrator errors."""
    pass


class ComponentRegistrationError(OrchestratorError):
    """Exception raised when component registration fails."""
    pass


class WorkflowExecutionError(OrchestratorError):
    """Exception raised when workflow execution fails."""
    pass


class ResourceAllocationError(OrchestratorError):
    """Exception raised when resource allocation fails."""
    pass


class HealthCheckError(OrchestratorError):
    """Exception raised when health check fails."""
    pass


# Component interfaces
class Component(ABC):
    """Base interface for all orchestrator components."""
    
    def __init__(self, name: str, component_type: ComponentType) -> None:
        """Initialize component.
        
        Args:
            name: Component name
            component_type: Type of component
        """
        self.name: str = name
        self.type: ComponentType = component_type
        self.status: ComponentStatus = ComponentStatus.IDLE
    
    @abstractmethod
    def health_check(self) -> bool:
        """Check if component is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        pass
    
    def start(self) -> None:
        """Start the component."""
        self.status = ComponentStatus.ACTIVE
    
    def stop(self) -> None:
        """Stop the component."""
        self.status = ComponentStatus.SHUTDOWN


@dataclass
class WorkflowStep:
    """Represents a single step in a workflow."""
    
    name: str
    dependencies: list[str] = field(default_factory=list)
    execute: Callable[[], bool] = field(default_factory=lambda: lambda: True)
    
    def __post_init__(self) -> None:
        """Validate the workflow step."""
        if not self.name:
            raise ValueError("WorkflowStep name cannot be empty")


@dataclass
class WorkflowResult:
    """Result of workflow step execution."""
    
    step: WorkflowStep
    status: WorkflowStatus
    error_message: str | None = None
    execution_time: float | None = None


@dataclass
class Resource:
    """Represents a system resource."""
    
    name: str
    type: ResourceType
    total: int
    available: int
    
    def __post_init__(self) -> None:
        """Validate resource configuration."""
        if self.available > self.total:
            raise ValueError("Available resources cannot exceed total")


@dataclass
class AllocationResult:
    """Result of resource allocation."""
    
    status: AllocationStatus
    allocated_amount: int
    resource_name: str
    error_message: str | None = None


class ComponentRegistry:
    """Registry for managing orchestrator components."""
    
    def __init__(self) -> None:
        """Initialize the component registry."""
        self.components: dict[str, Component] = {}
        self._components_by_type: dict[ComponentType, list[Component]] = defaultdict(list)
    
    def register(self, component: Component) -> None:
        """Register a component.
        
        Args:
            component: Component to register
            
        Raises:
            ComponentRegistrationError: If component already registered
        """
        if component.name in self.components:
            raise ComponentRegistrationError(f"Component '{component.name}' already registered")
        
        self.components[component.name] = component
        self._components_by_type[component.type].append(component)
        
        logger.info(f"Registered component: {component.name} (type: {component.type.name})")
    
    def unregister(self, name: str) -> None:
        """Unregister a component.
        
        Args:
            name: Name of component to unregister
        """
        if name not in self.components:
            return
        
        component = self.components[name]
        del self.components[name]
        self._components_by_type[component.type].remove(component)
        
        logger.info(f"Unregistered component: {name}")
    
    def get_component(self, name: str) -> Component | None:
        """Get a component by name.
        
        Args:
            name: Component name
            
        Returns:
            Component if found, None otherwise
        """
        return self.components.get(name)
    
    def discover_by_type(self, component_type: ComponentType) -> list[Component]:
        """Discover components by type.
        
        Args:
            component_type: Type of components to find
            
        Returns:
            List of components of the specified type
        """
        return self._components_by_type[component_type].copy()
    
    def get_all_components(self) -> list[Component]:
        """Get all registered components.
        
        Returns:
            List of all components
        """
        return list(self.components.values())


class ServiceHealth:
    """Service health monitoring for orchestrator components."""
    
    def __init__(self) -> None:
        """Initialize the service health monitor."""
        self.health_checks: dict[str, Callable[[], bool]] = {}
    
    def check_component_health(self, component: Component) -> bool:
        """Check health of a specific component.
        
        Args:
            component: Component to check
            
        Returns:
            True if healthy, False otherwise
        """
        try:
            return component.health_check()
        except Exception as e:
            logger.error(f"Health check failed for component {component.name}: {e}")
            return False
    
    def assess_system_health(self, registry: ComponentRegistry) -> dict[str, str | list[str] | int | bool]:
        """Assess overall system health.
        
        Args:
            registry: Component registry
            
        Returns:
            Health assessment report
        """
        components = registry.get_all_components()
        healthy_components: list[str] = []
        unhealthy_components: list[str] = []
        
        for component in components:
            if self.check_component_health(component):
                healthy_components.append(component.name)
            else:
                unhealthy_components.append(component.name)
        
        return {
            "overall_healthy": len(unhealthy_components) == 0,
            "healthy_components": healthy_components,
            "unhealthy_components": unhealthy_components,
            "total_components": len(components)
        }


class WorkflowEngine:
    """Workflow execution engine with dependency resolution."""
    
    def __init__(self) -> None:
        """Initialize the workflow engine."""
        self.workflows: dict[str, list[WorkflowStep]] = {}
    
    def execute_step(self, step: WorkflowStep) -> WorkflowResult:
        """Execute a single workflow step.
        
        Args:
            step: Step to execute
            
        Returns:
            Result of step execution
        """
        logger.debug(f"Executing workflow step: {step.name}")
        
        try:
            success = step.execute()
            status = WorkflowStatus.COMPLETED if success else WorkflowStatus.FAILED
            
            return WorkflowResult(
                step=step,
                status=status,
                error_message=None if success else "Step execution returned False"
            )
        
        except Exception as e:
            logger.error(f"Workflow step {step.name} failed: {e}")
            return WorkflowResult(
                step=step,
                status=WorkflowStatus.FAILED,
                error_message=str(e)
            )
    
    def resolve_dependencies(self, steps: list[WorkflowStep]) -> list[WorkflowStep]:
        """Resolve dependencies between workflow steps.
        
        Args:
            steps: List of workflow steps
            
        Returns:
            Steps ordered by dependencies
        """
        # Create a map of step names to steps
        step_map = {step.name: step for step in steps}
        
        # Topological sort to resolve dependencies
        visited: set[str] = set()
        result: list[WorkflowStep] = []
        
        def visit(step_name: str) -> None:
            if step_name in visited:
                return
            
            visited.add(step_name)
            
            if step_name in step_map:
                step = step_map[step_name]
                # Visit dependencies first
                for dep in step.dependencies:
                    if dep not in visited:
                        visit(dep)
                
                result.append(step)
        
        # Visit all steps
        for step in steps:
            visit(step.name)
        
        return result
    
    def register_workflow(self, name: str, steps: list[WorkflowStep]) -> None:
        """Register a workflow.
        
        Args:
            name: Workflow name
            steps: List of workflow steps
        """
        self.workflows[name] = self.resolve_dependencies(steps)
        logger.info(f"Registered workflow: {name} with {len(steps)} steps")


class ResourceAllocator:
    """Resource allocation and scheduling algorithms."""
    
    def __init__(self) -> None:
        """Initialize the resource allocator."""
        self.resources: dict[str, Resource] = {}
        self.allocations: dict[str, int] = defaultdict(int)
    
    def register_resource(self, resource: Resource) -> None:
        """Register a resource.
        
        Args:
            resource: Resource to register
        """
        self.resources[resource.name] = resource
        logger.info(f"Registered resource: {resource.name} (type: {resource.type.name})")
    
    def allocate(self, resource_name: str, amount: int) -> AllocationResult:
        """Allocate resources.
        
        Args:
            resource_name: Name of resource to allocate
            amount: Amount to allocate
            
        Returns:
            Allocation result
        """
        if resource_name not in self.resources:
            return AllocationResult(
                status=AllocationStatus.FAILED,
                allocated_amount=0,
                resource_name=resource_name,
                error_message=f"Resource '{resource_name}' not found"
            )
        
        resource = self.resources[resource_name]
        
        if resource.available < amount:
            return AllocationResult(
                status=AllocationStatus.INSUFFICIENT,
                allocated_amount=0,
                resource_name=resource_name,
                error_message=f"Insufficient resources (available: {resource.available}, requested: {amount})"
            )
        
        # Allocate resources
        resource.available -= amount
        self.allocations[resource_name] += amount
        
        logger.debug(f"Allocated {amount} units of {resource_name}")
        
        return AllocationResult(
            status=AllocationStatus.ALLOCATED,
            allocated_amount=amount,
            resource_name=resource_name
        )
    
    def deallocate(self, resource_name: str, amount: int) -> None:
        """Deallocate resources.
        
        Args:
            resource_name: Name of resource to deallocate
            amount: Amount to deallocate
        """
        if resource_name not in self.resources:
            return
        
        resource = self.resources[resource_name]
        resource.available += amount
        self.allocations[resource_name] = max(0, self.allocations[resource_name] - amount)
        
        logger.debug(f"Deallocated {amount} units of {resource_name}")


class MonitorOrchestrator:
    """Main monitoring orchestrator that coordinates all subsystem components."""
    
    def __init__(
        self,
        detector: ProcessDetector,
        calculator: ProgressCalculator,
        dispatcher: AsyncDispatcher,
        state_machine: StateMachine,
        event_bus: EventBus
    ) -> None:
        """Initialize the orchestrator.
        
        Args:
            detector: Process detector component
            calculator: Progress calculator component
            dispatcher: Notification dispatcher component
            state_machine: State machine for orchestrator state management
            event_bus: Event bus for inter-component communication
        """
        self.detector: ProcessDetector = detector
        self.calculator: ProgressCalculator = calculator
        self.dispatcher: AsyncDispatcher = dispatcher
        self.state_machine: StateMachine = state_machine
        self.event_bus: EventBus = event_bus
        
        # Initialize coordination subsystems
        self.registry: ComponentRegistry = ComponentRegistry()
        self.workflow_engine: WorkflowEngine = WorkflowEngine()
        self.resource_allocator: ResourceAllocator = ResourceAllocator()
        self.health_monitor: ServiceHealth = ServiceHealth()
        
        # Orchestrator state
        self.running: bool = False
        self.current_process: ProcessInfo | None = None
        self.last_error: Exception | None = None
        
        # Initialize basic workflows
        self._setup_workflows()
    
    def _setup_workflows(self) -> None:
        """Setup basic orchestrator workflows."""
        # Detection workflow
        detection_steps = [
            WorkflowStep(name="initialize_detector", execute=lambda: True),
            WorkflowStep(name="run_detection", execute=lambda: True),
            WorkflowStep(name="validate_process", execute=lambda: True),
        ]
        self.workflow_engine.register_workflow("detection", detection_steps)
        
        # Monitoring workflow
        monitoring_steps = [
            WorkflowStep(name="calculate_progress", execute=lambda: True),
            WorkflowStep(name="update_metrics", execute=lambda: True),
            WorkflowStep(name="check_completion", execute=lambda: True),
        ]
        self.workflow_engine.register_workflow("monitoring", monitoring_steps)
    
    async def startup(self) -> None:
        """Start the orchestrator and register components."""
        logger.info("Starting monitoring orchestrator")
        
        # Register components as wrapper adapters
        self._register_components()
        
        # Initialize resources
        self._initialize_resources()
        
        # Perform health checks
        health_status = self.health_monitor.assess_system_health(self.registry)
        if not health_status["overall_healthy"]:
            logger.warning(f"Some components are unhealthy: {health_status['unhealthy_components']}")
        
        self.running = True
        logger.info("Orchestrator started successfully")
    
    async def shutdown(self) -> None:
        """Shutdown the orchestrator and cleanup resources."""
        logger.info("Shutting down monitoring orchestrator")
        
        self.running = False
        
        # Stop all components
        for component in self.registry.get_all_components():
            component.stop()
        
        logger.info("Orchestrator shutdown complete")
    
    def _register_components(self) -> None:
        """Register all components with the registry."""
        # Create component adapters for existing components
        detector_component = ProcessDetectorAdapter(self.detector)
        calculator_component = ProgressCalculatorAdapter(self.calculator)
        dispatcher_component = DispatcherAdapter(self.dispatcher)
        state_machine_component = StateMachineAdapter(self.state_machine)
        event_bus_component = EventBusAdapter(self.event_bus)
        
        # Register components
        self.registry.register(detector_component)
        self.registry.register(calculator_component)
        self.registry.register(dispatcher_component)
        self.registry.register(state_machine_component)
        self.registry.register(event_bus_component)
    
    def _initialize_resources(self) -> None:
        """Initialize system resources."""
        # Initialize basic resources
        memory_resource = Resource(
            name="memory",
            type=ResourceType.MEMORY,
            total=1024,  # MB
            available=1024
        )
        
        cpu_resource = Resource(
            name="cpu",
            type=ResourceType.CPU,
            total=100,  # percentage
            available=100
        )
        
        self.resource_allocator.register_resource(memory_resource)
        self.resource_allocator.register_resource(cpu_resource)
    
    async def run_detection_cycle(self) -> None:
        """Run the process detection cycle."""
        try:
            # Transition to detecting state
            _ = self.state_machine.transition_to(MonitorState.DETECTING)
            
            # Perform detection
            process = self.detector.detect_mover()
            
            if process:
                self.current_process = process
                logger.info(f"Detected process: {process.name} (PID: {process.pid})")
                
                # Publish process detection event
                event = Event(
                    topic=EventTopic("process.detected"),
                    data={"process": process},
                    priority=EventPriority.HIGH
                )
                self.event_bus.publish_event(event)
                
                # Transition to monitoring state
                _ = self.state_machine.transition_to(MonitorState.MONITORING)
            else:
                # No process detected, stay in idle
                _ = self.state_machine.transition_to(MonitorState.IDLE)
                
        except Exception as e:
            logger.error(f"Detection cycle failed: {e}")
            self.last_error = e
            _ = self.state_machine.transition_to(MonitorState.ERROR)
            
            # Publish error event
            event = Event(
                topic=EventTopic("process.detection.error"),
                data={"error": str(e)},
                priority=EventPriority.CRITICAL
            )
            self.event_bus.publish_event(event)
    
    async def run_monitoring_cycle(self) -> None:
        """Run the process monitoring cycle."""
        if not self.current_process:
            return
        
        try:
            # Calculate progress
            progress = self.calculator.calculate_progress(transferred=0, total=100)
            
            logger.debug(f"Progress: {progress.percentage:.1f}%")
            
            # Publish progress event
            event = Event(
                topic=EventTopic("process.progress"),
                data={"progress": progress},
                priority=EventPriority.NORMAL
            )
            self.event_bus.publish_event(event)
            
            # Check if process is still running
            if not self.detector.is_process_running(self.current_process.pid):
                # Process completed
                _ = self.state_machine.transition_to(MonitorState.COMPLETING)
                
                # Publish completion event
                event = Event(
                    topic=EventTopic("process.completed"),
                    data={"process": self.current_process},
                    priority=EventPriority.HIGH
                )
                self.event_bus.publish_event(event)
                
                self.current_process = None
                _ = self.state_machine.transition_to(MonitorState.IDLE)
                
        except Exception as e:
            logger.error(f"Monitoring cycle failed: {e}")
            self.last_error = e
            _ = self.state_machine.transition_to(MonitorState.ERROR)
            
            # Publish error event
            event = Event(
                topic=EventTopic("process.monitoring.error"),
                data={"error": str(e)},
                priority=EventPriority.CRITICAL
            )
            self.event_bus.publish_event(event)


# Component adapters to wrap existing components
class ProcessDetectorAdapter(Component):
    """Adapter for ProcessDetector component."""
    
    def __init__(self, detector: ProcessDetector) -> None:
        """Initialize adapter."""
        super().__init__("process_detector", ComponentType.DETECTOR)
        self.detector: ProcessDetector = detector
    
    @override
    def health_check(self) -> bool:
        """Check if detector is healthy."""
        # Simple health check - try to detect processes
        try:
            _ = self.detector.detect_mover()
            return True
        except Exception:
            return False


class ProgressCalculatorAdapter(Component):
    """Adapter for ProgressCalculator component."""
    
    def __init__(self, calculator: ProgressCalculator) -> None:
        """Initialize adapter."""
        super().__init__("progress_calculator", ComponentType.CALCULATOR)
        self.calculator: ProgressCalculator = calculator
    
    @override
    def health_check(self) -> bool:
        """Check if calculator is healthy."""
        # Simple health check - calculator should always be healthy
        return True


class DispatcherAdapter(Component):
    """Adapter for AsyncDispatcher component."""
    
    def __init__(self, dispatcher: AsyncDispatcher) -> None:
        """Initialize adapter."""
        super().__init__("notification_dispatcher", ComponentType.DISPATCHER)
        self.dispatcher: AsyncDispatcher = dispatcher
    
    @override
    def health_check(self) -> bool:
        """Check if dispatcher is healthy."""
        # Simple health check - dispatcher should always be healthy
        return True


class StateMachineAdapter(Component):
    """Adapter for StateMachine component."""
    
    def __init__(self, state_machine: StateMachine) -> None:
        """Initialize adapter."""
        super().__init__("state_machine", ComponentType.STATE_MACHINE)
        self.state_machine: StateMachine = state_machine
    
    @override
    def health_check(self) -> bool:
        """Check if state machine is healthy."""
        # Simple health check - state machine should always be healthy
        return True


class EventBusAdapter(Component):
    """Adapter for EventBus component."""
    
    def __init__(self, event_bus: EventBus) -> None:
        """Initialize adapter."""
        super().__init__("event_bus", ComponentType.EVENT_BUS)
        self.event_bus: EventBus = event_bus
    
    @override
    def health_check(self) -> bool:
        """Check if event bus is healthy."""
        # Simple health check - event bus should always be healthy
        return True