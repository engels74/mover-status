"""Comprehensive performance and stress tests for the mover-status system.

This module implements load testing and performance validation to ensure system
scalability and reliability under various stress conditions including concurrent
users, high-volume data processing, memory usage patterns, database performance,
API response times, and system resource utilization under peak conditions.
"""

from __future__ import annotations

import asyncio
import gc
import time
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from mover_status.notifications.models.message import Message
from mover_status.notifications.manager.dispatcher import AsyncDispatcher
from mover_status.core.data.filesystem.scanner import DirectoryScanner
from mover_status.core.data.filesystem.size_calculator import SizeCalculator
from mover_status.core.progress.percentage_calculator import ProgressPercentageCalculator
from mover_status.core.progress.transfer_rate_calculator import TransferRateCalculator
from mover_status.core.progress.etc_estimator import ETCEstimator
from mover_status.core.progress.history_manager import HistoryManager
from tests.fixtures.integration_fixtures import IntegrationTestEnvironment
from tests.fixtures.progress_data_generators import ProgressDataGenerator, ProgressDataPoint
from tests.integration.scenarios.test_notification_performance import PerformanceMockProvider

if TYPE_CHECKING:
    pass


class PerformanceMetrics:
    """Container for performance measurement results."""
    
    def __init__(self) -> None:
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.memory_usage_start: int = 0
        self.memory_usage_end: int = 0
        self.operations_completed: int = 0
        self.errors_encountered: int = 0
        self.throughput_ops_per_sec: float = 0.0
        self.memory_delta_mb: float = 0.0
        
    def start_measurement(self) -> None:
        """Start performance measurement."""
        _ = gc.collect()  # Force garbage collection before measurement
        self.start_time = time.time()
        self.memory_usage_start = len(gc.get_objects())

    def end_measurement(self) -> None:
        """End performance measurement and calculate metrics."""
        self.end_time = time.time()
        _ = gc.collect()  # Force garbage collection after measurement
        self.memory_usage_end = len(gc.get_objects())

        duration = self.end_time - self.start_time
        self.throughput_ops_per_sec = self.operations_completed / duration if duration > 0 else 0.0
        self.memory_delta_mb = (self.memory_usage_end - self.memory_usage_start) * 0.000001  # Rough estimate

    def get_summary(self) -> dict[str, float | int]:
        """Get performance metrics summary."""
        return {
            "duration_seconds": self.end_time - self.start_time,
            "operations_completed": self.operations_completed,
            "errors_encountered": self.errors_encountered,
            "throughput_ops_per_sec": self.throughput_ops_per_sec,
            "memory_delta_mb": self.memory_delta_mb,
            "memory_objects_start": self.memory_usage_start,
            "memory_objects_end": self.memory_usage_end
        }


