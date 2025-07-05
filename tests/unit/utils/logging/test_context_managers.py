"""Test cases for logging context managers."""

from __future__ import annotations

import logging
import threading
import time

from mover_status.utils.logging.context_managers import (
    LogLevelContext,
    LogFieldContext,
    ContextualLogRecord,
    thread_local_context,
    log_level_context,
    log_field_context,
    combined_log_context,
)
from mover_status.utils.logging.log_level_manager import LogLevel


class TestLogLevelContext:
    """Test LogLevelContext context manager functionality."""
    
    def test_temporary_level_change(self) -> None:
        """Test temporary log level change."""
        logger = logging.getLogger("test.level.temp")
        original_level = logger.level
        
        with LogLevelContext(logger, LogLevel.DEBUG):
            assert logger.level == logging.DEBUG
        
        # Level should be restored after context exit
        assert logger.level == original_level
    
    def test_nested_level_contexts(self) -> None:
        """Test nested log level contexts."""
        logger = logging.getLogger("test.level.nested")
        original_level = logger.level
        
        with LogLevelContext(logger, LogLevel.INFO):
            assert logger.level == logging.INFO
            
            with LogLevelContext(logger, LogLevel.DEBUG):
                assert logger.level == logging.DEBUG
            
            # Should restore to outer context level
            assert logger.level == logging.INFO
        
        # Should restore to original level
        assert logger.level == original_level
    
    def test_exception_handling(self) -> None:
        """Test level restoration on exception."""
        logger = logging.getLogger("test.level.exception")
        original_level = logger.level
        
        try:
            with LogLevelContext(logger, LogLevel.DEBUG):
                assert logger.level == logging.DEBUG
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Level should be restored even after exception
        assert logger.level == original_level
    
    def test_logger_name_string(self) -> None:
        """Test context manager with logger name string."""
        logger_name = "test.level.string"
        
        with LogLevelContext(logger_name, LogLevel.DEBUG):
            logger = logging.getLogger(logger_name)
            assert logger.level == logging.DEBUG
    
    def test_multiple_loggers(self) -> None:
        """Test context manager with multiple loggers."""
        logger1 = logging.getLogger("test.level.multi1")
        logger2 = logging.getLogger("test.level.multi2")
        
        original_level1 = logger1.level
        original_level2 = logger2.level
        
        with LogLevelContext([logger1, logger2], LogLevel.DEBUG):
            assert logger1.level == logging.DEBUG
            assert logger2.level == logging.DEBUG
        
        # Both should be restored
        assert logger1.level == original_level1
        assert logger2.level == original_level2
    
    def test_thread_safety(self) -> None:
        """Test thread safety of LogLevelContext."""
        results: list[int] = []
        
        def worker(worker_id: int) -> None:
            logger = logging.getLogger(f"test.level.thread.{worker_id}")
            
            with LogLevelContext(logger, LogLevel.DEBUG):
                time.sleep(0.1)  # Simulate work
                results.append(logger.level)
        
        # Start multiple threads
        threads: list[threading.Thread] = []
        for i in range(3):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # All should have DEBUG level during context
        assert all(level == logging.DEBUG for level in results)


