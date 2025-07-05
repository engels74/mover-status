"""Correlation ID tracking system for logging."""

from __future__ import annotations

import contextvars
import threading
import uuid
from collections.abc import Generator
from contextlib import contextmanager


class CorrelationIdManager:
    """Thread-safe correlation ID manager using thread-local and context variables."""
    
    def __init__(self, prefix: str = "") -> None:
        """Initialize correlation ID manager.
        
        Args:
            prefix: Optional prefix for generated correlation IDs
        """
        self._local: threading.local = threading.local()
        self._contextvar: contextvars.ContextVar[str | None] = contextvars.ContextVar('correlation_id', default=None)
        self.prefix: str = prefix
    
    def get_correlation_id(self) -> str | None:
        """Get the current correlation ID for this thread/context.
        
        Returns:
            Current correlation ID or None if not set
        """
        # Try context variable first (for async support)
        context_id = self._contextvar.get()
        if context_id is not None:
            return context_id
        
        # Fall back to thread-local storage
        return getattr(self._local, 'correlation_id', None)
    
    def set_correlation_id(self, correlation_id: str) -> None:
        """Set the correlation ID for this thread/context.
        
        Args:
            correlation_id: The correlation ID to set
        """
        # Set in both context variable and thread-local storage
        _ = self._contextvar.set(correlation_id)
        self._local.correlation_id = correlation_id
    
    def clear_correlation_id(self) -> None:
        """Clear the correlation ID for this thread/context."""
        # Clear both context variable and thread-local storage
        _ = self._contextvar.set(None)
        if hasattr(self._local, 'correlation_id'):
            delattr(self._local, 'correlation_id')
    
    def generate_correlation_id(self, prefix: str | None = None) -> str:
        """Generate a new correlation ID and set it for this thread.
        
        Args:
            prefix: Optional prefix to use (overrides instance prefix)
            
        Returns:
            The generated correlation ID
        """
        # Use provided prefix, instance prefix, or empty string
        actual_prefix = prefix if prefix is not None else self.prefix
        
        # Generate UUID and format with prefix
        correlation_id = str(uuid.uuid4())
        if actual_prefix:
            correlation_id = f"{actual_prefix}-{correlation_id}"
        
        # Set and return the generated ID
        self.set_correlation_id(correlation_id)
        return correlation_id


class CorrelationIdContext:
    """Context manager for temporarily setting correlation ID."""
    
    def __init__(self, correlation_id: str | None, manager: CorrelationIdManager | None = None) -> None:
        """Initialize correlation ID context manager.
        
        Args:
            correlation_id: The correlation ID to set (None to clear)
            manager: Optional manager instance (uses global if not provided)
        """
        self.correlation_id: str | None = correlation_id
        self.manager: CorrelationIdManager = manager or get_correlation_id_manager()
        self.previous_id: str | None = None
    
    def __enter__(self) -> CorrelationIdContext:
        """Enter context and set correlation ID."""
        # Store the previous correlation ID
        self.previous_id = self.manager.get_correlation_id()
        
        # Set the new correlation ID
        if self.correlation_id is not None:
            self.manager.set_correlation_id(self.correlation_id)
        else:
            self.manager.clear_correlation_id()
        
        return self
    
    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object) -> None:
        """Exit context and restore previous correlation ID."""
        # Restore the previous correlation ID
        if self.previous_id is not None:
            self.manager.set_correlation_id(self.previous_id)
        else:
            self.manager.clear_correlation_id()


# Global correlation ID manager instance
_global_manager: CorrelationIdManager | None = None
_manager_lock = threading.Lock()


def get_correlation_id_manager() -> CorrelationIdManager:
    """Get the global correlation ID manager instance.
    
    Returns:
        The global CorrelationIdManager instance
    """
    global _global_manager
    
    # Use double-checked locking pattern for thread safety
    if _global_manager is None:
        with _manager_lock:
            if _global_manager is None:
                _global_manager = CorrelationIdManager()
    
    return _global_manager


# Global convenience functions
def get_correlation_id() -> str | None:
    """Get the current correlation ID.
    
    Returns:
        Current correlation ID or None if not set
    """
    return get_correlation_id_manager().get_correlation_id()


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current thread.
    
    Args:
        correlation_id: The correlation ID to set
    """
    get_correlation_id_manager().set_correlation_id(correlation_id)


def clear_correlation_id() -> None:
    """Clear the correlation ID for the current thread."""
    get_correlation_id_manager().clear_correlation_id()


def generate_correlation_id(prefix: str | None = None) -> str:
    """Generate and set a new correlation ID.
    
    Args:
        prefix: Optional prefix for the generated ID
        
    Returns:
        The generated correlation ID
    """
    return get_correlation_id_manager().generate_correlation_id(prefix)


@contextmanager
def correlation_id_context(correlation_id: str | None) -> Generator[None, None, None]:
    """Context manager for temporarily setting correlation ID.
    
    Args:
        correlation_id: The correlation ID to set (None to clear)
        
    Yields:
        None
    """
    with CorrelationIdContext(correlation_id):
        yield