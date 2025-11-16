"""Disk usage tracking for monitoring data transfer progress.

This module provides functions for calculating disk usage with support for:
- Synchronous disk traversal with exclusion path filtering
- Baseline disk usage capture at mover process start
- Current usage sampling during mover execution
- Robust error handling for inaccessible paths
- Async integration using asyncio.to_thread for CPU-bound operations
- Caching mechanism to prevent excessive disk I/O
- Configurable sampling intervals
- Context variable preservation across thread boundaries

All synchronous functions are designed to be offloaded to thread pools using
asyncio.to_thread to prevent blocking the main event loop during CPU-bound
disk traversal operations.
"""

import asyncio
import logging
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final

from mover_status.types.models import DiskSample

logger = logging.getLogger(__name__)

# Cache duration for disk usage samples to prevent excessive I/O
# Samples are cached for this duration to avoid redundant calculations
CACHE_DURATION_SECONDS: Final[int] = 30


def is_excluded(path: Path, exclusion_paths: Sequence[Path]) -> bool:
    """Check if a path should be excluded from disk usage calculation.

    A path is excluded if it is a subdirectory of any exclusion path or
    exactly matches an exclusion path.

    Args:
        path: The path to check for exclusion
        exclusion_paths: Sequence of paths to exclude from traversal

    Returns:
        True if the path should be excluded, False otherwise

    Examples:
        >>> is_excluded(
        ...     Path("/mnt/cache/appdata/qbittorrent"),
        ...     [Path("/mnt/cache/appdata")]
        ... )
        True
        >>> is_excluded(
        ...     Path("/mnt/cache/downloads"),
        ...     [Path("/mnt/cache/appdata")]
        ... )
        False
    """
    try:
        for exclusion in exclusion_paths:
            # Check if path is the same as or a subdirectory of exclusion
            if path == exclusion or exclusion in path.parents:
                return True
    except (OSError, ValueError):
        # Path comparison may fail for invalid paths
        return False

    return False


