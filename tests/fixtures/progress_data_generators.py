"""Mock data generators for various progress patterns in testing."""

from __future__ import annotations

import random
import math
from typing import NamedTuple, override, Callable
from collections.abc import Iterator
from decimal import Decimal


class ProgressDataPoint(NamedTuple):
    """A single progress data point for testing."""
    bytes_transferred: int
    timestamp: float
    total_size: int


class TransferPattern:
    """Base class for transfer pattern generators."""
    
    def __init__(self, total_size: int, duration: float) -> None:
        """Initialize pattern with total size and duration."""
        self.total_size: int = total_size
        self.duration: float = duration
    
    def generate(self, _sample_count: int) -> Iterator[ProgressDataPoint]:
        """Generate progress data points for the pattern."""
        raise NotImplementedError


class LinearTransferPattern(TransferPattern):
    """Generates a linear progress pattern with constant transfer rate."""
    
    @override
    def generate(self, sample_count: int) -> Iterator[ProgressDataPoint]:
        """Generate linear progress data points."""
        for i in range(sample_count):
            progress_ratio = i / max(1, sample_count - 1)
            timestamp = progress_ratio * self.duration
            bytes_transferred = int(progress_ratio * self.total_size)
            
            yield ProgressDataPoint(
                bytes_transferred=bytes_transferred,
                timestamp=timestamp,
                total_size=self.total_size
            )


class ExponentialTransferPattern(TransferPattern):
    """Generates exponential progress pattern (fast start, slow finish)."""
    
    def __init__(self, total_size: int, duration: float, decay_factor: float = 2.0) -> None:
        """Initialize with decay factor controlling exponential curve."""
        super().__init__(total_size, duration)
        self.decay_factor: float = decay_factor
    
    @override
    def generate(self, sample_count: int) -> Iterator[ProgressDataPoint]:
        """Generate exponential progress data points."""
        for i in range(sample_count):
            time_ratio = i / max(1, sample_count - 1)
            timestamp = time_ratio * self.duration
            
            # Exponential curve: fast initial progress, then slowing
            progress_ratio = 1.0 - math.exp(-self.decay_factor * time_ratio)
            bytes_transferred = int(progress_ratio * self.total_size)
            
            yield ProgressDataPoint(
                bytes_transferred=bytes_transferred,
                timestamp=timestamp,
                total_size=self.total_size
            )


class LogarithmicTransferPattern(TransferPattern):
    """Generates logarithmic progress pattern (slow start, fast finish)."""
    
    def __init__(self, total_size: int, duration: float, scale_factor: float = 5.0) -> None:
        """Initialize with scale factor controlling logarithmic curve."""
        super().__init__(total_size, duration)
        self.scale_factor: float = scale_factor
    
    @override
    def generate(self, sample_count: int) -> Iterator[ProgressDataPoint]:
        """Generate logarithmic progress data points."""
        for i in range(sample_count):
            time_ratio = i / max(1, sample_count - 1)
            timestamp = time_ratio * self.duration
            
            # Logarithmic curve: slow initial progress, then accelerating
            if time_ratio == 0:
                progress_ratio = 0.0
            else:
                progress_ratio = math.log(1 + self.scale_factor * time_ratio) / math.log(1 + self.scale_factor)
            
            bytes_transferred = int(progress_ratio * self.total_size)
            
            yield ProgressDataPoint(
                bytes_transferred=bytes_transferred,
                timestamp=timestamp,
                total_size=self.total_size
            )


class SinusoidalTransferPattern(TransferPattern):
    """Generates sinusoidal progress pattern with periodic speed variations."""
    
    def __init__(self, total_size: int, duration: float, frequency: float = 2.0, amplitude: float = 0.3) -> None:
        """Initialize with frequency and amplitude of speed variations."""
        super().__init__(total_size, duration)
        self.frequency: float = frequency
        self.amplitude: float = amplitude
    
    @override
    def generate(self, sample_count: int) -> Iterator[ProgressDataPoint]:
        """Generate sinusoidal progress data points."""
        total_progress = 0.0
        
        for i in range(sample_count):
            time_ratio = i / max(1, sample_count - 1)
            timestamp = time_ratio * self.duration
            
            # Base linear progress with sinusoidal variation
            base_rate = 1.0 / self.duration
            variation = self.amplitude * math.sin(2 * math.pi * self.frequency * time_ratio)
            instantaneous_rate = base_rate * (1.0 + variation)
            
            if i > 0:
                time_delta = timestamp - (time_ratio - 1/max(1, sample_count - 1)) * self.duration
                progress_delta = instantaneous_rate * time_delta * self.total_size
                total_progress += progress_delta
            
            # Ensure the final sample reaches exactly 100%
            if i == sample_count - 1:
                bytes_transferred = self.total_size
            else:
                bytes_transferred = min(int(total_progress), self.total_size)
            
            yield ProgressDataPoint(
                bytes_transferred=bytes_transferred,
                timestamp=timestamp,
                total_size=self.total_size
            )


