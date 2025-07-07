"""State machine implementation for monitoring orchestrator."""

from __future__ import annotations

import json
import threading
from enum import Enum, auto
from pathlib import Path
from typing import Callable, cast
from collections.abc import Mapping
from collections import defaultdict
from dataclasses import dataclass, field


class MonitorState(Enum):
    """States for the monitoring orchestrator."""
    
    IDLE = auto()
    DETECTING = auto()
    MONITORING = auto()
    COMPLETING = auto()
    ERROR = auto()
    RECOVERING = auto()
    SHUTDOWN = auto()
    SUSPENDED = auto()


class StateTransitionError(Exception):
    """Exception raised when state transition fails."""
    
    def __init__(
        self,
        message: str,
        from_state: MonitorState | None = None,
        to_state: MonitorState | None = None,
    ) -> None:
        """Initialize state transition error.
        
        Args:
            message: Error message
            from_state: Source state of failed transition
            to_state: Target state of failed transition
        """
        super().__init__(message)
        self.from_state: MonitorState | None = from_state
        self.to_state: MonitorState | None = to_state


@dataclass
class StateContext:
    """Context object that holds state-related data and manages state transitions."""
    
    current_state: MonitorState | None = None
    previous_state: MonitorState | None = None
    data: dict[str, object] = field(default_factory=dict)
    _state_history: list[MonitorState] = field(default_factory=list)
    
    def set_current_state(self, state: MonitorState) -> None:
        """Set the current state and update history.
        
        Args:
            state: New current state
        """
        if self.current_state is not None:
            self.previous_state = self.current_state
        self.current_state = state
        self._state_history.append(state)
    
    def get_state_history(self) -> list[MonitorState]:
        """Get the complete state transition history.
        
        Returns:
            List of states in chronological order
        """
        return self._state_history.copy()
    
    def set_data(self, key: str, value: object) -> None:
        """Set data in the context.
        
        Args:
            key: Data key
            value: Data value
        """
        self.data[key] = value
    
    def get_data(self, key: str, default: object = None) -> object:
        """Get data from the context.
        
        Args:
            key: Data key
            default: Default value if key not found
            
        Returns:
            Data value or default
        """
        return self.data.get(key, default)
    
    def has_data(self, key: str) -> bool:
        """Check if data key exists in context.
        
        Args:
            key: Data key to check
            
        Returns:
            True if key exists, False otherwise
        """
        return key in self.data
    
    def remove_data(self, key: str) -> None:
        """Remove data from context.
        
        Args:
            key: Data key to remove
        """
        _ = self.data.pop(key, None)
    
    def restore_state_history(self, state_names: list[str]) -> None:
        """Restore state history from a list of state names.
        
        Args:
            state_names: List of state names to restore
        """
        self._state_history.clear()
        for state_name in state_names:
            self._state_history.append(MonitorState[state_name])


class StateTransition:
    """Represents a state transition with optional guard and action."""
    
    from_state: MonitorState
    to_state: MonitorState
    guard: Callable[[StateContext], bool] | None
    action: Callable[[StateContext], None] | None
    
    def __init__(
        self,
        from_state: MonitorState,
        to_state: MonitorState,
        guard: Callable[[StateContext], bool] | None = None,
        action: Callable[[StateContext], None] | None = None,
    ) -> None:
        """Initialize state transition.
        
        Args:
            from_state: Source state
            to_state: Target state
            guard: Optional guard function that must return True for transition to proceed
            action: Optional action function to execute during transition
        """
        self.from_state = from_state
        self.to_state = to_state
        self.guard = guard
        self.action = action
    
    def can_transition(self, context: StateContext) -> bool:
        """Check if transition is allowed based on guard condition.
        
        Args:
            context: Current state context
            
        Returns:
            True if transition is allowed, False otherwise
        """
        if self.guard is None:
            return True
        return self.guard(context)
    
    def execute_action(self, context: StateContext) -> None:
        """Execute the transition action if defined.
        
        Args:
            context: Current state context
        """
        if self.action is not None:
            self.action(context)


