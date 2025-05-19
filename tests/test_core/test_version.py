"""
Tests for the version checking module.

This module contains tests for the version checking functionality in the core/version.py module.
"""

import pytest
from unittest.mock import patch, MagicMock
import requests


def test_get_current_version() -> None:
    """Test getting the current version from the package."""
    from mover_status.core.version import get_current_version

    # The version should be a string in the format "x.y.z"
    version = get_current_version()
    assert isinstance(version, str)

    # Check that the version follows semantic versioning format (x.y.z)
    parts = version.split(".")
    assert len(parts) >= 2, "Version should have at least major and minor components"

    # Check that the version components are integers
    for part in parts:
        assert part.isdigit(), f"Version component '{part}' should be a number"


def test_get_latest_version_success() -> None:
    """Test getting the latest version from GitHub successfully."""
    from mover_status.core.version import get_latest_version

    # Mock the requests.get function to return a successful response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"tag_name": "1.2.3"}]  # pyright:ignore[reportAny]

    with patch("requests.get", return_value=mock_response):
        version = get_latest_version()
        assert version == "1.2.3"


def test_get_latest_version_no_releases() -> None:
    """Test getting the latest version when there are no releases."""
    from mover_status.core.version import get_latest_version

    # Mock the requests.get function to return an empty list
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = []  # pyright:ignore[reportAny]

    with patch("requests.get", return_value=mock_response):
        with pytest.raises(ValueError, match="No releases found"):
            _ = get_latest_version()


def test_get_latest_version_http_error() -> None:
    """Test handling HTTP errors when getting the latest version."""
    from mover_status.core.version import get_latest_version

    # Mock requests.get to raise an HTTPError
    with patch("requests.get", side_effect=requests.exceptions.HTTPError("404 Client Error")):
        with pytest.raises(requests.exceptions.HTTPError):
            _ = get_latest_version()


def test_get_latest_version_connection_error() -> None:
    """Test handling connection errors when getting the latest version."""
    from mover_status.core.version import get_latest_version

    # Mock requests.get to raise a ConnectionError
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Connection refused")):
        with pytest.raises(requests.exceptions.ConnectionError):
            _ = get_latest_version()


def test_get_latest_version_timeout() -> None:
    """Test handling timeout errors when getting the latest version."""
    from mover_status.core.version import get_latest_version

    # Mock requests.get to raise a Timeout
    with patch("requests.get", side_effect=requests.exceptions.Timeout("Request timed out")):
        with pytest.raises(requests.exceptions.Timeout):
            _ = get_latest_version()


def test_check_for_updates_up_to_date() -> None:
    """Test checking for updates when the current version is up to date."""
    from mover_status.core.version import check_for_updates

    # Mock get_current_version and get_latest_version
    with patch("mover_status.core.version.get_current_version", return_value="1.2.3"):
        with patch("mover_status.core.version.get_latest_version", return_value="1.2.3"):
            result = check_for_updates()
            assert result == {"current_version": "1.2.3", "latest_version": "1.2.3", "update_available": False}


def test_check_for_updates_update_available() -> None:
    """Test checking for updates when an update is available."""
    from mover_status.core.version import check_for_updates

    # Mock get_current_version and get_latest_version
    with patch("mover_status.core.version.get_current_version", return_value="1.2.3"):
        with patch("mover_status.core.version.get_latest_version", return_value="1.3.0"):
            result = check_for_updates()
            assert result == {"current_version": "1.2.3", "latest_version": "1.3.0", "update_available": True}


def test_check_for_updates_network_error() -> None:
    """Test checking for updates when a network error occurs."""
    from mover_status.core.version import check_for_updates

    # Mock get_current_version and get_latest_version
    with patch("mover_status.core.version.get_current_version", return_value="1.2.3"):
        with patch("mover_status.core.version.get_latest_version", side_effect=requests.exceptions.RequestException("Network error")):
            result = check_for_updates()
            assert result == {"current_version": "1.2.3", "latest_version": None, "update_available": False, "error": "Network error"}


def test_compare_versions_equal() -> None:
    """Test comparing versions when they are equal."""
    from mover_status.core.version import compare_versions

    assert compare_versions("1.2.3", "1.2.3") == 0


def test_compare_versions_greater() -> None:
    """Test comparing versions when the first is greater."""
    from mover_status.core.version import compare_versions

    assert compare_versions("1.3.0", "1.2.3") > 0
    assert compare_versions("1.2.4", "1.2.3") > 0
    assert compare_versions("2.0.0", "1.9.9") > 0


def test_compare_versions_less() -> None:
    """Test comparing versions when the first is less."""
    from mover_status.core.version import compare_versions

    assert compare_versions("1.2.3", "1.3.0") < 0
    assert compare_versions("1.2.3", "1.2.4") < 0
    assert compare_versions("1.9.9", "2.0.0") < 0


def test_compare_versions_different_lengths() -> None:
    """Test comparing versions with different numbers of components."""
    from mover_status.core.version import compare_versions

    assert compare_versions("1.2", "1.2.0") == 0
    assert compare_versions("1.2.0", "1.2") == 0
    assert compare_versions("1.2.3", "1.2") > 0
    assert compare_versions("1.2", "1.2.3") < 0
