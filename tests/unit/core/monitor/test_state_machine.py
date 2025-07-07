"""Tests for monitoring orchestrator state machine."""

from __future__ import annotations

import pytest
from unittest.mock import patch

from mover_status.core.monitor.state_machine import (
    MonitorState,
    StateTransition,
    StateMachine,
    StateTransitionError,
    StatePersistence,
    StateContext,
)


class TestMonitorState:
    """Test cases for MonitorState enum."""

    def test_monitor_state_values(self) -> None:
        """Test that all expected monitor states are defined."""
        expected_states = {
            'IDLE', 'DETECTING', 'MONITORING', 'COMPLETING', 
            'ERROR', 'RECOVERING', 'SHUTDOWN', 'SUSPENDED'
        }
        actual_states = {state.name for state in MonitorState}
        assert actual_states == expected_states

    def test_state_ordering(self) -> None:
        """Test that states have proper ordering for comparison."""
        assert MonitorState.IDLE.value < MonitorState.DETECTING.value
        assert MonitorState.DETECTING.value < MonitorState.MONITORING.value
        assert MonitorState.MONITORING.value < MonitorState.COMPLETING.value


class TestStateTransition:
    """Test cases for state transition logic."""

    def test_state_transition_creation(self) -> None:
        """Test creating a state transition."""
        transition = StateTransition(
            from_state=MonitorState.IDLE,
            to_state=MonitorState.DETECTING,
            guard=lambda ctx: True,
            action=lambda ctx: None
        )
        assert transition.from_state == MonitorState.IDLE
        assert transition.to_state == MonitorState.DETECTING
        assert transition.guard is not None
        assert transition.action is not None

    def test_state_transition_without_guard(self) -> None:
        """Test state transition without guard condition."""
        transition = StateTransition(
            from_state=MonitorState.IDLE,
            to_state=MonitorState.DETECTING
        )
        assert transition.guard is None
        assert transition.action is None

    def test_state_transition_guard_validation(self) -> None:
        """Test guard condition validation."""
        context = StateContext()
        
        # Guard returns True
        transition = StateTransition(
            from_state=MonitorState.IDLE,
            to_state=MonitorState.DETECTING,
            guard=lambda ctx: True
        )
        assert transition.can_transition(context) is True
        
        # Guard returns False
        transition = StateTransition(
            from_state=MonitorState.IDLE,
            to_state=MonitorState.DETECTING,
            guard=lambda ctx: False
        )
        assert transition.can_transition(context) is False

    def test_state_transition_action_execution(self) -> None:
        """Test action execution during transition."""
        context = StateContext()
        action_executed = False
        
        def test_action(ctx: StateContext) -> None:
            nonlocal action_executed
            action_executed = True
            ctx.set_data("action_executed", True)
        
        transition = StateTransition(
            from_state=MonitorState.IDLE,
            to_state=MonitorState.DETECTING,
            action=test_action
        )
        
        transition.execute_action(context)
        assert action_executed is True
        assert context.get_data("action_executed") is True


class TestStateContext:
    """Test cases for state context management."""

    def test_state_context_initialization(self) -> None:
        """Test state context initialization."""
        context = StateContext()
        assert context.current_state is None
        assert context.previous_state is None
        assert len(context.data) == 0

    def test_state_context_data_operations(self) -> None:
        """Test context data operations."""
        context = StateContext()
        
        # Set and get data
        context.set_data("key1", "value1")
        assert context.get_data("key1") == "value1"
        
        # Get non-existent key with default
        assert context.get_data("key2", "default") == "default"
        
        # Check if key exists
        assert context.has_data("key1") is True
        assert context.has_data("key2") is False
        
        # Remove data
        context.remove_data("key1")
        assert context.has_data("key1") is False

    def test_state_context_state_management(self) -> None:
        """Test state management in context."""
        context = StateContext()
        
        # Set current state
        context.set_current_state(MonitorState.IDLE)
        assert context.current_state == MonitorState.IDLE
        
        # Transition to new state
        context.set_current_state(MonitorState.DETECTING)
        assert context.current_state == MonitorState.DETECTING
        assert context.previous_state == MonitorState.IDLE

    def test_state_context_history(self) -> None:
        """Test state transition history tracking."""
        context = StateContext()
        
        # Transition through multiple states
        context.set_current_state(MonitorState.IDLE)
        context.set_current_state(MonitorState.DETECTING)
        context.set_current_state(MonitorState.MONITORING)
        
        history = context.get_state_history()
        assert len(history) == 3
        assert history[0] == MonitorState.IDLE
        assert history[1] == MonitorState.DETECTING
        assert history[2] == MonitorState.MONITORING


