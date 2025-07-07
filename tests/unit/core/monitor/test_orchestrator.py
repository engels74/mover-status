"""Test cases for the monitoring orchestrator component coordination logic."""

from __future__ import annotations

import pytest
from unittest.mock import Mock, AsyncMock
from typing import cast

from mover_status.core.monitor.orchestrator import (
    MonitorOrchestrator,
    ComponentRegistry,
    ServiceHealth,
    WorkflowEngine,
    ResourceAllocator,
    Component,
    ComponentType,
    ComponentStatus,
    WorkflowStep,
    WorkflowStatus,
    Resource,
    ResourceType,
    AllocationStatus,
    ComponentRegistrationError,
)
from mover_status.core.monitor.state_machine import MonitorState, StateMachine
from mover_status.core.monitor.event_bus import EventBus
from mover_status.core.process import ProcessDetector, ProcessInfo, ProcessStatus
from mover_status.core.progress import ProgressCalculator, ProgressMetrics
from mover_status.notifications.manager import AsyncDispatcher


class TestComponentRegistry:
    """Test component registration and discovery mechanisms."""
    
    def test_component_registration(self) -> None:
        """Test registering components with the registry."""
        registry = ComponentRegistry()
        
        # Create mock component
        component = Mock(spec=Component)
        component.name = "test_component"
        component.type = ComponentType.DETECTOR
        component.status = ComponentStatus.IDLE
        component.health_check = Mock(return_value=True)
        
        # Register component
        registry.register(component)
        
        # Verify registration
        assert "test_component" in registry.components
        assert registry.components["test_component"] == component
        assert registry.get_component("test_component") == component
    
    def test_component_discovery(self) -> None:
        """Test discovering components by type."""
        registry = ComponentRegistry()
        
        # Create mock components
        detector = Mock(spec=Component)
        detector.name = "detector"
        detector.type = ComponentType.DETECTOR
        
        calculator = Mock(spec=Component)
        calculator.name = "calculator"
        calculator.type = ComponentType.CALCULATOR
        
        registry.register(detector)
        registry.register(calculator)
        
        # Test discovery
        detectors = registry.discover_by_type(ComponentType.DETECTOR)
        calculators = registry.discover_by_type(ComponentType.CALCULATOR)
        
        assert len(detectors) == 1
        assert len(calculators) == 1
        assert detectors[0] == detector
        assert calculators[0] == calculator
    
    def test_component_unregistration(self) -> None:
        """Test unregistering components."""
        registry = ComponentRegistry()
        
        component = Mock(spec=Component)
        component.name = "test_component"
        component.type = ComponentType.DETECTOR
        
        registry.register(component)
        assert "test_component" in registry.components
        
        registry.unregister("test_component")
        assert "test_component" not in registry.components
        assert registry.get_component("test_component") is None
    
    def test_duplicate_registration_error(self) -> None:
        """Test error when registering duplicate components."""
        registry = ComponentRegistry()
        
        component = Mock(spec=Component)
        component.name = "test_component"
        component.type = ComponentType.DETECTOR
        
        registry.register(component)
        
        with pytest.raises(ComponentRegistrationError):
            registry.register(component)