class TestLogFieldContext:
    """Test LogFieldContext context manager functionality."""
    
    def test_context_fields_added(self) -> None:
        """Test that context fields are added to log records."""
        logger = logging.getLogger("test.field.context")
        
        with LogFieldContext({"user_id": "123", "request_id": "abc"}):
            # Create a log record
            record = logging.LogRecord(
                name=logger.name,
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="Test message",
                args=(),
                exc_info=None
            )
            
            # Check that contextual fields are available
            contextual_record = ContextualLogRecord(record)
            fields = contextual_record.get_context_fields()
            
            assert fields["user_id"] == "123"
            assert fields["request_id"] == "abc"
    
    def test_nested_field_contexts(self) -> None:
        """Test nested field contexts."""
        with LogFieldContext({"user_id": "123"}):
            with LogFieldContext({"request_id": "abc"}):
                record = logging.LogRecord(
                    name="test.nested",
                    level=logging.INFO,
                    pathname="test.py",
                    lineno=1,
                    msg="Test message",
                    args=(),
                    exc_info=None
                )
                
                contextual_record = ContextualLogRecord(record)
                fields = contextual_record.get_context_fields()
                
                # Should have both fields
                assert fields["user_id"] == "123"
                assert fields["request_id"] == "abc"
    
    def test_field_override(self) -> None:
        """Test field override in nested contexts."""
        with LogFieldContext({"user_id": "123"}):
            with LogFieldContext({"user_id": "456"}):
                record = logging.LogRecord(
                    name="test.override",
                    level=logging.INFO,
                    pathname="test.py",
                    lineno=1,
                    msg="Test message",
                    args=(),
                    exc_info=None
                )
                
                contextual_record = ContextualLogRecord(record)
                fields = contextual_record.get_context_fields()
                
                # Should have inner value
                assert fields["user_id"] == "456"
    
    def test_context_cleanup(self) -> None:
        """Test context cleanup on exit."""
        with LogFieldContext({"temp_field": "value"}):
            pass
        
        # After exit, context should be clean
        record = logging.LogRecord(
            name="test.cleanup",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        contextual_record = ContextualLogRecord(record)
        fields = contextual_record.get_context_fields()
        
        assert "temp_field" not in fields
    
    def test_thread_isolation(self) -> None:
        """Test thread isolation of log field contexts."""
        results: dict[int, dict[str, str]] = {}
        
        def worker(worker_id: int) -> None:
            with LogFieldContext({"worker_id": str(worker_id)}):
                time.sleep(0.1)  # Simulate work
                
                record = logging.LogRecord(
                    name=f"test.thread.{worker_id}",
                    level=logging.INFO,
                    pathname="test.py",
                    lineno=1,
                    msg="Test message",
                    args=(),
                    exc_info=None
                )
                
                contextual_record = ContextualLogRecord(record)
                fields = contextual_record.get_context_fields()
                results[worker_id] = fields
        
        # Start multiple threads
        threads: list[threading.Thread] = []
        for i in range(3):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Each thread should have its own context
        assert results[0]["worker_id"] == "0"
        assert results[1]["worker_id"] == "1"
        assert results[2]["worker_id"] == "2"


class TestContextualLogRecord:
    """Test ContextualLogRecord functionality."""
    
    def test_basic_record_wrapper(self) -> None:
        """Test basic log record wrapper functionality."""
        original_record = logging.LogRecord(
            name="test.wrapper",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        contextual_record = ContextualLogRecord(original_record)
        
        # Should preserve original record attributes
        assert contextual_record.name == original_record.name
        assert contextual_record.levelno == original_record.levelno
        assert contextual_record.msg == original_record.msg
    
    def test_context_fields_integration(self) -> None:
        """Test context fields integration with record."""
        with LogFieldContext({"correlation_id": "xyz-123"}):
            record = logging.LogRecord(
                name="test.integration",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="Test message",
                args=(),
                exc_info=None
            )
            
            contextual_record = ContextualLogRecord(record)
            fields = contextual_record.get_context_fields()
            
            assert fields["correlation_id"] == "xyz-123"
    
    def test_no_context_fields(self) -> None:
        """Test behavior when no context fields are set."""
        record = logging.LogRecord(
            name="test.no_context",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        contextual_record = ContextualLogRecord(record)
        fields = contextual_record.get_context_fields()
        
        assert fields == {}


class TestThreadLocalContext:
    """Test thread-local context storage."""
    
    def test_thread_local_storage(self) -> None:
        """Test thread-local storage functionality."""
        thread_local_context.fields = {"test_key": "test_value"}
        
        assert hasattr(thread_local_context, "fields")
        assert thread_local_context.fields["test_key"] == "test_value"
    
    def test_thread_isolation(self) -> None:
        """Test thread isolation of context storage."""
        results: dict[int, str] = {}
        
        def worker(worker_id: int) -> None:
            thread_local_context.fields = {"worker": str(worker_id)}
            time.sleep(0.1)  # Simulate work
            results[worker_id] = thread_local_context.fields["worker"]
        
        # Start multiple threads
        threads: list[threading.Thread] = []
        for i in range(3):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Each thread should have its own context
        assert results[0] == "0"
        assert results[1] == "1"
        assert results[2] == "2"


class TestContextManagerIntegration:
    """Test integration between context managers and logging system."""
    
    def test_level_and_field_context_integration(self) -> None:
        """Test LogLevelContext and LogFieldContext work together."""
        logger = logging.getLogger("test.integration")
        original_level = logger.level
        
        with LogLevelContext(logger, LogLevel.DEBUG):
            with LogFieldContext({"integration_test": "true"}):
                # Logger should have DEBUG level
                assert logger.level == logging.DEBUG
                
                # Context fields should be available
                record = logging.LogRecord(
                    name=logger.name,
                    level=logging.INFO,
                    pathname="test.py",
                    lineno=1,
                    msg="Test message",
                    args=(),
                    exc_info=None
                )
                
                contextual_record = ContextualLogRecord(record)
                fields = contextual_record.get_context_fields()
                
                assert fields["integration_test"] == "true"
        
        # Logger level should be restored
        assert logger.level == original_level


class TestConvenienceFunctions:
    """Test convenience functions for context managers."""
    
    def test_log_level_context_function(self) -> None:
        """Test log_level_context convenience function."""
        logger = logging.getLogger("test.convenience.level")
        original_level = logger.level
        
        with log_level_context(logger, LogLevel.DEBUG):
            assert logger.level == logging.DEBUG
        
        assert logger.level == original_level
    
    def test_log_field_context_function(self) -> None:
        """Test log_field_context convenience function."""
        with log_field_context({"convenience_test": "true"}):
            record = logging.LogRecord(
                name="test.convenience.field",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="Test message",
                args=(),
                exc_info=None
            )
            
            contextual_record = ContextualLogRecord(record)
            fields = contextual_record.get_context_fields()
            
            assert fields["convenience_test"] == "true"
    
    def test_combined_log_context_function(self) -> None:
        """Test combined_log_context convenience function."""
        logger = logging.getLogger("test.convenience.combined")
        original_level = logger.level
        
        with combined_log_context(logger, LogLevel.WARNING, {"combined_test": "enabled"}):
            # Check level
            assert logger.level == logging.WARNING
            
            # Check fields
            record = logging.LogRecord(
                name=logger.name,
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="Test message",
                args=(),
                exc_info=None
            )
            
            contextual_record = ContextualLogRecord(record)
            fields = contextual_record.get_context_fields()
            
            assert fields["combined_test"] == "enabled"
        
        # Level should be restored
        assert logger.level == original_level


class TestErrorCases:
    """Test error handling and edge cases."""
    
    def test_invalid_logger_type(self) -> None:
        """Test error handling for invalid logger type."""
        try:
            _ = LogLevelContext(123, LogLevel.INFO)  # pyright: ignore[reportArgumentType]
            assert False, "Should have raised TypeError"
        except TypeError as e:
            assert "Invalid logger type" in str(e)
    
    def test_invalid_logger_in_list(self) -> None:
        """Test error handling for invalid logger type in list."""
        try:
            _ = LogLevelContext([logging.getLogger("test"), 123], LogLevel.INFO)  # pyright: ignore[reportArgumentType]
            assert False, "Should have raised TypeError"
        except TypeError as e:
            assert "Invalid logger type" in str(e)
    
    def test_contextual_log_record_attribute_delegation(self) -> None:
        """Test attribute delegation in ContextualLogRecord."""
        record = logging.LogRecord(
            name="test.delegation",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        contextual_record = ContextualLogRecord(record)
        
        # Test that we can access attributes that aren't copied directly
        assert contextual_record.lineno == 42
        assert contextual_record.pathname == "test.py"
    
    def test_automatic_contextual_logging(self) -> None:
        """Test automatic contextual logging with structured formatters."""
        logger = logging.getLogger("test.auto")
        original_level = logger.level
        
        with LogFieldContext({"auto_context": "enabled"}):
            with LogLevelContext(logger, LogLevel.INFO):
                # Verify context is properly maintained
                record = logging.LogRecord(
                    name=logger.name,
                    level=logging.INFO,
                    pathname="test.py",
                    lineno=1,
                    msg="Auto test message",
                    args=(),
                    exc_info=None
                )
                
                contextual_record = ContextualLogRecord(record)
                fields = contextual_record.get_context_fields()
                
                # Logger should have INFO level during context
                assert logger.level == logging.INFO
                assert fields["auto_context"] == "enabled"
        
        # Logger level should be restored
        assert logger.level == original_level