"""
Version checking module.

This module provides functions for checking the current version of the application,
fetching the latest version from GitHub, and comparing versions to determine if
an update is available.
"""

import logging
from typing import TypedDict, cast
import requests

# Get logger for this module
logger = logging.getLogger(__name__)

# GitHub API URL for releases
GITHUB_API_URL = "https://api.github.com/repos/engels74/mover-status/releases"


class UpdateCheckResult(TypedDict, total=False):
    """Type definition for the result of checking for updates."""
    current_version: str
    latest_version: str | None
    update_available: bool
    error: str


def get_current_version() -> str:
    """
    Get the current version of the application from the package __version__.

    Returns:
        str: The current version string (e.g., "0.1.0").
    """
    from mover_status import __version__
    logger.debug(f"Current version: {__version__}")
    return __version__


def get_latest_version() -> str:
    """
    Get the latest version of the application from GitHub releases.

    Returns:
        str: The latest version string (e.g., "0.1.0").

    Raises:
        requests.exceptions.RequestException: If there is an error connecting to GitHub.
        ValueError: If no releases are found or the response is invalid.
    """
    try:
        # Make a request to the GitHub API
        response = requests.get(GITHUB_API_URL, timeout=10)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Parse the response
        releases: list[dict[str, object]] = response.json()  # pyright:ignore[reportAny]

        # Check if there are any releases
        if not releases:
            logger.error("No releases found on GitHub")
            raise ValueError("No releases found")

        # Get the latest release tag
        latest_version = cast(str, releases[0]["tag_name"])

        # Remove 'v' prefix if present
        if latest_version.startswith("v"):
            latest_version = latest_version[1:]

        logger.debug(f"Latest version from GitHub: {latest_version}")
        return latest_version

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching latest version from GitHub: {e}")
        raise


def compare_versions(version1: str, version2: str) -> int:
    """
    Compare two version strings.

    Args:
        version1: The first version string.
        version2: The second version string.

    Returns:
        int: 0 if versions are equal, positive if version1 > version2, negative if version1 < version2.
    """
    # Split versions into components
    v1_parts = [int(x) for x in version1.split(".")]
    v2_parts = [int(x) for x in version2.split(".")]

    # Pad shorter version with zeros
    while len(v1_parts) < len(v2_parts):
        v1_parts.append(0)
    while len(v2_parts) < len(v1_parts):
        v2_parts.append(0)

    # Compare components
    for i in range(len(v1_parts)):
        if v1_parts[i] > v2_parts[i]:
            return 1
        elif v1_parts[i] < v2_parts[i]:
            return -1

    # Versions are equal
    return 0


def check_for_updates() -> UpdateCheckResult:
    """
    Check if a newer version of the application is available.

    Returns:
        UpdateCheckResult: A dictionary containing the current version, latest version,
                          and whether an update is available. If there was an error
                          fetching the latest version, the dictionary will also contain
                          an error message.
    """
    # Get the current version
    current_version = get_current_version()

    try:
        # Get the latest version
        latest_version = get_latest_version()

        # Compare versions
        update_available = compare_versions(latest_version, current_version) > 0

        return {
            "current_version": current_version,
            "latest_version": latest_version,
            "update_available": update_available
        }

    except requests.exceptions.RequestException as e:
        # Handle network errors
        logger.warning(f"Error checking for updates: {e}")
        return {
            "current_version": current_version,
            "latest_version": None,
            "update_available": False,
            "error": str(e)
        }
