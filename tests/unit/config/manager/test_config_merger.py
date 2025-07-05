"""Test suite for configuration merging functionality."""

from __future__ import annotations

import pytest

from mover_status.config.manager.config_merger import ConfigMerger, ConfigMergeError


class TestConfigMerger:
    """Test configuration merging functionality."""

    def test_merge_empty_configs(self) -> None:
        """Test merging empty configurations."""
        merger = ConfigMerger()
        result = merger.merge({}, {})
        assert result == {}

    def test_merge_simple_configs(self) -> None:
        """Test merging simple configuration dictionaries."""
        merger = ConfigMerger()
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = merger.merge(base, override)
        expected = {"a": 1, "b": 3, "c": 4}
        assert result == expected

    def test_merge_nested_configs(self) -> None:
        """Test merging nested configuration dictionaries."""
        merger = ConfigMerger()
        base = {
            "database": {"host": "localhost", "port": 5432},
            "cache": {"ttl": 300}
        }
        override = {
            "database": {"host": "remote", "ssl": True},
            "api": {"timeout": 30}
        }
        result = merger.merge(base, override)
        expected = {
            "database": {"host": "remote", "port": 5432, "ssl": True},
            "cache": {"ttl": 300},
            "api": {"timeout": 30}
        }
        assert result == expected

    def test_merge_deep_nested_configs(self) -> None:
        """Test merging deeply nested configuration dictionaries."""
        merger = ConfigMerger()
        base = {
            "level1": {
                "level2": {
                    "level3": {"value": 1, "keep": True}
                }
            }
        }
        override = {
            "level1": {
                "level2": {
                    "level3": {"value": 2, "new": "added"}
                }
            }
        }
        result = merger.merge(base, override)
        expected = {
            "level1": {
                "level2": {
                    "level3": {"value": 2, "keep": True, "new": "added"}
                }
            }
        }
        assert result == expected

    def test_merge_list_override(self) -> None:
        """Test that lists are completely replaced, not merged."""
        merger = ConfigMerger()
        base = {"items": [1, 2, 3]}
        override = {"items": [4, 5]}
        result = merger.merge(base, override)
        expected = {"items": [4, 5]}
        assert result == expected

    def test_merge_multiple_sources(self) -> None:
        """Test merging multiple configuration sources."""
        merger = ConfigMerger()
        defaults = {"a": 1, "b": {"x": 10, "y": 20}}
        file_config = {"b": {"x": 15, "z": 30}, "c": 3}
        env_config = {"b": {"x": 25}, "d": 4}
        
        result = merger.merge_multiple([defaults, file_config, env_config])
        expected = {
            "a": 1,
            "b": {"x": 25, "y": 20, "z": 30},
            "c": 3,
            "d": 4
        }
        assert result == expected

    def test_merge_with_none_values(self) -> None:
        """Test merging configurations with None values."""
        merger = ConfigMerger()
        base = {"a": 1, "b": None, "c": {"x": 10}}
        override = {"b": 2, "c": None, "d": None}
        result = merger.merge(base, override)
        expected = {"a": 1, "b": 2, "c": None, "d": None}
        assert result == expected

    def test_merge_preserves_original_configs(self) -> None:
        """Test that original configuration dictionaries are not modified."""
        merger = ConfigMerger()
        base = {"a": 1, "b": {"x": 10}}
        override = {"b": {"y": 20}}
        
        # Store original values
        original_base = base.copy()
        original_override = override.copy()
        
        _ = merger.merge(base, override)
        
        # Check that originals are unchanged
        assert base == original_base
        assert override == original_override

    def test_merge_with_audit_trail(self) -> None:
        """Test merging with audit trail tracking."""
        merger = ConfigMerger(track_sources=True)
        base = {"a": 1, "b": {"x": 10}}
        override = {"b": {"y": 20}, "c": 3}
        
        _ = merger.merge(base, override)
        
        # Check that audit trail is tracked
        audit_trail = merger.get_audit_trail()
        assert "a" in audit_trail
        assert "b.x" in audit_trail
        assert "b.y" in audit_trail
        assert "c" in audit_trail

    def test_merge_type_conflicts(self) -> None:
        """Test handling of type conflicts during merge."""
        merger = ConfigMerger()
        base = {"value": {"nested": True}}
        override = {"value": "string"}
        
        # Should replace with override value
        result = merger.merge(base, override)
        assert result == {"value": "string"}

    def test_merge_error_handling(self) -> None:
        """Test error handling in merge operations."""
        merger = ConfigMerger()
        
        # Test with invalid input types
        with pytest.raises(ConfigMergeError):
            _ = merger.merge("not a dict", {})
        
        with pytest.raises(ConfigMergeError):
            _ = merger.merge({}, "not a dict")

    def test_get_audit_trail(self) -> None:
        """Test retrieving audit trail information."""
        merger = ConfigMerger(track_sources=True)
        base = {"a": 1}
        override = {"b": 2}
        
        _ = merger.merge(base, override)
        
        audit_trail = merger.get_audit_trail()
        assert isinstance(audit_trail, dict)
        assert "a" in audit_trail
        assert "b" in audit_trail

    def test_get_audit_trail_when_disabled(self) -> None:
        """Test getting audit trail when tracking is disabled."""
        merger = ConfigMerger(track_sources=False)
        base = {"a": 1}
        override = {"b": 2}
        
        _ = merger.merge(base, override)
        
        audit_trail = merger.get_audit_trail()
        assert audit_trail == {}

    def test_clear_audit_trail(self) -> None:
        """Test clearing audit trail."""
        merger = ConfigMerger(track_sources=True)
        base = {"a": 1}
        override = {"b": 2}
        
        _ = merger.merge(base, override)
        assert merger.get_audit_trail() != {}
        
        merger.clear_audit_trail()
        assert merger.get_audit_trail() == {}

    def test_merge_with_custom_precedence(self) -> None:
        """Test merging with custom precedence rules."""
        merger = ConfigMerger()
        
        # Simulate environment variables having highest precedence
        defaults = {"timeout": 30, "retries": 3}
        file_config = {"timeout": 60, "host": "localhost"}
        env_config = {"timeout": 90}
        
        result = merger.merge_multiple([defaults, file_config, env_config])
        
        # Environment should win for timeout
        assert result["timeout"] == 90
        # File config should provide host
        assert result["host"] == "localhost"
        # Defaults should provide retries
        assert result["retries"] == 3

    def test_merge_empty_source_list(self) -> None:
        """Test merging with empty source list."""
        merger = ConfigMerger()
        result = merger.merge_multiple([])
        assert result == {}

    def test_merge_single_source(self) -> None:
        """Test merging with single source."""
        merger = ConfigMerger()
        source = {"a": 1, "b": 2}
        result = merger.merge_multiple([source])
        assert result == source
        # Should not modify original
        assert source == {"a": 1, "b": 2}