class StateMachine:
    """Thread-safe state machine for monitoring orchestrator."""
    
    def __init__(self, initial_state: MonitorState) -> None:
        """Initialize state machine.
        
        Args:
            initial_state: Initial state of the machine
        """
        self.context: StateContext = StateContext()
        self.context.set_current_state(initial_state)
        self._transitions: dict[MonitorState, list[StateTransition]] = defaultdict(list)
        self._state_lock: threading.RLock = threading.RLock()
        
        # Define hierarchical relationships
        self._parent_states: dict[MonitorState, set[MonitorState]] = {
            MonitorState.DETECTING: {MonitorState.IDLE},
            MonitorState.MONITORING: {MonitorState.IDLE},
            MonitorState.COMPLETING: {MonitorState.IDLE},
            MonitorState.ERROR: {MonitorState.IDLE},
            MonitorState.RECOVERING: {MonitorState.IDLE},
            MonitorState.SUSPENDED: {MonitorState.IDLE},
        }
        
        self._child_states: dict[MonitorState, set[MonitorState]] = {
            MonitorState.IDLE: {
                MonitorState.DETECTING, MonitorState.MONITORING, 
                MonitorState.COMPLETING, MonitorState.ERROR,
                MonitorState.RECOVERING, MonitorState.SUSPENDED
            }
        }
    
    @property
    def current_state(self) -> MonitorState:
        """Get current state of the machine.
        
        Returns:
            Current state
        """
        with self._state_lock:
            if self.context.current_state is None:
                msg = "State machine not properly initialized - no current state"
                raise RuntimeError(msg)
            return self.context.current_state
    
    def add_transition(self, transition: StateTransition) -> None:
        """Add a state transition to the machine.
        
        Args:
            transition: State transition to add
        """
        with self._state_lock:
            self._transitions[transition.from_state].append(transition)
    
    def get_transitions(self, from_state: MonitorState) -> list[StateTransition]:
        """Get all transitions from a given state.
        
        Args:
            from_state: Source state
            
        Returns:
            List of transitions from the given state
        """
        with self._state_lock:
            return self._transitions[from_state].copy()
    
    def transition_to(self, to_state: MonitorState) -> bool:
        """Transition to the specified state.
        
        Args:
            to_state: Target state
            
        Returns:
            True if transition was successful
            
        Raises:
            StateTransitionError: If transition is not allowed
        """
        with self._state_lock:
            current_state = self.context.current_state
            if current_state is None:
                msg = "Cannot transition - no current state set"
                raise StateTransitionError(msg, to_state=to_state)
            
            # Find valid transition
            valid_transition = None
            for transition in self._transitions[current_state]:
                if transition.to_state == to_state:
                    if transition.can_transition(self.context):
                        valid_transition = transition
                        break
            
            if valid_transition is None:
                raise StateTransitionError(
                    f"Cannot transition from {current_state.name} to {to_state.name}",
                    from_state=current_state,
                    to_state=to_state
                )
            
            # Execute action if defined
            valid_transition.execute_action(self.context)
            
            # Update state
            self.context.set_current_state(to_state)
            
            return True
    
    def get_parent_states(self, state: MonitorState) -> set[MonitorState]:
        """Get parent states for hierarchical state support.
        
        Args:
            state: State to get parents for
            
        Returns:
            Set of parent states
        """
        return self._parent_states.get(state, set())
    
    def get_child_states(self, state: MonitorState) -> set[MonitorState]:
        """Get child states for hierarchical state support.
        
        Args:
            state: State to get children for
            
        Returns:
            Set of child states
        """
        return self._child_states.get(state, set())
    
    def save_to_persistence(self, persistence: StatePersistence) -> None:
        """Save current state to persistence.
        
        Args:
            persistence: Persistence instance to save to
        """
        with self._state_lock:
            state_data = {
                'current_state': self.context.current_state.name if self.context.current_state else None,
                'previous_state': self.context.previous_state.name if self.context.previous_state else None,
                'context_data': self.context.data,
                'state_history': [s.name for s in self.context.get_state_history()]
            }
            persistence.save_state(state_data)
    
    def restore_from_persistence(self, persistence: StatePersistence) -> None:
        """Restore state from persistence.
        
        Args:
            persistence: Persistence instance to restore from
        """
        with self._state_lock:
            state_data = persistence.load_state()
            if state_data is None:
                return
            
            # Restore current state
            current_state_name = state_data.get('current_state')
            if current_state_name and isinstance(current_state_name, str):
                current_state = MonitorState[current_state_name]
                self.context.set_current_state(current_state)
            
            # Restore previous state
            previous_state_name = state_data.get('previous_state')
            if previous_state_name and isinstance(previous_state_name, str):
                self.context.previous_state = MonitorState[previous_state_name]
            
            # Restore context data
            context_data = state_data.get('context_data')
            if context_data and isinstance(context_data, dict):
                self.context.data.update(cast(dict[str, object], context_data))
            
            # Restore state history
            state_history = state_data.get('state_history')
            if state_history and isinstance(state_history, list):
                # Filter to only string values and restore
                state_names: list[str] = []
                for item in cast(list[object], state_history):
                    if isinstance(item, str):
                        state_names.append(item)
                self.context.restore_state_history(state_names)


class StatePersistence:
    """Handles state persistence to disk."""
    
    storage_path: Path
    
    def __init__(self, storage_path: Path | None = None) -> None:
        """Initialize state persistence.
        
        Args:
            storage_path: Path to store state file, defaults to temp directory
        """
        if storage_path is None:
            storage_path = Path.cwd() / '.mover_status_state.json'
        self.storage_path = storage_path
    
    def save_state(self, state_data: Mapping[str, object]) -> None:
        """Save state data to disk.
        
        Args:
            state_data: State data dictionary to save
        """
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=2)
        except (OSError, IOError) as e:
            raise StateTransitionError(f"Failed to save state: {e}") from e
    
    def load_state(self) -> dict[str, object] | None:
        """Load state data from disk.
        
        Returns:
            State data dictionary or None if file doesn't exist
        """
        try:
            if not self.storage_path.exists():
                return None
            
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                return cast(dict[str, object], json.load(f))
        except (OSError, IOError, json.JSONDecodeError):
            return None