class TestStateMachine:
    """Test cases for state machine implementation."""

    def test_state_machine_initialization(self) -> None:
        """Test state machine initialization."""
        machine = StateMachine(initial_state=MonitorState.IDLE)
        assert machine.current_state == MonitorState.IDLE
        assert machine.context.current_state == MonitorState.IDLE

    def test_state_machine_add_transition(self) -> None:
        """Test adding transitions to state machine."""
        machine = StateMachine(initial_state=MonitorState.IDLE)
        
        transition = StateTransition(
            from_state=MonitorState.IDLE,
            to_state=MonitorState.DETECTING
        )
        
        machine.add_transition(transition)
        transitions = machine.get_transitions(MonitorState.IDLE)
        assert len(transitions) == 1
        assert transitions[0] == transition

    def test_state_machine_multiple_transitions(self) -> None:
        """Test multiple transitions from same state."""
        machine = StateMachine(initial_state=MonitorState.IDLE)
        
        transition1 = StateTransition(
            from_state=MonitorState.IDLE,
            to_state=MonitorState.DETECTING
        )
        transition2 = StateTransition(
            from_state=MonitorState.IDLE,
            to_state=MonitorState.SHUTDOWN
        )
        
        machine.add_transition(transition1)
        machine.add_transition(transition2)
        
        transitions = machine.get_transitions(MonitorState.IDLE)
        assert len(transitions) == 2
        assert transition1 in transitions
        assert transition2 in transitions

    def test_state_machine_valid_transition(self) -> None:
        """Test valid state transition."""
        machine = StateMachine(initial_state=MonitorState.IDLE)
        
        transition = StateTransition(
            from_state=MonitorState.IDLE,
            to_state=MonitorState.DETECTING
        )
        machine.add_transition(transition)
        
        # Execute transition
        success = machine.transition_to(MonitorState.DETECTING)
        assert success is True
        assert machine.current_state == MonitorState.DETECTING

    def test_state_machine_invalid_transition(self) -> None:
        """Test invalid state transition."""
        machine = StateMachine(initial_state=MonitorState.IDLE)
        
        # No transition defined from IDLE to MONITORING
        with pytest.raises(StateTransitionError):
            _ = machine.transition_to(MonitorState.MONITORING)

    def test_state_machine_guarded_transition(self) -> None:
        """Test guarded state transition."""
        machine = StateMachine(initial_state=MonitorState.IDLE)
        
        # Transition with guard that returns False
        transition = StateTransition(
            from_state=MonitorState.IDLE,
            to_state=MonitorState.DETECTING,
            guard=lambda ctx: False
        )
        machine.add_transition(transition)
        
        # Transition should fail due to guard
        with pytest.raises(StateTransitionError):
            _ = machine.transition_to(MonitorState.DETECTING)

    def test_state_machine_action_execution(self) -> None:
        """Test action execution during transition."""
        machine = StateMachine(initial_state=MonitorState.IDLE)
        
        action_executed = False
        
        def test_action(_ctx: StateContext) -> None:
            nonlocal action_executed
            action_executed = True
        
        transition = StateTransition(
            from_state=MonitorState.IDLE,
            to_state=MonitorState.DETECTING,
            action=test_action
        )
        machine.add_transition(transition)
        
        # Execute transition
        _ = machine.transition_to(MonitorState.DETECTING)
        assert action_executed is True

    def test_state_machine_hierarchical_states(self) -> None:
        """Test hierarchical state support."""
        machine = StateMachine(initial_state=MonitorState.IDLE)
        
        # Test parent-child state relationships
        parent_states = machine.get_parent_states(MonitorState.MONITORING)
        assert MonitorState.IDLE in parent_states  # IDLE is parent of all active states
        
        child_states = machine.get_child_states(MonitorState.IDLE)
        assert MonitorState.DETECTING in child_states

    def test_state_machine_thread_safety(self) -> None:
        """Test thread-safe state management."""
        machine = StateMachine(initial_state=MonitorState.IDLE)
        
        # Add transition
        transition = StateTransition(
            from_state=MonitorState.IDLE,
            to_state=MonitorState.DETECTING
        )
        machine.add_transition(transition)
        
        # Test that state changes are thread-safe
        with machine._state_lock:  # pyright: ignore[reportPrivateUsage] # needed for testing thread safety
            current_state = machine.current_state
            assert current_state == MonitorState.IDLE