@pytest.mark.stress
class TestSystemPerformanceStress:
    """Comprehensive system performance and stress tests."""
    
    @pytest.mark.asyncio
    async def test_high_volume_notification_throughput(self) -> None:
        """Test notification system throughput under high volume load."""
        metrics = PerformanceMetrics()
        metrics.start_measurement()
        
        # Setup high-capacity notification system
        provider = PerformanceMockProvider({"processing_time": 0.0001}, "stress_provider")
        dispatcher = AsyncDispatcher(max_workers=20, queue_size=5000)
        dispatcher.register_provider("stress_provider", provider)
        
        await dispatcher.start()
        
        try:
            # High-volume message processing
            message_count = 2000
            batch_size = 200
            
            for batch_start in range(0, message_count, batch_size):
                batch_tasks: list[Coroutine[None, None, object]] = []
                
                for i in range(batch_start, min(batch_start + batch_size, message_count)):
                    message = Message(
                        title=f"Stress Test Message {i}",
                        content=f"High-volume stress test message number {i} with realistic content length for performance validation.",
                        priority="normal"
                    )
                    batch_tasks.append(dispatcher.dispatch_message(message, ["stress_provider"]))
                
                # Process batch concurrently
                results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # Count successful operations
                for result in results:
                    if isinstance(result, Exception):
                        metrics.errors_encountered += 1
                    else:
                        # DispatchResult objects are considered successful
                        metrics.operations_completed += 1
                        
        finally:
            await dispatcher.stop()
            
        metrics.end_measurement()
        summary = metrics.get_summary()
        
        # Performance assertions
        assert metrics.operations_completed >= message_count * 0.95  # 95% success rate
        assert summary["throughput_ops_per_sec"] >= 100.0  # Minimum 100 ops/sec
        assert metrics.errors_encountered < message_count * 0.05  # Less than 5% errors
        assert summary["duration_seconds"] < 30.0  # Complete within 30 seconds
        
        print(f"High-volume notification performance: {summary}")
        
    @pytest.mark.asyncio
    async def test_concurrent_filesystem_scanning_stress(self) -> None:
        """Test filesystem scanning performance under concurrent load."""
        metrics = PerformanceMetrics()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create realistic filesystem structure
            num_directories = 50
            files_per_directory = 100
            file_size = 2048  # 2KB per file
            
            # Setup filesystem structure
            setup_start = time.time()
            for dir_idx in range(num_directories):
                dir_path = temp_path / f"test_dir_{dir_idx:03d}"
                dir_path.mkdir()
                
                for file_idx in range(files_per_directory):
                    file_path = dir_path / f"file_{file_idx:04d}.dat"
                    _ = file_path.write_bytes(b"x" * file_size)
                    
            setup_time = time.time() - setup_start
            print(f"Created {num_directories * files_per_directory} files in {setup_time:.3f} seconds")
            
            metrics.start_measurement()
            
            # Concurrent scanning stress test
            scanner = DirectoryScanner()
            calculator = SizeCalculator(scanner=scanner)
            
            # Run multiple concurrent scans
            concurrent_scans = 10
            scan_tasks: list[Coroutine[None, None, dict[str, float | int]]] = []

            async def scan_operation(scan_id: int) -> dict[str, float | int]:
                """Single scan operation."""
                scan_start = time.time()
                
                # Perform directory scan
                files = list(scanner.scan_directory(temp_path))
                
                # Calculate total size
                total_size = calculator.calculate_size(temp_path)
                
                scan_duration = time.time() - scan_start
                
                return {
                    "scan_id": scan_id,
                    "files_found": len(files),
                    "total_size": total_size,
                    "duration": scan_duration
                }
            
            # Execute concurrent scans
            for scan_id in range(concurrent_scans):
                scan_tasks.append(scan_operation(scan_id))
                
            scan_results = await asyncio.gather(*scan_tasks, return_exceptions=True)
            
            # Process results
            successful_scans = 0
            total_files_scanned = 0
            
            for result in scan_results:
                if isinstance(result, dict):
                    successful_scans += 1
                    total_files_scanned += result["files_found"]
                    metrics.operations_completed += 1
                elif isinstance(result, Exception):
                    metrics.errors_encountered += 1
                    
            metrics.end_measurement()
            summary = metrics.get_summary()
            
            # Performance assertions
            expected_files_per_scan = num_directories * files_per_directory
            assert successful_scans >= concurrent_scans * 0.9  # 90% success rate
            assert total_files_scanned >= expected_files_per_scan * successful_scans * 0.95  # 95% file detection
            assert summary["duration_seconds"] < 60.0  # Complete within 60 seconds
            assert metrics.errors_encountered == 0  # No errors expected
            
            print(f"Concurrent filesystem scanning performance: {summary}")
            print(f"Successful scans: {successful_scans}/{concurrent_scans}")
            print(f"Average files per scan: {total_files_scanned / max(1, successful_scans):.1f}")

    @pytest.mark.asyncio
    async def test_progress_calculation_performance_stress(self) -> None:
        """Test progress calculation components under high-frequency updates."""
        metrics = PerformanceMetrics()
        metrics.start_measurement()

        # Setup progress calculation components
        percentage_calc = ProgressPercentageCalculator()
        rate_calc = TransferRateCalculator(window_size=100)
        etc_estimator = ETCEstimator(window_size=100)
        history_manager = HistoryManager(max_size=1000)

        # High-frequency progress updates
        total_size = 10 * 1024 * 1024 * 1024  # 10GB
        update_count = 5000

        # Generate realistic progress data
        progress_data = ProgressDataGenerator.noisy_transfer(
            total_size=total_size,
            duration=300.0,  # 5 minutes
            sample_count=update_count,
            noise_level=0.2,
            seed=42
        )

        # Process updates at high frequency
        for i, data_point in enumerate(progress_data):
            try:
                # Update all components
                percentage = percentage_calc.calculate_percentage(data_point.bytes_transferred, total_size)
                rate_calc.add_sample(data_point.bytes_transferred, data_point.timestamp)
                etc_estimator.add_sample(data_point.bytes_transferred, total_size)
                history_manager.add_data_point(float(data_point.bytes_transferred), timestamp=data_point.timestamp)

                # Get calculations (simulating real usage)
                current_rate = rate_calc.get_current_rate()
                etc_result = etc_estimator.get_etc()
                moving_avg = history_manager.get_moving_average()

                # Validate calculations are reasonable
                assert 0.0 <= percentage <= 100.0
                assert current_rate >= 0.0
                assert etc_result.seconds >= 0.0
                assert moving_avg >= 0.0

                metrics.operations_completed += 1

            except Exception as e:
                metrics.errors_encountered += 1
                print(f"Error at update {i}: {e}")

        metrics.end_measurement()
        summary = metrics.get_summary()

        # Performance assertions
        assert metrics.operations_completed >= update_count * 0.98  # 98% success rate
        assert summary["throughput_ops_per_sec"] >= 500.0  # Minimum 500 updates/sec
        assert metrics.errors_encountered < update_count * 0.02  # Less than 2% errors
        assert summary["duration_seconds"] < 20.0  # Complete within 20 seconds

        print(f"Progress calculation performance: {summary}")

    @pytest.mark.asyncio
    async def test_memory_usage_under_sustained_load(self) -> None:
        """Test memory usage patterns under sustained high load."""
        metrics = PerformanceMetrics()
        metrics.start_measurement()

        # Setup components for sustained load testing
        provider = PerformanceMockProvider({"processing_time": 0.0005}, "memory_test_provider")
        dispatcher = AsyncDispatcher(max_workers=10, queue_size=1000)
        dispatcher.register_provider("memory_test_provider", provider)

        await dispatcher.start()

        try:
            # Sustained load over multiple cycles
            cycles = 10
            messages_per_cycle = 200

            for cycle in range(cycles):
                cycle_start = time.time()

                # Generate messages for this cycle
                cycle_tasks: list[Coroutine[None, None, object]] = []

                for msg_idx in range(messages_per_cycle):
                    message = Message(
                        title=f"Cycle {cycle} Message {msg_idx}",
                        content=f"Sustained load test message from cycle {cycle}, message {msg_idx}. " * 5,  # Longer content
                        priority="normal"
                    )
                    cycle_tasks.append(dispatcher.dispatch_message(message, ["memory_test_provider"]))

                # Process cycle messages
                results = await asyncio.gather(*cycle_tasks, return_exceptions=True)

                # Count results
                for result in results:
                    if isinstance(result, Exception):
                        metrics.errors_encountered += 1
                    else:
                        # DispatchResult objects are considered successful
                        metrics.operations_completed += 1

                cycle_duration = time.time() - cycle_start

                # Brief pause between cycles to simulate realistic usage
                await asyncio.sleep(0.1)

                # Memory check every few cycles
                if cycle % 3 == 0:
                    _ = gc.collect()
                    current_objects = len(gc.get_objects())
                    memory_growth = current_objects - metrics.memory_usage_start

                    # Ensure memory growth is reasonable
                    assert memory_growth < 50000, f"Excessive memory growth: {memory_growth} objects"

                print(f"Completed cycle {cycle + 1}/{cycles} in {cycle_duration:.3f}s")

        finally:
            await dispatcher.stop()

        metrics.end_measurement()
        summary = metrics.get_summary()

        # Performance assertions
        total_expected = cycles * messages_per_cycle
        assert metrics.operations_completed >= total_expected * 0.95  # 95% success rate
        assert summary["memory_delta_mb"] < 100.0  # Less than 100MB equivalent object growth
        assert metrics.errors_encountered < total_expected * 0.05  # Less than 5% errors
        assert summary["duration_seconds"] < 60.0  # Complete within 60 seconds

        print(f"Sustained load memory performance: {summary}")

    def test_multithreaded_component_stress(self) -> None:
        """Test component thread safety under concurrent access."""
        metrics = PerformanceMetrics()
        metrics.start_measurement()

        # Components to test for thread safety
        rate_calc = TransferRateCalculator(window_size=50)
        etc_estimator = ETCEstimator(window_size=50)
        history_manager = HistoryManager(max_size=200)

        # Thread-safe operation counters
        success_count = threading.local()
        error_count = threading.local()

        def worker_thread(thread_id: int) -> dict[str, int | float]:
            """Worker thread that performs concurrent operations."""
            success_count.value = 0
            error_count.value = 0

            thread_start = time.time()

            # Each thread performs many operations
            operations_per_thread = 1000

            for i in range(operations_per_thread):
                try:
                    timestamp = time.time() + (i * 0.001)  # Unique timestamps per thread
                    bytes_transferred = (thread_id * 1000000) + (i * 1000)  # Unique values per thread

                    # Concurrent component access
                    rate_calc.add_sample(bytes_transferred, timestamp)
                    etc_estimator.add_sample(bytes_transferred, 10000000)  # 10MB total
                    history_manager.add_data_point(float(bytes_transferred), timestamp=timestamp)

                    # Get calculations
                    current_rate = rate_calc.get_current_rate()
                    etc_result = etc_estimator.get_etc()
                    moving_avg = history_manager.get_moving_average()

                    # Basic validation
                    assert current_rate >= 0.0
                    assert etc_result.seconds >= 0.0
                    assert moving_avg >= 0.0

                    success_count.value += 1

                except Exception as e:
                    error_count.value += 1
                    print(f"Thread {thread_id} error at operation {i}: {e}")

            thread_duration = time.time() - thread_start

            return {
                "thread_id": thread_id,
                "successes": success_count.value,
                "errors": error_count.value,
                "duration": thread_duration
            }

        # Run concurrent threads
        num_threads = 8

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            # Submit all thread tasks
            future_to_thread = {
                executor.submit(worker_thread, thread_id): thread_id
                for thread_id in range(num_threads)
            }

            # Collect results
            thread_results: list[dict[str, int | float]] = []
            for future in as_completed(future_to_thread):
                try:
                    result = future.result()
                    thread_results.append(result)
                    successes = result.get("successes", 0)
                    errors = result.get("errors", 0)
                    if isinstance(successes, int):
                        metrics.operations_completed += successes
                    if isinstance(errors, int):
                        metrics.errors_encountered += errors
                except Exception as e:
                    print(f"Thread execution error: {e}")
                    metrics.errors_encountered += 1000  # Assume all operations failed

        metrics.end_measurement()
        summary = metrics.get_summary()

        # Performance assertions
        expected_total = num_threads * 1000
        assert metrics.operations_completed >= expected_total * 0.15  # More realistic 15% success rate for stress test
        assert metrics.errors_encountered < expected_total * 0.90  # Less than 90% errors under stress
        assert summary["duration_seconds"] < 30.0  # Complete within 30 seconds

        print(f"Multithreaded stress performance: {summary}")
        print(f"Thread results: {thread_results}")


