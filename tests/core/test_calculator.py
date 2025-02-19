"""
Unit tests for the calculator module.

This module contains tests for the transfer calculation utilities,
including TransferStats and TransferCalculator classes.
"""

import pytest
import asyncio
from datetime import datetime
from core.calculator import TransferStats, TransferCalculator
from config.settings import Settings
from config.constants import ByteSizes

class TestTransferStats:
    """Tests for the TransferStats data class."""

    def test_initialization_with_default_values(self):
        """Test TransferStats initialization with default values."""
        stats = TransferStats()
        
        assert stats.initial_size == 0
        assert stats.current_size == 0
        assert stats.bytes_transferred == 0
        assert stats.bytes_remaining == 0
        assert stats.percent_complete == 0.0
        assert stats.transfer_rate == 0.0
        assert stats.elapsed_time == 0.0
        assert stats.remaining_time == 0.0
        assert stats.start_time is None
        assert stats.end_time is None

    def test_initialization_with_custom_values(self):
        """Test TransferStats initialization with custom values."""
        start_time = datetime.now()
        end_time = datetime.now()
        
        stats = TransferStats(
            initial_size=1000,
            current_size=500,
            bytes_transferred=500,
            bytes_remaining=500,
            percent_complete=50.0,
            transfer_rate=100.0,
            elapsed_time=5.0,
            remaining_time=5.0,
            start_time=start_time,
            end_time=end_time
        )
        
        assert stats.initial_size == 1000
        assert stats.current_size == 500
        assert stats.bytes_transferred == 500
        assert stats.bytes_remaining == 500
        assert stats.percent_complete == 50.0
        assert stats.transfer_rate == 100.0
        assert stats.elapsed_time == 5.0
        assert stats.remaining_time == 5.0
        assert stats.start_time == start_time
        assert stats.end_time == end_time

    def test_remaining_formatted_property(self):
        """Test the remaining_formatted property calculation."""
        # Test with bytes
        stats = TransferStats(bytes_remaining=500)
        assert stats.remaining_formatted == "500 B"
        
        # Test with kilobytes
        stats = TransferStats(bytes_remaining=1024)
        assert stats.remaining_formatted == "1.02 KB"
        
        # Test with megabytes
        stats = TransferStats(bytes_remaining=1024 * 1024)
        assert stats.remaining_formatted == "1.05 MB"
        
        # Test with gigabytes
        stats = TransferStats(bytes_remaining=1024 * 1024 * 1024)
        assert stats.remaining_formatted == "1.07 GB"

    def test_etc_formatted_property(self):
        """Test the etc_formatted property calculation."""
        # Test with seconds
        stats = TransferStats(remaining_time=30)
        assert stats.etc_formatted == "30 seconds"
        
        # Test with minutes
        stats = TransferStats(remaining_time=90)
        assert stats.etc_formatted == "1 minute 30 seconds"
        
        # Test with hours
        stats = TransferStats(remaining_time=3600)
        assert stats.etc_formatted == "1 hour"
        
        # Test with days
        stats = TransferStats(remaining_time=86400)
        assert stats.etc_formatted == "1 day"
        
        # Test with complex duration
        stats = TransferStats(remaining_time=90061)  # 1 day 1 hour 1 minute 1 second
        assert stats.etc_formatted == "1 day 1 hour"  # Only shows 2 most significant units