class TestStatePersistence:
    """Test cases for state persistence."""

    def test_state_persistence_initialization(self) -> None:
        """Test state persistence initialization."""
        persistence = StatePersistence()
        assert persistence.storage_path is not None

    def test_state_persistence_save_and_load(self) -> None:
        """Test saving and loading state."""
        persistence = StatePersistence()
        
        # Create state to save
        state_data = {
            'current_state': MonitorState.MONITORING.name,
            'previous_state': MonitorState.DETECTING.name,
            'context_data': {'key': 'value'}
        }
        
        # Save state
        persistence.save_state(state_data)
        
        # Load state
        loaded_state = persistence.load_state()
        assert loaded_state is not None
        assert loaded_state['current_state'] == MonitorState.MONITORING.name
        assert loaded_state['previous_state'] == MonitorState.DETECTING.name
        context_data = loaded_state['context_data']
        assert isinstance(context_data, dict)
        assert context_data['key'] == 'value'

    def test_state_persistence_file_operations(self) -> None:
        """Test file operations for state persistence."""
        persistence = StatePersistence()
        
        # Test that state file is created
        state_data = {'current_state': MonitorState.IDLE.name}
        persistence.save_state(state_data)
        
        assert persistence.storage_path.exists()
        assert persistence.storage_path.is_file()

    def test_state_persistence_error_handling(self) -> None:
        """Test error handling in state persistence."""
        persistence = StatePersistence()
        
        # Test loading non-existent state
        with patch('pathlib.Path.exists', return_value=False):
            loaded_state = persistence.load_state()
            assert loaded_state is None

    def test_state_persistence_restoration(self) -> None:
        """Test state restoration from persistence."""
        machine = StateMachine(initial_state=MonitorState.IDLE)
        persistence = StatePersistence()
        
        # Create and save state
        state_data = {
            'current_state': MonitorState.MONITORING.name,
            'context_data': {'process_id': 12345}
        }
        persistence.save_state(state_data)
        
        # Restore state to machine
        machine.restore_from_persistence(persistence)
        
        assert machine.current_state == MonitorState.MONITORING
        assert machine.context.get_data('process_id') == 12345


class TestStateTransitionError:
    """Test cases for state transition error handling."""

    def test_state_transition_error_creation(self) -> None:
        """Test creating state transition error."""
        error = StateTransitionError(
            "Cannot transition from IDLE to MONITORING",
            from_state=MonitorState.IDLE,
            to_state=MonitorState.MONITORING
        )
        
        assert str(error) == "Cannot transition from IDLE to MONITORING"
        assert error.from_state == MonitorState.IDLE
        assert error.to_state == MonitorState.MONITORING

    def test_state_transition_error_inheritance(self) -> None:
        """Test that StateTransitionError inherits from Exception."""
        error = StateTransitionError("Test error")
        assert isinstance(error, Exception)