class TestServiceHealth:
    """Test service health monitoring."""
    
    def test_health_check_success(self) -> None:
        """Test successful health check."""
        health_monitor = ServiceHealth()
        
        # Create mock component
        component = Mock(spec=Component)
        component.name = "test_component"
        component.health_check = Mock(return_value=True)
        
        # Check health
        result = health_monitor.check_component_health(component)
        
        assert result is True
        component.health_check.assert_called_once()  # pyright: ignore[reportAny]
    
    def test_health_check_failure(self) -> None:
        """Test health check failure."""
        health_monitor = ServiceHealth()
        
        # Create mock component that fails health check
        component = Mock(spec=Component)
        component.name = "test_component"
        component.health_check = Mock(side_effect=Exception("Health check failed"))
        
        # Check health
        result = health_monitor.check_component_health(component)
        
        assert result is False
        component.health_check.assert_called_once()  # pyright: ignore[reportAny]
    
    def test_overall_health_assessment(self) -> None:
        """Test overall system health assessment."""
        health_monitor = ServiceHealth()
        
        # Create mock registry with components
        registry = Mock(spec=ComponentRegistry)
        
        healthy_component = Mock(spec=Component)
        healthy_component.name = "healthy"
        healthy_component.health_check = Mock(return_value=True)
        
        unhealthy_component = Mock(spec=Component)
        unhealthy_component.name = "unhealthy"
        unhealthy_component.health_check = Mock(side_effect=Exception("Failed"))
        
        registry.get_all_components = Mock(return_value=[healthy_component, unhealthy_component])
        
        # Check overall health
        health_status = health_monitor.assess_system_health(registry)
        
        assert health_status["overall_healthy"] is False
        assert health_status["healthy_components"] == ["healthy"]
        assert health_status["unhealthy_components"] == ["unhealthy"]
        assert health_status["total_components"] == 2


class TestWorkflowEngine:
    """Test workflow execution engine with dependency resolution."""
    
    def test_workflow_step_execution(self) -> None:
        """Test executing individual workflow steps."""
        engine = WorkflowEngine()
        
        # Create mock step
        step = Mock(spec=WorkflowStep)
        step.name = "test_step"
        step.dependencies = []
        step.execute = Mock(return_value=True)
        
        # Execute step
        result = engine.execute_step(step)
        
        assert result.status == WorkflowStatus.COMPLETED
        assert result.step == step
        step.execute.assert_called_once()
    
    def test_workflow_dependency_resolution(self) -> None:
        """Test resolving workflow step dependencies."""
        engine = WorkflowEngine()
        
        # Create steps with dependencies
        step1 = Mock(spec=WorkflowStep)
        step1.name = "step1"
        step1.dependencies = []
        step1.execute = Mock(return_value=True)
        
        step2 = Mock(spec=WorkflowStep)
        step2.name = "step2"
        step2.dependencies = ["step1"]
        step2.execute = Mock(return_value=True)
        
        steps = cast(list[WorkflowStep], [step2, step1])  # Intentionally out of order
        
        # Resolve dependencies
        ordered_steps = engine.resolve_dependencies(steps)
        
        assert len(ordered_steps) == 2
        assert ordered_steps[0].name == "step1"
        assert ordered_steps[1].name == "step2"
    
    def test_workflow_execution_with_failure(self) -> None:
        """Test workflow execution with step failure."""
        engine = WorkflowEngine()
        
        # Create failing step
        step = Mock(spec=WorkflowStep)
        step.name = "failing_step"
        step.dependencies = []
        step.execute = Mock(side_effect=Exception("Step failed"))
        
        # Execute step
        result = engine.execute_step(step)
        
        assert result.status == WorkflowStatus.FAILED
        assert result.step == step
        assert result.error_message == "Step failed"


class TestResourceAllocator:
    """Test resource allocation and scheduling algorithms."""
    
    def test_resource_allocation(self) -> None:
        """Test basic resource allocation."""
        allocator = ResourceAllocator()
        
        # Create mock resource
        resource = Mock(spec=Resource)
        resource.name = "test_resource"
        resource.type = ResourceType.MEMORY
        resource.available = 100
        resource.total = 100
        
        allocator.register_resource(resource)
        
        # Allocate resource
        result = allocator.allocate("test_resource", 50)
        
        assert result.status == AllocationStatus.ALLOCATED
        assert result.allocated_amount == 50
        assert resource.available == 50  # pyright: ignore[reportAny]
    
    def test_resource_allocation_insufficient(self) -> None:
        """Test resource allocation when insufficient resources."""
        allocator = ResourceAllocator()
        
        # Create mock resource
        resource = Mock(spec=Resource)
        resource.name = "test_resource"
        resource.type = ResourceType.MEMORY
        resource.available = 30
        resource.total = 100
        
        allocator.register_resource(resource)
        
        # Try to allocate more than available
        result = allocator.allocate("test_resource", 50)
        
        assert result.status == AllocationStatus.INSUFFICIENT
        assert result.allocated_amount == 0
        assert resource.available == 30  # Unchanged  # pyright: ignore[reportAny]
    
    def test_resource_deallocation(self) -> None:
        """Test resource deallocation."""
        allocator = ResourceAllocator()
        
        # Create mock resource
        resource = Mock(spec=Resource)
        resource.name = "test_resource"
        resource.type = ResourceType.MEMORY
        resource.available = 50
        resource.total = 100
        
        allocator.register_resource(resource)
        
        # Deallocate resource
        allocator.deallocate("test_resource", 20)
        
        assert resource.available == 70