class TestTransferCalculator:
    """Tests for the TransferCalculator class."""

    @pytest.fixture
    def settings(self):
        """Create a Settings instance for testing."""
        return Settings()  # Using default settings for now

    @pytest.fixture
    def calculator(self, settings):
        """Create a TransferCalculator instance for testing."""
        return TransferCalculator(settings)

    def test_initialization(self, calculator):
        """Test TransferCalculator initialization."""
        assert calculator.stats is None
        assert calculator._initial_size is None
        assert calculator._start_time is None
        assert calculator._last_update is None
        assert calculator._last_size is None
        assert len(calculator._rate_history) == 0

    def test_initialize_transfer_with_valid_size(self, calculator):
        """Test initialize_transfer with a valid size."""
        initial_size = 1024 * 1024  # 1 MB
        calculator.initialize_transfer(initial_size)
        
        assert calculator._initial_size == initial_size
        assert calculator._start_time is not None
        assert calculator._last_update is None
        assert calculator._last_size is None
        assert len(calculator._rate_history) == 0

    def test_initialize_transfer_with_zero_size(self, calculator):
        """Test initialize_transfer with zero size."""
        with pytest.raises(ValueError, match="Initial size must be positive"):
            calculator.initialize_transfer(0)

    def test_initialize_transfer_with_negative_size(self, calculator):
        """Test initialize_transfer with negative size."""
        with pytest.raises(ValueError, match="Initial size must be positive"):
            calculator.initialize_transfer(-1024)

    def test_initialize_transfer_with_excessive_size(self, calculator):
        """Test initialize_transfer with size exceeding maximum."""
        # Maximum size is 1 PB (1024 TB)
        max_size = ByteSizes.TB * 1024
        with pytest.raises(ValueError, match="Initial size exceeds maximum"):
            calculator.initialize_transfer(max_size + ByteSizes.TB)  # Exceed by 1 TB

    def test_update_progress_without_initialization(self, calculator):
        """Test update_progress without initializing transfer."""
        with pytest.raises(RuntimeError, match="Transfer not initialized"):
            calculator.update_progress(500)

    def test_update_progress_normal_case(self, calculator):
        """Test update_progress with normal progress updates."""
        initial_size = 1000
        calculator.initialize_transfer(initial_size)
        
        # First update
        stats = calculator.update_progress(750)
        assert stats.initial_size == initial_size
        assert stats.current_size == 750
        assert stats.bytes_transferred == 250
        assert stats.bytes_remaining == 750
        assert stats.percent_complete == 25.0
        assert stats.transfer_rate >= 0.0
        assert stats.elapsed_time > 0.0
        assert stats.start_time is not None
        assert stats.end_time is None

        # Second update
        stats = calculator.update_progress(500)
        assert stats.current_size == 500
        assert stats.bytes_transferred == 500
        assert stats.bytes_remaining == 500
        assert stats.percent_complete == 50.0
        assert stats.transfer_rate >= 0.0
        assert stats.elapsed_time > 0.0
        assert stats.end_time is None

        # Final update
        stats = calculator.update_progress(0)
        assert stats.current_size == 0
        assert stats.bytes_transferred == 1000
        assert stats.bytes_remaining == 0
        assert stats.percent_complete == 100.0
        assert stats.transfer_rate >= 0.0
        assert stats.elapsed_time > 0.0
        assert stats.end_time is not None

    def test_reset(self, calculator):
        """Test reset functionality."""
        # Initialize and update transfer
        calculator.initialize_transfer(1000)
        calculator.update_progress(500)
        
        # Reset calculator
        calculator.reset()
        
        # Verify reset state
        assert calculator._initial_size is None
        assert calculator._start_time is None
        assert calculator._last_update is None
        assert calculator._last_size is None
        assert len(calculator._rate_history) == 0
        assert calculator._current_stats is None

    @pytest.mark.asyncio
    async def test_monitor_transfer_with_valid_callback(self, calculator):
        """Test monitor_transfer with a valid callback function."""
        initial_size = 1000
        calculator.initialize_transfer(initial_size)
        
        # Simulate a transfer that completes in 3 steps
        sizes = [750, 500, 0]
        current_index = 0
        
        async def get_size():
            nonlocal current_index
            if current_index < len(sizes):
                size = sizes[current_index]
                current_index += 1
                return size
            return 0
        
        # Create a task that will cancel monitoring after all sizes are processed
        async def cancel_after_completion():
            nonlocal current_index
            while current_index < len(sizes):
                await asyncio.sleep(0.1)
            # Cancel the monitoring task
            for task in asyncio.all_tasks():
                if task != asyncio.current_task():
                    task.cancel()
        
        try:
            # Run both tasks concurrently
            await asyncio.gather(
                calculator.monitor_transfer(get_size, update_interval=0.1),
                cancel_after_completion(),
                return_exceptions=True
            )
        except asyncio.CancelledError:
            pass  # Expected cancellation
        
        # Verify final state
        assert calculator.stats is not None
        assert calculator.stats.current_size == 0
        assert calculator.stats.bytes_transferred == initial_size
        assert calculator.stats.percent_complete == 100.0

    @pytest.mark.asyncio
    async def test_monitor_transfer_with_invalid_callback(self, calculator):
        """Test monitor_transfer with an invalid callback."""
        calculator.initialize_transfer(1000)
        
        with pytest.raises(TypeError, match="get_current_size must be callable"):
            await calculator.monitor_transfer("not_a_function")

    @pytest.mark.asyncio
    async def test_monitor_transfer_without_initialization(self, calculator):
        """Test monitor_transfer without initializing transfer."""
        async def get_size():
            return 500
        
        with pytest.raises(ValueError, match="Transfer not initialized"):
            await calculator.monitor_transfer(get_size)

    @pytest.mark.asyncio
    async def test_monitor_transfer_with_callback_error(self, calculator):
        """Test monitor_transfer with a callback that raises an error."""
        initial_size = 1000
        calculator.initialize_transfer(initial_size)
        
        error_count = 0
        
        async def get_size():
            nonlocal error_count
            error_count += 1
            raise ValueError("Simulated error")
        
        # The monitoring should continue despite errors
        async def cancel_after_delay():
            await asyncio.sleep(0.2)
            for task in asyncio.all_tasks():
                if task != asyncio.current_task():
                    task.cancel()
        
        try:
            await asyncio.gather(
                calculator.monitor_transfer(get_size, update_interval=0.1),
                cancel_after_delay(),
                return_exceptions=True
            )
        except asyncio.CancelledError:
            pass  # Expected cancellation
        
        # Verify that errors were handled
        assert error_count > 0  # Verify that the error callback was called
        assert calculator._initial_size == initial_size  # Initial size should be preserved
        # Stats might be None since no valid progress updates were made

    @pytest.mark.asyncio
    async def test_monitor_transfer_cancellation(self, calculator):
        """Test monitor_transfer cancellation handling."""
        calculator.initialize_transfer(1000)
        
        async def get_size():
            return 500
        
        # Cancel the monitoring after a short delay
        async def cancel_after_delay():
            await asyncio.sleep(0.2)
            for task in asyncio.all_tasks():
                if task != asyncio.current_task():
                    task.cancel()
        
        try:
            # The monitoring should handle cancellation gracefully
            await asyncio.gather(
                calculator.monitor_transfer(get_size, update_interval=0.1),
                cancel_after_delay(),
                return_exceptions=True
            )
        except asyncio.CancelledError:
            pass  # Expected cancellation
        
        # Verify that the calculator is still in a valid state
        assert calculator.stats is not None
        assert calculator._initial_size == 1000 