class TestStateMachineIntegration:
    """Integration tests for state machine components."""

    def test_complete_state_machine_workflow(self) -> None:
        """Test complete state machine workflow."""
        machine = StateMachine(initial_state=MonitorState.IDLE)
        
        # Define all transitions
        transitions = [
            StateTransition(MonitorState.IDLE, MonitorState.DETECTING),
            StateTransition(MonitorState.DETECTING, MonitorState.MONITORING),
            StateTransition(MonitorState.MONITORING, MonitorState.COMPLETING),
            StateTransition(MonitorState.COMPLETING, MonitorState.IDLE),
            StateTransition(MonitorState.MONITORING, MonitorState.ERROR),
            StateTransition(MonitorState.ERROR, MonitorState.RECOVERING),
            StateTransition(MonitorState.RECOVERING, MonitorState.IDLE),
        ]
        
        for transition in transitions:
            machine.add_transition(transition)
        
        # Execute workflow
        _ = machine.transition_to(MonitorState.DETECTING)
        assert machine.current_state == MonitorState.DETECTING
        
        _ = machine.transition_to(MonitorState.MONITORING)
        assert machine.current_state == MonitorState.MONITORING
        
        _ = machine.transition_to(MonitorState.COMPLETING)
        assert machine.current_state == MonitorState.COMPLETING
        
        _ = machine.transition_to(MonitorState.IDLE)
        assert machine.current_state == MonitorState.IDLE

    def test_error_recovery_workflow(self) -> None:
        """Test error recovery workflow."""
        machine = StateMachine(initial_state=MonitorState.MONITORING)
        
        # Add error and recovery transitions
        error_transition = StateTransition(
            from_state=MonitorState.MONITORING,
            to_state=MonitorState.ERROR
        )
        recovery_transition = StateTransition(
            from_state=MonitorState.ERROR,
            to_state=MonitorState.RECOVERING
        )
        restart_transition = StateTransition(
            from_state=MonitorState.RECOVERING,
            to_state=MonitorState.IDLE
        )
        
        machine.add_transition(error_transition)
        machine.add_transition(recovery_transition)
        machine.add_transition(restart_transition)
        
        # Simulate error
        _ = machine.transition_to(MonitorState.ERROR)
        assert machine.current_state == MonitorState.ERROR
        
        # Recover
        _ = machine.transition_to(MonitorState.RECOVERING)
        assert machine.current_state == MonitorState.RECOVERING
        
        # Restart
        _ = machine.transition_to(MonitorState.IDLE)
        assert machine.current_state == MonitorState.IDLE

    def test_state_machine_with_context_data(self) -> None:
        """Test state machine with context data flow."""
        machine = StateMachine(initial_state=MonitorState.IDLE)
        
        # Add transition with action that modifies context
        def on_start_detecting(ctx: StateContext) -> None:
            ctx.set_data("detection_started", True)
            ctx.set_data("start_time", 1234567890)
        
        transition = StateTransition(
            from_state=MonitorState.IDLE,
            to_state=MonitorState.DETECTING,
            action=on_start_detecting
        )
        machine.add_transition(transition)
        
        # Execute transition
        _ = machine.transition_to(MonitorState.DETECTING)
        
        # Verify context data
        assert machine.context.get_data("detection_started") is True
        assert machine.context.get_data("start_time") == 1234567890

    def test_state_machine_persistence_integration(self) -> None:
        """Test state machine with persistence integration."""
        # Create machine and set up state
        machine = StateMachine(initial_state=MonitorState.IDLE)
        machine.context.set_data("test_key", "test_value")
        
        # Save state
        persistence = StatePersistence()
        machine.save_to_persistence(persistence)
        
        # Create new machine and restore
        new_machine = StateMachine(initial_state=MonitorState.IDLE)
        new_machine.restore_from_persistence(persistence)
        
        # Verify restoration
        assert new_machine.context.get_data("test_key") == "test_value"