def calculate_disk_usage_sync(
    paths: Iterable[Path],
    *,
    exclusion_paths: Sequence[Path] | None = None,
) -> int:
    """Calculate total disk usage across paths with exclusion filtering.

    Performs synchronous disk traversal to calculate the total bytes used
    across all specified paths, excluding any paths matching exclusion patterns.
    This function is designed to be called from asyncio.to_thread to avoid
    blocking the event loop.

    This function handles errors gracefully:
    - Permission errors for inaccessible files/directories are logged and skipped
    - Filesystem errors (removed files, broken symlinks) are logged and skipped
    - Invalid paths are logged and skipped
    - Errors do not halt traversal; remaining paths continue processing

    Args:
        paths: Iterable of paths to calculate disk usage for
        exclusion_paths: Optional sequence of paths to exclude from calculation
                        (defaults to empty sequence)

    Returns:
        Total disk usage in bytes across all accessible files

    Examples:
        >>> from pathlib import Path
        >>> # Calculate usage for cache directory, excluding appdata
        >>> usage = calculate_disk_usage_sync(
        ...     paths=[Path("/mnt/cache")],
        ...     exclusion_paths=[Path("/mnt/cache/appdata")]
        ... )
        >>> usage >= 0
        True
    """
    if exclusion_paths is None:
        exclusion_paths = []

    total_bytes = 0
    processed_files = 0
    skipped_files = 0
    excluded_paths_count = 0

    for base_path in paths:
        # Validate base path exists and is accessible
        try:
            if not base_path.exists():
                logger.warning(
                    "Base path does not exist, skipping",
                    extra={"path": str(base_path)},
                )
                continue

            # Check if the entire base path is excluded
            if is_excluded(base_path, exclusion_paths):
                logger.debug(
                    "Base path is excluded, skipping",
                    extra={"path": str(base_path)},
                )
                excluded_paths_count += 1
                continue

        except (OSError, PermissionError) as exc:
            logger.warning(
                "Cannot access base path, skipping",
                extra={"path": str(base_path), "error": str(exc)},
            )
            continue

        # Handle single file case
        try:
            if base_path.is_file() and not base_path.is_symlink():
                file_size = base_path.stat().st_size
                total_bytes += file_size
                processed_files += 1
                continue
        except (OSError, PermissionError) as exc:
            logger.warning(
                "Cannot access file, skipping",
                extra={"path": str(base_path), "error": str(exc)},
            )
            continue

        # Traverse directory tree
        try:
            # Use rglob to recursively traverse all files
            for entry in base_path.rglob("*"):
                try:
                    # Skip if path is excluded
                    if is_excluded(entry, exclusion_paths):
                        excluded_paths_count += 1
                        continue

                    # Only count regular files (skip directories, symlinks, etc.)
                    if entry.is_file() and not entry.is_symlink():
                        # Get file size
                        file_size = entry.stat().st_size
                        total_bytes += file_size
                        processed_files += 1

                except PermissionError:
                    # Permission denied for file/directory
                    logger.debug(
                        "Permission denied, skipping",
                        extra={"path": str(entry)},
                    )
                    skipped_files += 1

                except (OSError, FileNotFoundError):
                    # File removed/changed during traversal, broken symlink, etc.
                    logger.debug(
                        "Filesystem error, skipping",
                        extra={"path": str(entry)},
                    )
                    skipped_files += 1

                except Exception as exc:
                    # Unexpected error - log but continue
                    logger.warning(
                        "Unexpected error calculating file size, skipping",
                        extra={"path": str(entry), "error": str(exc)},
                    )
                    skipped_files += 1

        except Exception as exc:
            # Unexpected error during directory traversal
            logger.error(
                "Error traversing directory",
                extra={"path": str(base_path), "error": str(exc)},
            )
            continue

    # Log summary statistics
    logger.info(
        "Disk usage calculation complete",
        extra={
            "total_bytes": total_bytes,
            "processed_files": processed_files,
            "skipped_files": skipped_files,
            "excluded_paths": excluded_paths_count,
        },
    )

    return total_bytes


def capture_baseline(
    paths: Iterable[Path],
    *,
    exclusion_paths: Sequence[Path] | None = None,
) -> DiskSample:
    """Capture baseline disk usage snapshot at mover process start.

    Creates an immutable DiskSample representing the initial state of disk
    usage before data movement begins. This baseline is used by the progress
    calculator to determine how much data has been transferred.

    This function is a thin wrapper around calculate_disk_usage_sync that
    packages the result into a DiskSample with the current timestamp.

    Args:
        paths: Iterable of paths to calculate disk usage for
        exclusion_paths: Optional sequence of paths to exclude from calculation

    Returns:
        DiskSample containing timestamp, total bytes, and consolidated path info

    Examples:
        >>> from pathlib import Path
        >>> baseline = capture_baseline(
        ...     paths=[Path("/mnt/cache")],
        ...     exclusion_paths=[Path("/mnt/cache/appdata")]
        ... )
        >>> baseline.bytes_used >= 0
        True
        >>> isinstance(baseline.timestamp, datetime)
        True
    """
    logger.info("Capturing baseline disk usage snapshot")

    bytes_used = calculate_disk_usage_sync(
        paths=paths,
        exclusion_paths=exclusion_paths,
    )

    # Create consolidated path string for logging and tracking
    path_str = ", ".join(str(p) for p in paths)

    baseline = DiskSample(
        timestamp=datetime.now(),
        bytes_used=bytes_used,
        path=path_str,
    )

    logger.info(
        "Baseline snapshot captured",
        extra={
            "bytes_used": bytes_used,
            "paths": path_str,
            "timestamp": baseline.timestamp.isoformat(),
        },
    )

    return baseline


