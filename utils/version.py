# utils/version.py

"""
Version checking utilities and GitHub release integration.
Provides functionality to check for updates and compare version numbers.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import total_ordering
from typing import Optional, Tuple

import aiohttp
from structlog import get_logger

from config.constants import (
    CURRENT_VERSION,
    GITHUB_API_RELEASES_URL,
    VERSION_CHECK_INTERVAL,
)

logger = get_logger(__name__)

@total_ordering
@dataclass
class Version:
    """
    Represents a semantic version number.
    Supports comparison operations and parsing from strings.
    """
    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None

    @classmethod
    def from_string(cls, version_str: str) -> "Version":
        """Parse version string into Version object.

        Args:
            version_str: Version string (e.g., "1.2.3" or "1.2.3-beta")

        Returns:
            Version: Parsed version object

        Raises:
            ValueError: If version string format is invalid
        """
        pattern = r"^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9]+))?$"
        match = re.match(pattern, version_str)
        if not match:
            raise ValueError(f"Invalid version format: {version_str}")

        major, minor, patch, prerelease = match.groups()
        return cls(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            prerelease=prerelease,
        )

    def __str__(self) -> str:
        """Convert Version to string."""
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            return f"{base}-{self.prerelease}"
        return base

    def __eq__(self, other: object) -> bool:
        """Compare versions for equality."""
        if not isinstance(other, Version):
            return NotImplemented
        return (
            self.major == other.major
            and self.minor == other.minor
            and self.patch == other.patch
            and self.prerelease == other.prerelease
        )

    def __lt__(self, other: "Version") -> bool:
        """Compare versions for ordering."""
        if not isinstance(other, Version):
            return NotImplemented

        # Compare major.minor.patch
        self_tuple = (self.major, self.minor, self.patch)
        other_tuple = (other.major, other.minor, other.patch)
        if self_tuple != other_tuple:
            return self_tuple < other_tuple

        # Handle prerelease versions
        if self.prerelease is None and other.prerelease is not None:
            return False
        if self.prerelease is not None and other.prerelease is None:
            return True
        return bool(
            self.prerelease
            and other.prerelease
            and self.prerelease < other.prerelease
        )

class VersionChecker:
    """
    Handles version checking against GitHub releases.
    Implements caching to avoid excessive API requests.
    """

    def __init__(self):
        """Initialize version checker."""
        self._latest_version: Optional[Version] = None
        self._last_check: Optional[datetime] = None
        self._current = Version.from_string(CURRENT_VERSION)

    @property
    def current_version(self) -> Version:
        """Get current version."""
        return self._current

    async def get_latest_version(self, force_check: bool = False) -> Version:
        """Get latest version from GitHub releases.

        Args:
            force_check: Force check even if cached result is available

        Returns:
            Version: Latest version from GitHub

        Raises:
            aiohttp.ClientError: If GitHub API request fails
        """
        # Use cached version if available and not expired
        if not force_check and self._is_cache_valid():
            assert self._latest_version is not None
            return self._latest_version

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(GITHUB_API_RELEASES_URL) as response:
                    response.raise_for_status()
                    data = await response.json()

                    if not data:
                        raise ValueError("No releases found")

                    # Get latest release version
                    latest_tag = data[0]["tag_name"].lstrip("v")
                    self._latest_version = Version.from_string(latest_tag)
                    self._last_check = datetime.now()

                    logger.debug(
                        "Version check completed",
                        current_version=str(self._current),
                        latest_version=str(self._latest_version),
                    )

                    return self._latest_version

        except aiohttp.ClientError as err:
            logger.error(
                "Failed to check for updates",
                error=str(err),
                current_version=str(self._current),
            )
            raise

    def _is_cache_valid(self) -> bool:
        """Check if cached version is still valid."""
        if self._latest_version is None or self._last_check is None:
            return False

        cache_age = datetime.now() - self._last_check
        return cache_age < timedelta(seconds=VERSION_CHECK_INTERVAL)

    async def check_for_updates(self) -> Tuple[bool, Optional[str]]:
        """Check if updates are available.

        Returns:
            Tuple[bool, Optional[str]]: (update_available, latest_version_str)
        """
        try:
            latest = await self.get_latest_version()
            if latest > self._current:
                return True, str(latest)
            return False, None
        except Exception as err:
            logger.error("Update check failed", error=str(err))
            return False, None

# Global version checker instance
version_checker = VersionChecker()