class BurstyTransferPattern(TransferPattern):
    """Generates bursty transfer pattern with alternating fast/slow periods."""
    
    def __init__(self, total_size: int, duration: float, burst_ratio: float = 0.8, burst_frequency: float = 4.0) -> None:
        """Initialize with burst characteristics."""
        super().__init__(total_size, duration)
        self.burst_ratio: float = burst_ratio  # Portion of data transferred during bursts
        self.burst_frequency: float = burst_frequency  # Number of burst cycles
    
    @override
    def generate(self, sample_count: int) -> Iterator[ProgressDataPoint]:
        """Generate bursty progress data points."""
        total_progress = 0.0
        
        for i in range(sample_count):
            time_ratio = i / max(1, sample_count - 1)
            timestamp = time_ratio * self.duration
            
            # Determine if in burst or slow period
            cycle_position = (time_ratio * self.burst_frequency) % 1.0
            is_burst = cycle_position < 0.5  # 50% burst, 50% slow
            
            if is_burst:
                # High rate during burst
                rate_multiplier = 2.0 * self.burst_ratio / 0.5
            else:
                # Low rate during slow period
                rate_multiplier = 2.0 * (1.0 - self.burst_ratio) / 0.5
            
            base_rate = self.total_size / self.duration
            if i > 0:
                time_delta = timestamp - (time_ratio - 1/max(1, sample_count - 1)) * self.duration
                progress_delta = base_rate * rate_multiplier * time_delta
                total_progress += progress_delta
            
            # Ensure the final sample reaches exactly 100%
            if i == sample_count - 1:
                bytes_transferred = self.total_size
            else:
                bytes_transferred = min(int(total_progress), self.total_size)
            
            yield ProgressDataPoint(
                bytes_transferred=bytes_transferred,
                timestamp=timestamp,
                total_size=self.total_size
            )


class StallAndResumePattern(TransferPattern):
    """Generates pattern with periodic stalls and resumes."""
    
    stall_intervals: list[tuple[float, float]]
    
    def __init__(self, total_size: int, duration: float, stall_intervals: list[tuple[float, float]]) -> None:
        """Initialize with list of (start_ratio, end_ratio) for stall periods."""
        super().__init__(total_size, duration)
        self.stall_intervals = stall_intervals
    
    @override
    def generate(self, sample_count: int) -> Iterator[ProgressDataPoint]:
        """Generate stall-and-resume progress data points."""
        total_progress = 0.0
        last_timestamp = 0.0
        
        # Calculate effective duration (excluding stalls)
        stall_duration = sum((end - start) for start, end in self.stall_intervals) * self.duration
        effective_duration = self.duration - stall_duration
        base_rate = self.total_size / effective_duration if effective_duration > 0 else 0
        
        for i in range(sample_count):
            time_ratio = i / max(1, sample_count - 1)
            timestamp = time_ratio * self.duration
            
            # Check if currently in a stall period
            is_stalled = any(start <= time_ratio <= end for start, end in self.stall_intervals)
            
            if not is_stalled and i > 0:
                time_delta = timestamp - last_timestamp
                progress_delta = base_rate * time_delta
                total_progress += progress_delta
            
            # Ensure the final sample reaches exactly 100%
            if i == sample_count - 1:
                bytes_transferred = self.total_size
            else:
                bytes_transferred = min(int(total_progress), self.total_size)
            
            last_timestamp = timestamp
            
            yield ProgressDataPoint(
                bytes_transferred=bytes_transferred,
                timestamp=timestamp,
                total_size=self.total_size
            )