def sample_current_usage(
    paths: Iterable[Path],
    *,
    exclusion_paths: Sequence[Path] | None = None,
) -> DiskSample:
    """Sample current disk usage during mover execution.

    Creates an immutable DiskSample representing the current state of disk
    usage. This sample is compared against the baseline to calculate progress
    percentage and estimate time of completion.

    This function is identical to capture_baseline in implementation but
    semantically distinct in purpose. It's called periodically during mover
    execution to track ongoing progress, whereas capture_baseline is called
    once at the start.

    Args:
        paths: Iterable of paths to calculate disk usage for
        exclusion_paths: Optional sequence of paths to exclude from calculation

    Returns:
        DiskSample containing timestamp, total bytes, and consolidated path info

    Examples:
        >>> from pathlib import Path
        >>> sample = sample_current_usage(
        ...     paths=[Path("/mnt/cache")],
        ...     exclusion_paths=[Path("/mnt/cache/appdata")]
        ... )
        >>> sample.bytes_used >= 0
        True
    """
    logger.debug("Sampling current disk usage")

    bytes_used = calculate_disk_usage_sync(
        paths=paths,
        exclusion_paths=exclusion_paths,
    )

    # Create consolidated path string
    path_str = ", ".join(str(p) for p in paths)

    sample = DiskSample(
        timestamp=datetime.now(),
        bytes_used=bytes_used,
        path=path_str,
    )

    logger.debug(
        "Current usage sample complete",
        extra={
            "bytes_used": bytes_used,
            "timestamp": sample.timestamp.isoformat(),
        },
    )

    return sample


# Cache for disk usage samples to prevent excessive I/O
# Maps tuple of (paths, exclusion_paths) to (sample, expiry_time)
_sample_cache: dict[tuple[tuple[Path, ...], tuple[Path, ...]], tuple[DiskSample, datetime]] = {}