class TestMonitorOrchestrator:
    """Test the main monitoring orchestrator integration."""
    
    def test_orchestrator_initialization(self) -> None:
        """Test orchestrator initialization."""
        # Mock dependencies
        detector = Mock(spec=ProcessDetector)
        calculator = Mock(spec=ProgressCalculator)
        dispatcher = Mock(spec=AsyncDispatcher)
        state_machine = Mock(spec=StateMachine)
        event_bus = Mock(spec=EventBus)
        
        orchestrator = MonitorOrchestrator(
            detector=detector,
            calculator=calculator,
            dispatcher=dispatcher,
            state_machine=state_machine,
            event_bus=event_bus
        )
        
        assert orchestrator.detector == detector
        assert orchestrator.calculator == calculator
        assert orchestrator.dispatcher == dispatcher
        assert orchestrator.state_machine == state_machine
        assert orchestrator.event_bus == event_bus
        assert orchestrator.registry is not None
        assert orchestrator.workflow_engine is not None
        assert orchestrator.resource_allocator is not None
        assert orchestrator.health_monitor is not None
    
    @pytest.mark.asyncio
    async def test_orchestrator_startup(self) -> None:
        """Test orchestrator startup sequence."""
        # Mock dependencies
        detector = Mock(spec=ProcessDetector)
        calculator = Mock(spec=ProgressCalculator)
        dispatcher = Mock(spec=AsyncDispatcher)
        state_machine = Mock(spec=StateMachine)
        event_bus = Mock(spec=EventBus)
        
        orchestrator = MonitorOrchestrator(
            detector=detector,
            calculator=calculator,
            dispatcher=dispatcher,
            state_machine=state_machine,
            event_bus=event_bus
        )
        
        # Mock component health checks
        orchestrator.health_monitor.check_component_health = Mock(return_value=True)
        
        # Test startup
        await orchestrator.startup()
        
        assert orchestrator.running is True
        # Verify components were registered
        assert len(orchestrator.registry.components) > 0
    
    @pytest.mark.asyncio
    async def test_orchestrator_shutdown(self) -> None:
        """Test orchestrator shutdown sequence."""
        # Mock dependencies
        detector = Mock(spec=ProcessDetector)
        calculator = Mock(spec=ProgressCalculator)
        dispatcher = Mock(spec=AsyncDispatcher)
        state_machine = Mock(spec=StateMachine)
        event_bus = Mock(spec=EventBus)
        
        orchestrator = MonitorOrchestrator(
            detector=detector,
            calculator=calculator,
            dispatcher=dispatcher,
            state_machine=state_machine,
            event_bus=event_bus
        )
        
        orchestrator.running = True
        
        # Test shutdown
        await orchestrator.shutdown()
        
        assert orchestrator.running is False
    
    @pytest.mark.asyncio
    async def test_orchestrator_process_detection_workflow(self) -> None:
        """Test the process detection workflow."""
        # Mock dependencies
        detector = Mock(spec=ProcessDetector)
        calculator = Mock(spec=ProgressCalculator)
        dispatcher = Mock(spec=AsyncDispatcher)
        state_machine = Mock(spec=StateMachine)
        event_bus = Mock(spec=EventBus)
        
        # Mock process detection
        process_info = Mock(spec=ProcessInfo)
        process_info.pid = 1234
        process_info.name = "test_process"
        process_info.status = ProcessStatus.RUNNING
        
        detector.detect_mover = Mock(return_value=process_info)
        detector.is_process_running = Mock(return_value=True)
        
        # Mock state machine
        state_machine.get_current_state = Mock(return_value=MonitorState.IDLE)
        state_machine.transition_to = Mock(return_value=True)
        
        # Mock event bus
        event_bus.publish = Mock()
        
        orchestrator = MonitorOrchestrator(
            detector=detector,
            calculator=calculator,
            dispatcher=dispatcher,
            state_machine=state_machine,
            event_bus=event_bus
        )
        
        # Test process detection workflow
        await orchestrator.run_detection_cycle()
        
        # Verify detection was called
        detector.detect_mover.assert_called_once()
        
        # Verify state transitions (DETECTING -> MONITORING when process found)
        assert state_machine.transition_to.call_count == 2
        state_machine.transition_to.assert_any_call(MonitorState.DETECTING)
        state_machine.transition_to.assert_called_with(MonitorState.MONITORING)
        
        # Verify event was published
        event_bus.publish_event.assert_called()
    
    @pytest.mark.asyncio
    async def test_orchestrator_monitoring_workflow(self) -> None:
        """Test the monitoring workflow."""
        # Mock dependencies
        detector = Mock(spec=ProcessDetector)
        calculator = Mock(spec=ProgressCalculator)
        dispatcher = Mock(spec=AsyncDispatcher)
        state_machine = Mock(spec=StateMachine)
        event_bus = Mock(spec=EventBus)
        
        # Mock progress calculation
        progress_metrics = Mock(spec=ProgressMetrics)
        progress_metrics.percentage = 75.0
        progress_metrics.transfer_rate = 10.5
        progress_metrics.eta_seconds = 300
        
        calculator.calculate_progress = AsyncMock(return_value=progress_metrics)
        
        # Mock state machine
        state_machine.get_current_state = Mock(return_value=MonitorState.MONITORING)
        
        # Mock event bus
        event_bus.publish = Mock()
        
        orchestrator = MonitorOrchestrator(
            detector=detector,
            calculator=calculator,
            dispatcher=dispatcher,
            state_machine=state_machine,
            event_bus=event_bus
        )
        
        # Set current process
        process_info = Mock(spec=ProcessInfo)
        process_info.pid = 1234
        orchestrator.current_process = process_info
        
        # Test monitoring workflow
        await orchestrator.run_monitoring_cycle()
        
        # Verify progress calculation
        calculator.calculate_progress.assert_called_once()
        
        # Verify event was published
        event_bus.publish_event.assert_called()
    
    @pytest.mark.asyncio
    async def test_orchestrator_error_handling(self) -> None:
        """Test orchestrator error handling."""
        # Mock dependencies
        detector = Mock(spec=ProcessDetector)
        calculator = Mock(spec=ProgressCalculator)
        dispatcher = Mock(spec=AsyncDispatcher)
        state_machine = Mock(spec=StateMachine)
        event_bus = Mock(spec=EventBus)
        
        # Mock failing detector
        detector.detect_mover = Mock(side_effect=Exception("Detection failed"))
        
        # Mock state machine
        state_machine.get_current_state = Mock(return_value=MonitorState.IDLE)
        state_machine.transition_to = Mock(return_value=True)
        
        # Mock event bus
        event_bus.publish = Mock()
        
        orchestrator = MonitorOrchestrator(
            detector=detector,
            calculator=calculator,
            dispatcher=dispatcher,
            state_machine=state_machine,
            event_bus=event_bus
        )
        
        # Test error handling
        await orchestrator.run_detection_cycle()
        
        # Verify error state transition
        state_machine.transition_to.assert_called_with(MonitorState.ERROR)
        
        # Verify error event was published
        event_bus.publish_event.assert_called()
        
        # Check that error was logged
        assert orchestrator.last_error is not None