class NoisyTransferPattern(TransferPattern):
    """Generates noisy transfer pattern with random variations."""
    
    def __init__(self, total_size: int, duration: float, noise_level: float = 0.2, seed: int | None = None) -> None:
        """Initialize with noise level (0.0 = no noise, 1.0 = high noise)."""
        super().__init__(total_size, duration)
        self.noise_level: float = noise_level
        if seed is not None:
            random.seed(seed)
    
    @override
    def generate(self, sample_count: int) -> Iterator[ProgressDataPoint]:
        """Generate noisy progress data points."""
        total_progress = 0.0
        base_rate = self.total_size / self.duration
        
        for i in range(sample_count):
            time_ratio = i / max(1, sample_count - 1)
            timestamp = time_ratio * self.duration
            
            if i > 0:
                # Add random noise to the rate
                noise_factor = 1.0 + self.noise_level * (random.random() - 0.5) * 2
                noisy_rate = base_rate * noise_factor
                
                time_delta = timestamp - (time_ratio - 1/max(1, sample_count - 1)) * self.duration
                progress_delta = noisy_rate * time_delta
                total_progress += progress_delta
            
            # Ensure the final sample reaches exactly 100%
            if i == sample_count - 1:
                bytes_transferred = self.total_size
            else:
                bytes_transferred = min(int(total_progress), self.total_size)
            
            yield ProgressDataPoint(
                bytes_transferred=bytes_transferred,
                timestamp=timestamp,
                total_size=self.total_size
            )


class ProgressDataGenerator:
    """Factory class for generating various progress data patterns."""
    
    @staticmethod
    def linear_transfer(total_size: int, duration: float, sample_count: int = 100) -> list[ProgressDataPoint]:
        """Generate linear transfer pattern."""
        pattern = LinearTransferPattern(total_size, duration)
        return list(pattern.generate(sample_count))
    
    @staticmethod
    def exponential_transfer(total_size: int, duration: float, sample_count: int = 100, 
                           decay_factor: float = 2.0) -> list[ProgressDataPoint]:
        """Generate exponential transfer pattern."""
        pattern = ExponentialTransferPattern(total_size, duration, decay_factor)
        return list(pattern.generate(sample_count))
    
    @staticmethod
    def logarithmic_transfer(total_size: int, duration: float, sample_count: int = 100,
                           scale_factor: float = 5.0) -> list[ProgressDataPoint]:
        """Generate logarithmic transfer pattern."""
        pattern = LogarithmicTransferPattern(total_size, duration, scale_factor)
        return list(pattern.generate(sample_count))
    
    @staticmethod
    def sinusoidal_transfer(total_size: int, duration: float, sample_count: int = 100,
                          frequency: float = 2.0, amplitude: float = 0.3) -> list[ProgressDataPoint]:
        """Generate sinusoidal transfer pattern."""
        pattern = SinusoidalTransferPattern(total_size, duration, frequency, amplitude)
        return list(pattern.generate(sample_count))
    
    @staticmethod
    def bursty_transfer(total_size: int, duration: float, sample_count: int = 100,
                       burst_ratio: float = 0.8, burst_frequency: float = 4.0) -> list[ProgressDataPoint]:
        """Generate bursty transfer pattern."""
        pattern = BurstyTransferPattern(total_size, duration, burst_ratio, burst_frequency)
        return list(pattern.generate(sample_count))
    
    @staticmethod
    def stall_and_resume(total_size: int, duration: float, sample_count: int = 100,
                        stall_intervals: list[tuple[float, float]] | None = None) -> list[ProgressDataPoint]:
        """Generate stall-and-resume pattern."""
        if stall_intervals is None:
            stall_intervals = [(0.3, 0.4), (0.7, 0.8)]  # Default stalls at 30-40% and 70-80% time
        pattern = StallAndResumePattern(total_size, duration, stall_intervals)
        return list(pattern.generate(sample_count))
    
    @staticmethod
    def noisy_transfer(total_size: int, duration: float, sample_count: int = 100,
                      noise_level: float = 0.2, seed: int | None = None) -> list[ProgressDataPoint]:
        """Generate noisy transfer pattern."""
        pattern = NoisyTransferPattern(total_size, duration, noise_level, seed)
        return list(pattern.generate(sample_count))
    
    @staticmethod
    def real_world_patterns() -> dict[str, list[ProgressDataPoint]]:
        """Generate collection of realistic transfer patterns."""
        patterns = {}
        
        # Small file - fast transfer
        patterns['small_file_fast'] = ProgressDataGenerator.linear_transfer(
            total_size=1024 * 1024,  # 1MB
            duration=5.0,  # 5 seconds
            sample_count=50
        )
        
        # Large file - slow start, then fast
        patterns['large_file_accelerating'] = ProgressDataGenerator.logarithmic_transfer(
            total_size=10 * 1024 * 1024 * 1024,  # 10GB
            duration=3600.0,  # 1 hour
            sample_count=200,
            scale_factor=3.0
        )
        
        # Network transfer with interruptions
        patterns['network_with_interruptions'] = ProgressDataGenerator.stall_and_resume(
            total_size=500 * 1024 * 1024,  # 500MB
            duration=300.0,  # 5 minutes
            sample_count=150,
            stall_intervals=[(0.2, 0.25), (0.6, 0.7), (0.85, 0.9)]
        )
        
        # WiFi transfer with variable speed
        patterns['wifi_variable_speed'] = ProgressDataGenerator.sinusoidal_transfer(
            total_size=2 * 1024 * 1024 * 1024,  # 2GB
            duration=1800.0,  # 30 minutes
            sample_count=180,
            frequency=3.0,
            amplitude=0.4
        )
        
        # Torrent-like bursty download
        patterns['torrent_bursty'] = ProgressDataGenerator.bursty_transfer(
            total_size=5 * 1024 * 1024 * 1024,  # 5GB
            duration=2400.0,  # 40 minutes
            sample_count=240,
            burst_ratio=0.7,
            burst_frequency=6.0
        )
        
        # Noisy cellular connection
        patterns['cellular_noisy'] = ProgressDataGenerator.noisy_transfer(
            total_size=100 * 1024 * 1024,  # 100MB
            duration=120.0,  # 2 minutes
            sample_count=120,
            noise_level=0.5,
            seed=42
        )
        
        return patterns  # pyright: ignore[reportUnknownVariableType]
    
    @staticmethod
    def generate_high_precision_data(total_size: Decimal, duration: float, 
                                   sample_count: int = 100) -> list[tuple[Decimal, float]]:
        """Generate high-precision progress data using Decimal arithmetic."""
        data_points: list[tuple[Decimal, float]] = []
        
        for i in range(sample_count):
            time_ratio = Decimal(str(i)) / Decimal(str(max(1, sample_count - 1)))
            timestamp = float(time_ratio) * duration
            bytes_transferred = time_ratio * total_size
            
            data_points.append((bytes_transferred, timestamp))
        
        return data_points
    
    @staticmethod
    def generate_edge_case_data() -> dict[str, list[ProgressDataPoint]]:
        """Generate edge case scenarios for testing."""
        edge_cases = {}
        
        # Zero-size transfer
        edge_cases['zero_size'] = [
            ProgressDataPoint(0, 0.0, 0),
            ProgressDataPoint(0, 1.0, 0),
            ProgressDataPoint(0, 2.0, 0),
        ]
        
        # Single byte transfer
        edge_cases['single_byte'] = [
            ProgressDataPoint(0, 0.0, 1),
            ProgressDataPoint(1, 1.0, 1),
        ]
        
        # Instant completion
        edge_cases['instant_completion'] = [
            ProgressDataPoint(0, 0.0, 1000),
            ProgressDataPoint(1000, 0.001, 1000),
        ]
        
        # Very slow transfer (1 byte per second)
        edge_cases['extremely_slow'] = [
            ProgressDataPoint(0, 0.0, 3600),
            ProgressDataPoint(1, 1.0, 3600),
            ProgressDataPoint(2, 2.0, 3600),
            ProgressDataPoint(3, 3.0, 3600),
        ]
        
        # Massive file
        edge_cases['massive_file'] = ProgressDataGenerator.linear_transfer(
            total_size=2**50,  # 1 petabyte
            duration=86400.0,  # 24 hours
            sample_count=24
        )
        
        return edge_cases  # pyright: ignore[reportUnknownVariableType]