def _get_cache_key(
    paths: Iterable[Path],
    exclusion_paths: Sequence[Path] | None,
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """Generate cache key from paths and exclusion paths.

    Args:
        paths: Iterable of paths to calculate disk usage for
        exclusion_paths: Optional sequence of paths to exclude

    Returns:
        Tuple of (paths_tuple, exclusions_tuple) for use as cache key
    """
    paths_tuple = tuple(paths)
    exclusions_tuple = tuple(exclusion_paths) if exclusion_paths else ()
    return (paths_tuple, exclusions_tuple)


def _is_cache_valid(expiry_time: datetime) -> bool:
    """Check if cached sample is still valid.

    Args:
        expiry_time: Expiry timestamp for cached sample

    Returns:
        True if cache is still valid, False if expired
    """
    return datetime.now() < expiry_time


async def capture_baseline_async(
    paths: Iterable[Path],
    *,
    exclusion_paths: Sequence[Path] | None = None,
) -> DiskSample:
    """Async wrapper for baseline disk usage capture using asyncio.to_thread.

    Offloads CPU-bound disk traversal to thread pool to prevent blocking the
    event loop. Preserves context variables across the thread boundary for
    proper correlation ID tracking and logging context.

    This function does NOT use caching since baseline is captured only once
    at mover process start and represents the initial state.

    Args:
        paths: Iterable of paths to calculate disk usage for
        exclusion_paths: Optional sequence of paths to exclude from calculation

    Returns:
        DiskSample containing timestamp, total bytes, and consolidated path info

    Examples:
        >>> from pathlib import Path
        >>> baseline = await capture_baseline_async(
        ...     paths=[Path("/mnt/cache")],
        ...     exclusion_paths=[Path("/mnt/cache/appdata")]
        ... )
        >>> baseline.bytes_used >= 0
        True
    """
    logger.info("Capturing baseline disk usage snapshot (async)")

    # Offload CPU-bound calculation to thread pool
    # Context is automatically copied by asyncio.to_thread
    baseline = await asyncio.to_thread(
        capture_baseline,
        paths,
        exclusion_paths=exclusion_paths,
    )

    logger.info(
        "Baseline snapshot captured (async)",
        extra={
            "bytes_used": baseline.bytes_used,
            "timestamp": baseline.timestamp.isoformat(),
        },
    )

    return baseline


async def sample_current_usage_async(
    paths: Iterable[Path],
    *,
    exclusion_paths: Sequence[Path] | None = None,
    cache_duration_seconds: int = CACHE_DURATION_SECONDS,
) -> DiskSample:
    """Async wrapper for current usage sampling with caching support.

    Offloads CPU-bound disk traversal to thread pool to prevent blocking the
    event loop. Implements caching mechanism to prevent excessive disk I/O
    during frequent sampling. Preserves context variables across the thread
    boundary for proper correlation ID tracking and logging context.

    Caching behavior:
    - Cache key is based on paths and exclusion_paths
    - Cache entries expire after cache_duration_seconds
    - Expired entries are automatically removed and recalculated
    - Cache is shared across all calls with same paths/exclusions

    Args:
        paths: Iterable of paths to calculate disk usage for
        exclusion_paths: Optional sequence of paths to exclude from calculation
        cache_duration_seconds: Duration in seconds to cache samples (default: 30)

    Returns:
        DiskSample containing timestamp, total bytes, and consolidated path info

    Examples:
        >>> from pathlib import Path
        >>> # First call performs disk traversal
        >>> sample1 = await sample_current_usage_async(
        ...     paths=[Path("/mnt/cache")],
        ...     exclusion_paths=[Path("/mnt/cache/appdata")]
        ... )
        >>> # Second call within cache duration returns cached result
        >>> sample2 = await sample_current_usage_async(
        ...     paths=[Path("/mnt/cache")],
        ...     exclusion_paths=[Path("/mnt/cache/appdata")]
        ... )
        >>> sample1.bytes_used == sample2.bytes_used
        True
    """
    logger.debug("Sampling current disk usage (async)")

    # Generate cache key
    cache_key = _get_cache_key(paths, exclusion_paths)

    # Check cache for valid entry
    if cache_key in _sample_cache:
        cached_sample, expiry_time = _sample_cache[cache_key]
        if _is_cache_valid(expiry_time):
            logger.debug(
                "Using cached disk usage sample",
                extra={
                    "bytes_used": cached_sample.bytes_used,
                    "cached_at": cached_sample.timestamp.isoformat(),
                    "expires_at": expiry_time.isoformat(),
                },
            )
            return cached_sample
        else:
            logger.debug(
                "Cache expired, recalculating disk usage",
                extra={
                    "expired_at": expiry_time.isoformat(),
                },
            )

    # Cache miss or expired - perform disk traversal
    # Offload CPU-bound calculation to thread pool
    # Context is automatically copied by asyncio.to_thread
    sample = await asyncio.to_thread(
        sample_current_usage,
        paths,
        exclusion_paths=exclusion_paths,
    )

    # Update cache with new sample and expiry time
    expiry_time = datetime.now() + timedelta(seconds=cache_duration_seconds)
    _sample_cache[cache_key] = (sample, expiry_time)

    logger.debug(
        "Current usage sample complete (async)",
        extra={
            "bytes_used": sample.bytes_used,
            "timestamp": sample.timestamp.isoformat(),
            "cache_expires_at": expiry_time.isoformat(),
        },
    )

    return sample


def clear_sample_cache() -> None:
    """Clear the disk usage sample cache.

    This function is useful for testing and for forcing fresh calculations
    when needed (e.g., after configuration changes or when starting a new
    monitoring cycle).

    Examples:
        >>> clear_sample_cache()
        >>> # Next sample_current_usage_async call will perform fresh calculation
    """
    global _sample_cache
    _sample_cache.clear()
    logger.debug("Disk usage sample cache cleared")
