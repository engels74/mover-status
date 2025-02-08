# utils/version.py

"""
Version checking utilities and GitHub release integration.
Provides functionality to check for updates and compare version numbers.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import total_ordering
from typing import Optional

import aiohttp
from structlog import get_logger

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

    CURRENT = "1.0.0"  # Replace with actual current version
    GITHUB_API_URL = "https://api.github.com/repos/engels74/mover-status/releases/latest"

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

    def __init__(self) -> None:
        """Initialize version checker."""
        self._latest_version: Optional[Version] = None
        self._last_check: Optional[datetime] = None
        self._current = Version.from_string(Version.CURRENT)

    @property
    def current_version(self) -> Version:
        """Get current version."""
        return self._current

    def get_version(self) -> str:
        """Get the current version string.

        Returns:
            str: Current version string
        """
        return str(self._current)

    async def get_latest_version(self, force_check: bool = False) -> Version:
        """Get latest version from GitHub releases.

        Args:
            force_check: Force check even if cached result is available

        Returns:
            Version: Latest version from GitHub

        Raises:
            aiohttp.ClientError: If GitHub API request fails
            ValueError: If GitHub API response is invalid or no releases found
        """
        if not force_check and self._is_cache_valid() and self._latest_version is not None:
            return self._latest_version

        async with aiohttp.ClientSession() as session:
            async with session.get(Version.GITHUB_API_URL) as response:
                response.raise_for_status()
                data = await response.json()

        if "tag_name" not in data:
            raise ValueError("Invalid GitHub API response")

        version_str = data["tag_name"].lstrip("v")
        self._latest_version = Version.from_string(version_str)
        self._last_check = datetime.now()

        return self._latest_version

    async def check_for_updates(self) -> tuple[bool, str]:
        """Check if updates are available.

        Returns:
            tuple[bool, str]: (update_available, latest_version_string)
        """
        try:
            latest = await self.get_latest_version()
            return latest > self.current_version, str(latest)
        except Exception as e:
            logger.warning("Failed to check for updates", error=str(e))
            return False, str(self.current_version)

    def _is_cache_valid(self) -> bool:
        """Check if cached version is still valid.

        Returns:
            bool: True if cache is valid, False otherwise
        """
        if not self._latest_version or not self._last_check:
            return False
        cache_age = datetime.now() - self._last_check
        return cache_age < timedelta(hours=1)


# Global version checker instance
version_checker = VersionChecker()