# Convenience functions for common test scenarios
def quick_linear_pattern(size_mb: int = 100, duration_seconds: int = 60) -> list[ProgressDataPoint]:
    """Quick linear pattern for simple tests."""
    return ProgressDataGenerator.linear_transfer(
        total_size=size_mb * 1024 * 1024,
        duration=float(duration_seconds),
        sample_count=duration_seconds
    )


def quick_realistic_pattern(scenario: str = 'normal') -> list[ProgressDataPoint]:
    """Quick realistic patterns for common test scenarios."""
    scenarios: dict[str, Callable[[], list[ProgressDataPoint]]] = {
        'normal': lambda: ProgressDataGenerator.linear_transfer(50 * 1024 * 1024, 30.0, 30),
        'slow': lambda: ProgressDataGenerator.exponential_transfer(100 * 1024 * 1024, 300.0, 60),
        'fast': lambda: ProgressDataGenerator.linear_transfer(10 * 1024 * 1024, 5.0, 10),
        'interrupted': lambda: ProgressDataGenerator.stall_and_resume(200 * 1024 * 1024, 120.0, 60),
        'noisy': lambda: ProgressDataGenerator.noisy_transfer(75 * 1024 * 1024, 45.0, 45, 0.3, 123),
    }
    
    return scenarios.get(scenario, scenarios['normal'])()