"""
Data utility module.

This module provides utilities for working with data and file system operations.
It is used primarily for calculating directory sizes and handling exclusions.
"""

import os
import subprocess
import logging
import warnings
from pathlib import Path
from typing import List, Union, Optional

# Get logger for this module
logger = logging.getLogger(__name__)


def format_exclusions(exclusion_paths: List[str]) -> List[str]:
    """
    Format exclusion paths for use with the du command.

    Args:
        exclusion_paths: List of paths to exclude.

    Returns:
        List[str]: Formatted exclusion parameters for du command.
        
    Warns:
        UserWarning: If an exclusion path does not exist.
    """
    formatted_exclusions: List[str] = []
    
    for path in exclusion_paths:
        if not os.path.exists(path):
            warnings.warn(f"Exclusion path {path} does not exist and will be ignored.")
            continue
        
        formatted_exclusions.append(f"--exclude={path}")
    
    return formatted_exclusions


def get_directory_size(directory_path: Union[str, Path], exclusions: Optional[List[str]] = None) -> int:
    """
    Calculate the total size of a directory in bytes.

    This function uses the 'du' command to calculate the size of a directory,
    which is more efficient than walking the directory tree in Python.
    
    Args:
        directory_path: Path to the directory to calculate size for.
        exclusions: Optional list of paths to exclude from the calculation.

    Returns:
        int: Size of the directory in bytes.

    Raises:
        FileNotFoundError: If the directory does not exist.
        RuntimeError: If the directory size calculation fails.
        
    Warns:
        UserWarning: If an exclusion path does not exist.
    """
    # Convert Path to string if necessary
    dir_path_str = str(directory_path)
    
    # Check if directory exists
    if not os.path.isdir(dir_path_str):
        raise FileNotFoundError(f"Directory {dir_path_str} does not exist")
    
    # Format exclusions if provided
    exclusion_params: List[str] = []
    if exclusions:
        exclusion_params = format_exclusions(exclusions)
    
    # Build the du command
    command = ["du", "-sb"] + exclusion_params + [dir_path_str]
    
    try:
        logger.debug(f"Running command: {' '.join(command)}")
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse the output (format: "size path")
        output = result.stdout.strip()
        size_str = output.split()[0]
        
        try:
            size = int(size_str)
            logger.debug(f"Directory {dir_path_str} size: {size} bytes")
            return size
        except ValueError:
            raise RuntimeError(f"Failed to parse directory size: {output}")
        
    except subprocess.SubprocessError as e:
        logger.error(f"Failed to calculate directory size: {e}")
        raise RuntimeError(f"Failed to calculate directory size: {e}")