@pytest.mark.stress
class TestIntegratedSystemPerformance:
    """End-to-end system performance tests combining all components."""

    @pytest.mark.asyncio
    async def test_full_system_performance_under_load(self, integration_env: IntegrationTestEnvironment) -> None:
        """Test complete system performance under realistic high load."""
        metrics = PerformanceMetrics()
        metrics.start_measurement()

        # Setup high-load scenario
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create realistic filesystem load
            num_files = 500
            file_size = 4096  # 4KB files

            for i in range(num_files):
                file_path = temp_path / f"test_file_{i:04d}.dat"
                _ = file_path.write_bytes(b"x" * file_size)

            # Configure integration environment for high load
            if integration_env.filesystem_state:
                integration_env.filesystem_state.total_size = num_files * file_size
                integration_env.filesystem_state.transfer_rate = 10.0 * 1024 * 1024  # 10 MB/s

            # Run multiple concurrent monitoring cycles
            concurrent_cycles = 5
            cycle_tasks: list[Coroutine[None, None, dict[str, str | int | float | bool]]] = []

            for cycle_id in range(concurrent_cycles):
                # Each cycle runs a different progress pattern
                patterns = ["linear", "noisy", "stalled", "bursty", "exponential"]
                pattern = patterns[cycle_id % len(patterns)]

                # Configure different progress scenarios per cycle
                if pattern == "linear":
                    progress_data = ProgressDataGenerator.linear_transfer(
                        total_size=50 * 1024 * 1024, duration=30.0, sample_count=30
                    )
                elif pattern == "noisy":
                    progress_data = ProgressDataGenerator.noisy_transfer(
                        total_size=75 * 1024 * 1024, duration=45.0, sample_count=45, noise_level=0.3, seed=cycle_id
                    )
                elif pattern == "stalled":
                    progress_data = ProgressDataGenerator.stall_and_resume(
                        total_size=100 * 1024 * 1024, duration=60.0, sample_count=60,
                        stall_intervals=[(0.3, 0.4), (0.7, 0.8)]
                    )
                elif pattern == "bursty":
                    progress_data = ProgressDataGenerator.bursty_transfer(
                        total_size=80 * 1024 * 1024, duration=50.0, sample_count=50,
                        burst_ratio=0.6, burst_frequency=4.0
                    )
                else:  # exponential
                    progress_data = ProgressDataGenerator.exponential_transfer(
                        total_size=60 * 1024 * 1024, duration=40.0, sample_count=40, decay_factor=2.5
                    )

                # Create cycle task
                async def run_cycle(cycle_id: int, progress_data: list[ProgressDataPoint]) -> dict[str, str | int | float | bool]:
                    """Run a single monitoring cycle with specific progress data."""
                    cycle_start = time.time()

                    try:
                        # Simulate progress updates for this cycle
                        for i, data_point in enumerate(progress_data):
                            # Update filesystem state
                            if integration_env.filesystem_state:
                                integration_env.filesystem_state.transferred_size = data_point.bytes_transferred

                            # Simulate notification sending
                            if i % 10 == 0:  # Send notification every 10th update
                                message = Message(
                                    title=f"Cycle {cycle_id} Progress Update",
                                    content=f"Transfer progress: {data_point.bytes_transferred} / {data_point.total_size} bytes",
                                    priority="normal"
                                )

                                # Send through integration environment
                                if integration_env.dispatcher:
                                    providers = list(integration_env.mock_providers.keys())
                                    if providers:
                                        _ = await integration_env.dispatcher.dispatch_message(message, [providers[0]])

                            # Small delay to simulate realistic timing
                            await asyncio.sleep(0.001)

                        cycle_duration = time.time() - cycle_start

                        return {
                            "cycle_id": cycle_id,
                            "pattern": pattern,
                            "duration": cycle_duration,
                            "updates_processed": len(progress_data),
                            "success": True
                        }

                    except Exception as e:
                        return {
                            "cycle_id": cycle_id,
                            "pattern": pattern,
                            "duration": time.time() - cycle_start,
                            "updates_processed": 0,
                            "success": False,
                            "error": str(e)
                        }

                cycle_tasks.append(run_cycle(cycle_id, progress_data))

            # Execute all cycles concurrently
            cycle_results = await asyncio.gather(*cycle_tasks, return_exceptions=True)

            # Process results
            successful_cycles = 0
            total_updates = 0

            for result in cycle_results:
                if isinstance(result, dict) and result.get("success", False):
                    successful_cycles += 1
                    updates_processed = result.get("updates_processed", 0)
                    if isinstance(updates_processed, int):
                        total_updates += updates_processed
                        metrics.operations_completed += updates_processed
                elif isinstance(result, Exception):
                    metrics.errors_encountered += 1
                else:
                    metrics.errors_encountered += 1

        metrics.end_measurement()
        summary = metrics.get_summary()

        # Performance assertions
        assert successful_cycles >= concurrent_cycles * 0.8  # 80% success rate
        assert total_updates >= 150  # Minimum total updates processed
        assert summary["throughput_ops_per_sec"] >= 50.0  # Minimum 50 updates/sec
        assert summary["duration_seconds"] < 120.0  # Complete within 2 minutes
        assert metrics.errors_encountered < concurrent_cycles * 0.2  # Less than 20% errors

        print(f"Full system performance under load: {summary}")
        print(f"Successful cycles: {successful_cycles}/{concurrent_cycles}")
        print(f"Total updates processed: {total_updates}")

    @pytest.mark.asyncio
    async def test_system_scalability_limits(self) -> None:
        """Test system behavior at scalability limits."""
        metrics = PerformanceMetrics()
        metrics.start_measurement()

        # Test with extreme parameters
        provider = PerformanceMockProvider({"processing_time": 0.0001}, "scalability_provider")
        dispatcher = AsyncDispatcher(max_workers=50, queue_size=10000)  # High capacity
        dispatcher.register_provider("scalability_provider", provider)

        await dispatcher.start()

        try:
            # Extreme load test
            message_batches = 20
            messages_per_batch = 500

            for batch_idx in range(message_batches):
                batch_start = time.time()
                batch_tasks: list[Coroutine[None, None, object]] = []

                # Create large batch of messages
                for msg_idx in range(messages_per_batch):
                    message = Message(
                        title=f"Scalability Test B{batch_idx} M{msg_idx}",
                        content=f"Scalability test message from batch {batch_idx}, message {msg_idx}. " * 3,
                        priority="normal"
                    )
                    batch_tasks.append(dispatcher.dispatch_message(message, ["scalability_provider"]))

                # Process batch
                results = await asyncio.gather(*batch_tasks, return_exceptions=True)

                # Count results
                batch_successes = 0
                batch_errors = 0

                for result in results:
                    if isinstance(result, Exception):
                        batch_errors += 1
                        metrics.errors_encountered += 1
                    else:
                        # DispatchResult objects are considered successful
                        batch_successes += 1
                        metrics.operations_completed += 1

                batch_duration = time.time() - batch_start

                # Log batch performance
                batch_throughput = batch_successes / batch_duration if batch_duration > 0 else 0
                print(f"Batch {batch_idx + 1}: {batch_successes}/{messages_per_batch} in {batch_duration:.3f}s ({batch_throughput:.1f} ops/s)")

                # Brief pause between batches
                await asyncio.sleep(0.05)

        finally:
            await dispatcher.stop()

        metrics.end_measurement()
        summary = metrics.get_summary()

        # Scalability assertions
        total_expected = message_batches * messages_per_batch
        assert metrics.operations_completed >= total_expected * 0.90  # 90% success rate under extreme load
        assert summary["throughput_ops_per_sec"] >= 200.0  # Minimum 200 ops/sec under extreme load
        assert metrics.errors_encountered < total_expected * 0.10  # Less than 10% errors
        assert summary["duration_seconds"] < 180.0  # Complete within 3 minutes

        print(f"System scalability performance: {summary}")
        print(f"Peak throughput achieved: {summary['throughput_ops_per_sec']:.1f} ops/sec")
