"""Tests for YAML configuration loader."""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest
import yaml

from mover_status.config.loader.yaml_loader import YamlLoader, ConfigLoadError


class TestYamlLoader:
    """Test suite for YamlLoader class."""

    def test_load_valid_yaml_file(self) -> None:
        """Test loading a valid YAML file."""
        loader = YamlLoader()
        test_data = {
            "monitoring": {
                "interval": 30,
                "dry_run": False,
            },
            "process": {
                "name": "mover",
                "path": "/usr/local/sbin/mover",
            },
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            _ = yaml.dump(test_data, f)
            temp_path = Path(f.name)
        
        try:
            result = loader.load(temp_path)
            assert result == test_data
        finally:
            _ = temp_path.unlink()

    def test_load_empty_yaml_file(self) -> None:
        """Test loading an empty YAML file returns empty dict."""
        loader = YamlLoader()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            _ = f.write("")
            temp_path = Path(f.name)
        
        try:
            result = loader.load(temp_path)
            assert result == {}
        finally:
            _ = temp_path.unlink()

    def test_load_none_yaml_file(self) -> None:
        """Test loading YAML file with null content returns empty dict."""
        loader = YamlLoader()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            _ = f.write("null")
            temp_path = Path(f.name)
        
        try:
            result = loader.load(temp_path)
            assert result == {}
        finally:
            _ = temp_path.unlink()

    def test_load_nonexistent_file(self) -> None:
        """Test loading a non-existent file raises ConfigLoadError."""
        loader = YamlLoader()
        nonexistent_path = Path("/non/existent/file.yaml")
        
        with pytest.raises(ConfigLoadError) as exc_info:
            _ = loader.load(nonexistent_path)
        
        assert "Failed to load" in str(exc_info.value)
        assert str(nonexistent_path) in str(exc_info.value)

    def test_load_invalid_yaml_file(self) -> None:
        """Test loading an invalid YAML file raises ConfigLoadError."""
        loader = YamlLoader()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            _ = f.write("invalid: yaml: content: [unclosed")
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(ConfigLoadError) as exc_info:
                _ = loader.load(temp_path)
            
            assert "Failed to load" in str(exc_info.value)
            assert str(temp_path) in str(exc_info.value)
        finally:
            _ = temp_path.unlink()

    def test_load_permission_denied(self) -> None:
        """Test loading file with permission denied raises ConfigLoadError."""
        loader = YamlLoader()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            _ = yaml.dump({"test": "data"}, f)
            temp_path = Path(f.name)
        
        try:
            # Remove read permissions
            _ = temp_path.chmod(0o000)
            
            with pytest.raises(ConfigLoadError) as exc_info:
                _ = loader.load(temp_path)
            
            assert "Failed to load" in str(exc_info.value)
            assert str(temp_path) in str(exc_info.value)
        finally:
            # Restore permissions before cleanup
            _ = temp_path.chmod(0o644)
            _ = temp_path.unlink()

    def test_load_nested_yaml_structure(self) -> None:
        """Test loading complex nested YAML structure."""
        loader = YamlLoader()
        test_data = {
            "providers": {
                "discord": {
                    "webhook_url": "https://discord.com/api/webhooks/test",
                    "embeds": {
                        "enabled": True,
                        "colors": {
                            "started": 0x00ff00,
                            "progress": 0x0099ff,
                            "completed": 0x00cc00,
                            "failed": 0xff0000,
                        },
                    },
                    "notifications": {
                        "rate_limits": {
                            "progress": 300,
                            "status": 60,
                        },
                    },
                },
                "telegram": {
                    "bot_token": "test_token",
                    "chat_ids": [12345, 67890],
                },
            },
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            _ = yaml.dump(test_data, f)
            temp_path = Path(f.name)
        
        try:
            result = loader.load(temp_path)
            assert result == test_data
        finally:
            _ = temp_path.unlink()

    def test_load_yaml_with_special_types(self) -> None:
        """Test loading YAML with special Python types."""
        loader = YamlLoader()
        
        # Use safe_dump to ensure we don't have Python-specific types
        yaml_content = """
        string_val: "test string"
        int_val: 42
        float_val: 3.14
        bool_val: true
        null_val: null
        list_val:
          - item1
          - item2
          - item3
        dict_val:
          nested_key: "nested_value"
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            _ = f.write(yaml_content)
            temp_path = Path(f.name)
        
        try:
            result = loader.load(temp_path)
            
            assert result["string_val"] == "test string"
            assert result["int_val"] == 42
            assert result["float_val"] == 3.14
            assert result["bool_val"] is True
            assert result["null_val"] is None
            assert result["list_val"] == ["item1", "item2", "item3"]
            assert result["dict_val"] == {"nested_key": "nested_value"}
        finally:
            _ = temp_path.unlink()

    def test_load_multiple_files(self) -> None:
        """Test that loader can handle multiple separate load calls."""
        loader = YamlLoader()
        
        # Create first file
        data1 = {"config1": {"value": 1}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f1:
            _ = yaml.dump(data1, f1)
            temp_path1 = Path(f1.name)
        
        # Create second file
        data2 = {"config2": {"value": 2}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f2:
            _ = yaml.dump(data2, f2)
            temp_path2 = Path(f2.name)
        
        try:
            result1 = loader.load(temp_path1)
            result2 = loader.load(temp_path2)
            
            assert result1 == data1
            assert result2 == data2
        finally:
            _ = temp_path1.unlink()
            _ = temp_path2.unlink()