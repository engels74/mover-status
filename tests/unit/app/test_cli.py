"""Tests for CLI interface."""

from __future__ import annotations

import pytest
from click.testing import CliRunner
from pathlib import Path
from unittest.mock import patch, MagicMock

from mover_status.app.cli import cli


class TestCLIBasicFunctionality:
    """Test basic CLI functionality."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    def test_cli_help_command(self, runner: CliRunner) -> None:
        """Test CLI help command displays correctly."""
        result = runner.invoke(cli, ['--help'])
        
        assert result.exit_code == 0
        assert 'Mover Status Monitor' in result.output
        assert 'Track Unraid mover progress' in result.output
        assert '--config' in result.output
        assert '--dry-run' in result.output
        assert '--log-level' in result.output
        assert '--once' in result.output
        assert '--version' in result.output

    def test_cli_version_command(self, runner: CliRunner) -> None:
        """Test CLI version command displays correctly."""
        result = runner.invoke(cli, ['--version'])
        
        assert result.exit_code == 0
        # Version should be displayed in output
        assert 'version' in result.output.lower()

    def test_cli_default_invocation(self, runner: CliRunner) -> None:
        """Test CLI with default parameters."""
        with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
            mock_instance = MagicMock()
            mock_runner.return_value = mock_instance
            
            result = runner.invoke(cli, [])
            
            assert result.exit_code == 0
            mock_runner.assert_called_once()
            mock_instance.run.assert_called_once()  # pyright: ignore[reportAny]

    def test_cli_config_option(self, runner: CliRunner) -> None:
        """Test CLI with config file option."""
        with runner.isolated_filesystem():
            # Create a test config file
            config_path = Path('test_config.yaml')
            _ = config_path.write_text('test: config')
            
            with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                mock_instance = MagicMock()
                mock_runner.return_value = mock_instance
                
                result = runner.invoke(cli, ['--config', str(config_path)])
                
                assert result.exit_code == 0
                mock_runner.assert_called_once()
                call_args = mock_runner.call_args
                assert call_args is not None
                assert call_args.kwargs['config_path'] == config_path

    def test_cli_config_option_short_form(self, runner: CliRunner) -> None:
        """Test CLI with config file option short form."""
        with runner.isolated_filesystem():
            config_path = Path('test_config.yaml')
            _ = config_path.write_text('test: config')
            
            with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                mock_instance = MagicMock()
                mock_runner.return_value = mock_instance
                
                result = runner.invoke(cli, ['-c', str(config_path)])
                
                assert result.exit_code == 0
                mock_runner.assert_called_once()

    def test_cli_dry_run_option(self, runner: CliRunner) -> None:
        """Test CLI with dry-run option."""
        with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
            mock_instance = MagicMock()
            mock_runner.return_value = mock_instance
            
            result = runner.invoke(cli, ['--dry-run'])
            
            assert result.exit_code == 0
            mock_runner.assert_called_once()
            call_args = mock_runner.call_args
            assert call_args is not None
            assert call_args.kwargs['dry_run'] is True

    def test_cli_dry_run_option_short_form(self, runner: CliRunner) -> None:
        """Test CLI with dry-run option short form."""
        with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
            mock_instance = MagicMock()
            mock_runner.return_value = mock_instance
            
            result = runner.invoke(cli, ['-d'])
            
            assert result.exit_code == 0
            mock_runner.assert_called_once()
            call_args = mock_runner.call_args
            assert call_args is not None
            assert call_args.kwargs['dry_run'] is True

    def test_cli_log_level_option(self, runner: CliRunner) -> None:
        """Test CLI with log-level option."""
        log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
        
        for level in log_levels:
            with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                mock_instance = MagicMock()
                mock_runner.return_value = mock_instance
                
                result = runner.invoke(cli, ['--log-level', level])
                
                assert result.exit_code == 0
                mock_runner.assert_called_once()
                call_args = mock_runner.call_args
                assert call_args is not None
                assert call_args.kwargs['log_level'] == level

    def test_cli_log_level_option_short_form(self, runner: CliRunner) -> None:
        """Test CLI with log-level option short form."""
        with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
            mock_instance = MagicMock()
            mock_runner.return_value = mock_instance
            
            result = runner.invoke(cli, ['-l', 'DEBUG'])
            
            assert result.exit_code == 0
            mock_runner.assert_called_once()
            call_args = mock_runner.call_args
            assert call_args is not None
            assert call_args.kwargs['log_level'] == 'DEBUG'

    def test_cli_once_option(self, runner: CliRunner) -> None:
        """Test CLI with once option."""
        with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
            mock_instance = MagicMock()
            mock_runner.return_value = mock_instance
            
            result = runner.invoke(cli, ['--once'])
            
            assert result.exit_code == 0
            mock_runner.assert_called_once()
            call_args = mock_runner.call_args
            assert call_args is not None
            assert call_args.kwargs['run_once'] is True

    def test_cli_once_option_short_form(self, runner: CliRunner) -> None:
        """Test CLI with once option short form."""
        with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
            mock_instance = MagicMock()
            mock_runner.return_value = mock_instance
            
            result = runner.invoke(cli, ['-o'])
            
            assert result.exit_code == 0
            mock_runner.assert_called_once()
            call_args = mock_runner.call_args
            assert call_args is not None
            assert call_args.kwargs['run_once'] is True

    def test_cli_combined_options(self, runner: CliRunner) -> None:
        """Test CLI with multiple options combined."""
        with runner.isolated_filesystem():
            config_path = Path('test_config.yaml')
            _ = config_path.write_text('test: config')
            
            with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                mock_instance = MagicMock()
                mock_runner.return_value = mock_instance
                
                result = runner.invoke(cli, [
                    '--config', str(config_path),
                    '--dry-run',
                    '--log-level', 'DEBUG',
                    '--once'
                ])
                
                assert result.exit_code == 0
                mock_runner.assert_called_once()
                call_args = mock_runner.call_args
                assert call_args is not None
                assert call_args.kwargs['config_path'] == config_path
                assert call_args.kwargs['dry_run'] is True
                assert call_args.kwargs['log_level'] == 'DEBUG'
                assert call_args.kwargs['run_once'] is True


class TestCLIArgumentValidation:
    """Test CLI argument parsing and validation."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    def test_config_path_validation_valid_extension(self, runner: CliRunner) -> None:
        """Test config path validation accepts valid file extensions."""
        with runner.isolated_filesystem():
            # Test valid extensions
            valid_extensions = ['config.yaml', 'config.yml', 'config.json', 'config.toml']

            for config_file in valid_extensions:
                _ = Path(config_file).write_text('test: config')

                with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                    mock_instance = MagicMock()
                    mock_runner.return_value = mock_instance

                    result = runner.invoke(cli, ['--config', config_file])

                    assert result.exit_code == 0, f"Failed for {config_file}"
                    mock_runner.assert_called_once()

    def test_config_path_validation_invalid_extension(self, runner: CliRunner) -> None:
        """Test config path validation rejects invalid file extensions."""
        with runner.isolated_filesystem():
            # Test invalid extensions
            invalid_config = 'config.txt'
            _ = Path(invalid_config).write_text('test: config')

            result = runner.invoke(cli, ['--config', invalid_config])

            # Should fail validation
            assert result.exit_code != 0
            assert 'Invalid configuration file extension' in result.output

    def test_config_path_validation_directory_provided(self, runner: CliRunner) -> None:
        """Test config path validation rejects directories."""
        with runner.isolated_filesystem():
            # Create a directory instead of file
            Path('config_dir').mkdir()

            result = runner.invoke(cli, ['--config', 'config_dir'])

            # Should fail validation
            assert result.exit_code != 0
            assert 'Configuration path must be a file' in result.output

    def test_log_level_case_insensitive(self, runner: CliRunner) -> None:
        """Test log level accepts case-insensitive values."""
        with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
            mock_instance = MagicMock()
            mock_runner.return_value = mock_instance

            # Test various case combinations
            test_cases = ['debug', 'DEBUG', 'Debug', 'info', 'INFO', 'Info']

            for log_level in test_cases:
                result = runner.invoke(cli, ['--log-level', log_level])

                assert result.exit_code == 0, f"Failed for log level: {log_level}"
                mock_runner.assert_called_once()
                call_args = mock_runner.call_args
                assert call_args is not None
                # Should be normalized to uppercase
                assert call_args.kwargs['log_level'] == log_level.upper()
                mock_runner.reset_mock()

    def test_mutually_exclusive_options_validation(self, runner: CliRunner) -> None:
        """Test validation of mutually exclusive options."""
        # For now, we don't have mutually exclusive options, but this test
        # is prepared for future enhancements
        with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
            mock_instance = MagicMock()
            mock_runner.return_value = mock_instance

            # Test that dry-run and once can be used together (they're not mutually exclusive)
            result = runner.invoke(cli, ['--dry-run', '--once'])

            assert result.exit_code == 0
            mock_runner.assert_called_once()
            call_args = mock_runner.call_args
            assert call_args is not None
            assert call_args.kwargs['dry_run'] is True
            assert call_args.kwargs['run_once'] is True

    def test_log_level_validation_with_whitespace(self, runner: CliRunner) -> None:
        """Test log level validation handles whitespace correctly."""
        with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
            mock_instance = MagicMock()
            mock_runner.return_value = mock_instance

            # Test with leading/trailing whitespace
            result = runner.invoke(cli, ['--log-level', '  DEBUG  '])

            assert result.exit_code == 0
            mock_runner.assert_called_once()
            call_args = mock_runner.call_args
            assert call_args is not None
            # Should be normalized to uppercase and trimmed
            assert call_args.kwargs['log_level'] == 'DEBUG'

    def test_log_level_validation_invalid_value(self, runner: CliRunner) -> None:
        """Test log level validation rejects invalid values."""
        result = runner.invoke(cli, ['--log-level', 'INVALID'])

        assert result.exit_code != 0
        assert 'Invalid log level' in result.output
        assert 'Valid options:' in result.output

    def test_config_path_validation_empty_extension(self, runner: CliRunner) -> None:
        """Test config path validation handles files without extensions."""
        with runner.isolated_filesystem():
            # Create a file without extension
            config_file = Path('config')
            _ = config_file.write_text('test: config')

            result = runner.invoke(cli, ['--config', str(config_file)])

            # Should fail validation due to missing extension
            assert result.exit_code != 0
            assert 'Invalid configuration file extension' in result.output

    def test_config_path_validation_case_insensitive_extension(self, runner: CliRunner) -> None:
        """Test config path validation handles case-insensitive extensions."""
        with runner.isolated_filesystem():
            # Test uppercase extension
            config_file = Path('config.YAML')
            _ = config_file.write_text('test: config')

            with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                mock_instance = MagicMock()
                mock_runner.return_value = mock_instance

                result = runner.invoke(cli, ['--config', str(config_file)])

                assert result.exit_code == 0
                mock_runner.assert_called_once()


class TestCLIErrorHandling:
    """Test CLI error handling."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    def test_cli_invalid_log_level(self, runner: CliRunner) -> None:
        """Test CLI with invalid log level."""
        result = runner.invoke(cli, ['--log-level', 'INVALID'])

        assert result.exit_code != 0
        assert 'Invalid value' in result.output

    def test_cli_nonexistent_config_file(self, runner: CliRunner) -> None:
        """Test CLI with nonexistent config file."""
        with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
            mock_instance = MagicMock()
            mock_runner.return_value = mock_instance

            result = runner.invoke(cli, ['--config', 'nonexistent.yaml'])

            # CLI should accept nonexistent config files and let the application handle it
            assert result.exit_code == 0
            mock_runner.assert_called_once()
            call_args = mock_runner.call_args
            assert call_args is not None
            assert call_args.kwargs['config_path'] == Path('nonexistent.yaml')

    def test_cli_keyboard_interrupt_handling(self, runner: CliRunner) -> None:
        """Test CLI handles KeyboardInterrupt gracefully."""
        with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
            mock_instance = MagicMock()
            mock_runner.return_value = mock_instance
            mock_instance.run.side_effect = KeyboardInterrupt()  # pyright: ignore[reportAny]
            
            result = runner.invoke(cli, [])
            
            assert result.exit_code == 0
            assert 'Shutting down gracefully' in result.output

    def test_cli_application_exception_handling(self, runner: CliRunner) -> None:
        """Test CLI handles application exceptions."""
        with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
            mock_instance = MagicMock()
            mock_runner.return_value = mock_instance
            mock_instance.run.side_effect = RuntimeError("Test error")  # pyright: ignore[reportAny]
            
            result = runner.invoke(cli, [])
            
            assert result.exit_code != 0
            assert 'Error: Test error' in result.output


class TestCLIDefaults:
    """Test CLI default values."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    def test_cli_default_values(self, runner: CliRunner) -> None:
        """Test CLI uses correct default values."""
        with runner.isolated_filesystem():
            with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                mock_instance = MagicMock()
                mock_runner.return_value = mock_instance

                result = runner.invoke(cli, [])

                assert result.exit_code == 0
                mock_runner.assert_called_once()
                call_args = mock_runner.call_args
                assert call_args is not None

                # Check default values - config_path should be discovered (defaults to config.yaml if none found)
                assert call_args.kwargs['config_path'] == Path('config.yaml')
                assert call_args.kwargs['dry_run'] is False
                assert call_args.kwargs['log_level'] == 'INFO'
                assert call_args.kwargs['run_once'] is False


class TestCLIConfigurationFileSupport:
    """Test CLI configuration file discovery and loading."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    def test_config_file_discovery_current_directory(self, runner: CliRunner) -> None:
        """Test configuration file discovery in current directory."""
        with runner.isolated_filesystem():
            # Create config files in order of precedence
            config_files = ['config.yaml', 'config.yml', 'config.json', 'config.toml']

            for config_file in config_files:
                _ = Path(config_file).write_text(f'test: {config_file}')

                with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                    mock_instance = MagicMock()
                    mock_runner.return_value = mock_instance

                    # Test without explicit config - should discover the file
                    result = runner.invoke(cli, [])

                    assert result.exit_code == 0
                    mock_runner.assert_called_once()
                    call_args = mock_runner.call_args
                    assert call_args is not None
                    # Should use discovered config file
                    assert call_args.kwargs['config_path'] == Path(config_file)

                # Clean up for next iteration
                Path(config_file).unlink()

    def test_config_file_discovery_precedence(self, runner: CliRunner) -> None:
        """Test configuration file discovery precedence order."""
        with runner.isolated_filesystem():
            # Create multiple config files - should prefer .yaml over others
            _ = Path('config.toml').write_text('test: toml')
            _ = Path('config.json').write_text('{"test": "json"}')
            _ = Path('config.yml').write_text('test: yml')
            _ = Path('config.yaml').write_text('test: yaml')

            with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                mock_instance = MagicMock()
                mock_runner.return_value = mock_instance

                result = runner.invoke(cli, [])

                assert result.exit_code == 0
                mock_runner.assert_called_once()
                call_args = mock_runner.call_args
                assert call_args is not None
                # Should prefer .yaml over other formats
                assert call_args.kwargs['config_path'] == Path('config.yaml')

    def test_config_file_discovery_home_directory(self, runner: CliRunner) -> None:
        """Test configuration file discovery in home directory."""
        with runner.isolated_filesystem():
            # Create a fake home directory structure
            home_dir = Path('fake_home')
            home_dir.mkdir()
            config_file = home_dir / '.mover-status.yaml'
            _ = config_file.write_text('test: home_config')

            with patch('pathlib.Path.home', return_value=home_dir):
                with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                    mock_instance = MagicMock()
                    mock_runner.return_value = mock_instance

                    result = runner.invoke(cli, [])

                    assert result.exit_code == 0
                    mock_runner.assert_called_once()
                    call_args = mock_runner.call_args
                    assert call_args is not None
                    # Should discover config in home directory
                    assert call_args.kwargs['config_path'] == config_file

    def test_config_file_discovery_system_directory(self, runner: CliRunner) -> None:
        """Test configuration file discovery in system directory."""
        with runner.isolated_filesystem():
            # Create a fake system config directory
            system_dir = Path('fake_etc')
            system_dir.mkdir()
            config_file = system_dir / 'mover-status.yaml'
            _ = config_file.write_text('test: system_config')

            with patch('mover_status.app.cli.SYSTEM_CONFIG_PATHS', [system_dir / 'mover-status.yaml']):
                with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                    mock_instance = MagicMock()
                    mock_runner.return_value = mock_instance

                    result = runner.invoke(cli, [])

                    assert result.exit_code == 0
                    mock_runner.assert_called_once()
                    call_args = mock_runner.call_args
                    assert call_args is not None
                    # Should discover config in system directory
                    assert call_args.kwargs['config_path'] == config_file

    def test_config_file_discovery_precedence_order(self, runner: CliRunner) -> None:
        """Test configuration file discovery follows correct precedence order."""
        with runner.isolated_filesystem():
            # Create config files in different locations
            current_config = Path('config.yaml')
            _ = current_config.write_text('location: current')

            home_dir = Path('fake_home')
            home_dir.mkdir()
            home_config = home_dir / '.mover-status.yaml'
            _ = home_config.write_text('location: home')

            system_dir = Path('fake_etc')
            system_dir.mkdir()
            system_config = system_dir / 'mover-status.yaml'
            _ = system_config.write_text('location: system')

            with patch('pathlib.Path.home', return_value=home_dir):
                with patch('mover_status.app.cli.SYSTEM_CONFIG_PATHS', [system_config]):
                    with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                        mock_instance = MagicMock()
                        mock_runner.return_value = mock_instance

                        result = runner.invoke(cli, [])

                        assert result.exit_code == 0
                        mock_runner.assert_called_once()
                        call_args = mock_runner.call_args
                        assert call_args is not None
                        # Should prefer current directory over home/system
                        assert call_args.kwargs['config_path'] == current_config

    def test_explicit_config_overrides_discovery(self, runner: CliRunner) -> None:
        """Test explicit config option overrides automatic discovery."""
        with runner.isolated_filesystem():
            # Create discovered config
            _ = Path('config.yaml').write_text('location: discovered')

            # Create explicit config
            explicit_config = Path('explicit.yaml')
            _ = explicit_config.write_text('location: explicit')

            with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                mock_instance = MagicMock()
                mock_runner.return_value = mock_instance

                result = runner.invoke(cli, ['--config', str(explicit_config)])

                assert result.exit_code == 0
                mock_runner.assert_called_once()
                call_args = mock_runner.call_args
                assert call_args is not None
                # Should use explicit config, not discovered one
                assert call_args.kwargs['config_path'] == explicit_config

    def test_config_discovery_no_files_found(self, runner: CliRunner) -> None:
        """Test configuration discovery when no config files are found."""
        with runner.isolated_filesystem():
            # Don't create any config files
            with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                mock_instance = MagicMock()
                mock_runner.return_value = mock_instance

                result = runner.invoke(cli, [])

                assert result.exit_code == 0
                mock_runner.assert_called_once()
                call_args = mock_runner.call_args
                assert call_args is not None
                # Should fall back to default config.yaml
                assert call_args.kwargs['config_path'] == Path('config.yaml')

    def test_config_discovery_home_directory_error_handling(self, runner: CliRunner) -> None:
        """Test configuration discovery handles home directory access errors gracefully."""
        with runner.isolated_filesystem():
            # Mock Path.home() to raise an exception
            with patch('pathlib.Path.home', side_effect=OSError("Cannot access home directory")):
                with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                    mock_instance = MagicMock()
                    mock_runner.return_value = mock_instance

                    result = runner.invoke(cli, [])

                    assert result.exit_code == 0
                    mock_runner.assert_called_once()
                    call_args = mock_runner.call_args
                    assert call_args is not None
                    # Should fall back to default config.yaml when home access fails
                    assert call_args.kwargs['config_path'] == Path('config.yaml')

    def test_config_discovery_mixed_file_types(self, runner: CliRunner) -> None:
        """Test configuration discovery with mixed file types in different locations."""
        with runner.isolated_filesystem():
            # Create config files of different types in different locations
            home_dir = Path('fake_home')
            home_dir.mkdir()

            # Create TOML in home (lower precedence)
            home_config = home_dir / '.mover-status.toml'
            _ = home_config.write_text('[test]\nvalue = "home_toml"')

            # Create JSON in current directory (higher precedence)
            current_config = Path('config.json')
            _ = current_config.write_text('{"test": {"value": "current_json"}}')

            with patch('pathlib.Path.home', return_value=home_dir):
                with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                    mock_instance = MagicMock()
                    mock_runner.return_value = mock_instance

                    result = runner.invoke(cli, [])

                    assert result.exit_code == 0
                    mock_runner.assert_called_once()
                    call_args = mock_runner.call_args
                    assert call_args is not None
                    # Should prefer current directory JSON over home directory TOML
                    assert call_args.kwargs['config_path'] == current_config


class TestCLIUtilityFunctions:
    """Test CLI utility functions."""

    def test_sanitize_string_input_none_value(self) -> None:
        """Test sanitize_string_input with None value."""
        from mover_status.app.cli import sanitize_string_input
        
        result = sanitize_string_input(None)
        assert result is None

    def test_sanitize_string_input_empty_string(self) -> None:
        """Test sanitize_string_input with empty string."""
        from mover_status.app.cli import sanitize_string_input
        
        result = sanitize_string_input("")
        assert result is None

    def test_sanitize_string_input_whitespace_only(self) -> None:
        """Test sanitize_string_input with whitespace-only string."""
        from mover_status.app.cli import sanitize_string_input
        
        result = sanitize_string_input("   \t  \n  ")
        assert result is None

    def test_sanitize_string_input_valid_string(self) -> None:
        """Test sanitize_string_input with valid string."""
        from mover_status.app.cli import sanitize_string_input
        
        result = sanitize_string_input("  hello world  ")
        assert result == "hello world"

    def test_sanitize_string_input_no_trimming_needed(self) -> None:
        """Test sanitize_string_input with string that doesn't need trimming."""
        from mover_status.app.cli import sanitize_string_input
        
        result = sanitize_string_input("hello world")
        assert result == "hello world"

    def test_validate_log_level_none_value(self) -> None:
        """Test validate_log_level with None value."""
        from mover_status.app.cli import validate_log_level
        import click
        
        # Create mock context and parameter
        ctx = click.Context(click.Command('test'))
        param = click.Option(['--log-level'])
        
        result = validate_log_level(ctx, param, None)
        assert result is None

    def test_validate_config_path_none_value(self) -> None:
        """Test validate_config_path with None value."""
        from mover_status.app.cli import validate_config_path
        import click
        
        # Create mock context and parameter
        ctx = click.Context(click.Command('test'))
        param = click.Option(['--config'])
        
        result = validate_config_path(ctx, param, None)
        assert result is None


class TestCLIVersionHandling:
    """Test CLI version handling and error cases."""

    def test_version_import_error_handling(self) -> None:
        """Test version import error handling."""
        # Test the exception handling by patching importlib.metadata.version
        with patch('importlib.metadata.version', side_effect=ImportError("Module not found")):
            # Import a fresh copy of the CLI module to trigger the error handling
            import sys
            if 'mover_status.app.cli' in sys.modules:
                del sys.modules['mover_status.app.cli']
            
            # Now import it again to trigger the ImportError handling
            import mover_status.app.cli
            
            # Check that the version falls back to "unknown"
            assert mover_status.app.cli.__version__ == "unknown"


class TestCLIIntegrationWorkflows:
    """Test complete CLI integration workflows."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    def test_complete_monitoring_workflow(self, runner: CliRunner) -> None:
        """Test complete monitoring workflow from start to finish."""
        with runner.isolated_filesystem():
            # Create a complete config file
            config_content = """
monitoring:
  interval: 30
  mover_check_interval: 10
  
notifications:
  discord:
    webhook_url: "https://discord.com/api/webhooks/test"
    enabled: true
"""
            config_path = Path('config.yaml')
            _ = config_path.write_text(config_content)
            
            with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                mock_instance = MagicMock()
                mock_runner.return_value = mock_instance
                
                # Test the complete workflow
                result = runner.invoke(cli, [
                    '--config', str(config_path),
                    '--log-level', 'DEBUG',
                    '--dry-run'
                ])
                
                assert result.exit_code == 0
                mock_runner.assert_called_once()
                call_args = mock_runner.call_args
                assert call_args is not None
                assert call_args.kwargs['config_path'] == config_path
                assert call_args.kwargs['log_level'] == 'DEBUG'
                assert call_args.kwargs['dry_run'] is True
                assert call_args.kwargs['run_once'] is False
                mock_instance.run.assert_called_once()  # pyright: ignore[reportAny]

    def test_one_shot_monitoring_workflow(self, runner: CliRunner) -> None:
        """Test one-shot monitoring workflow."""
        with runner.isolated_filesystem():
            with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                mock_instance = MagicMock()
                mock_runner.return_value = mock_instance
                
                # Test one-shot execution
                result = runner.invoke(cli, ['--once', '--log-level', 'WARNING'])
                
                assert result.exit_code == 0
                mock_runner.assert_called_once()
                call_args = mock_runner.call_args
                assert call_args is not None
                assert call_args.kwargs['run_once'] is True
                assert call_args.kwargs['log_level'] == 'WARNING'
                mock_instance.run.assert_called_once()  # pyright: ignore[reportAny]

    def test_config_discovery_with_various_scenarios(self, runner: CliRunner) -> None:
        """Test configuration discovery in various realistic scenarios."""
        with runner.isolated_filesystem():
            # Scenario 1: Multiple config files exist, should pick the first one
            config_files = [
                ('config.yaml', 'primary: config'),
                ('config.json', '{"secondary": "config"}'),
                ('config.toml', '[tertiary]\nvalue = "config"')
            ]
            
            for filename, content in config_files:
                _ = Path(filename).write_text(content)
            
            with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                mock_instance = MagicMock()
                mock_runner.return_value = mock_instance
                
                result = runner.invoke(cli, ['--dry-run'])
                
                assert result.exit_code == 0
                mock_runner.assert_called_once()
                call_args = mock_runner.call_args
                assert call_args is not None
                # Should pick the first one in precedence order (config.yaml)
                assert call_args.kwargs['config_path'] == Path('config.yaml')

    def test_error_propagation_workflow(self, runner: CliRunner) -> None:
        """Test error propagation in complete workflow."""
        with runner.isolated_filesystem():
            with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                mock_instance = MagicMock()
                mock_runner.return_value = mock_instance
                
                # Test that ValueError is properly converted to ClickException
                test_error = ValueError("Configuration validation failed")
                mock_instance.run.side_effect = test_error  # pyright: ignore[reportAny]
                
                result = runner.invoke(cli, ['--config', 'test.yaml'])
                
                assert result.exit_code != 0
                assert "Configuration validation failed" in result.output
                mock_runner.assert_called_once()


class TestCLIEdgeCases:
    """Test CLI edge cases and boundary conditions."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    def test_config_validation_with_special_characters(self, runner: CliRunner) -> None:
        """Test config path validation with special characters."""
        with runner.isolated_filesystem():
            # Test with special characters in filename
            special_config = Path('config-with-special_chars.yaml')
            _ = special_config.write_text('test: config')
            
            with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                mock_instance = MagicMock()
                mock_runner.return_value = mock_instance
                
                result = runner.invoke(cli, ['--config', str(special_config)])
                
                assert result.exit_code == 0
                mock_runner.assert_called_once()

    def test_config_validation_with_unicode_filename(self, runner: CliRunner) -> None:
        """Test config path validation with unicode characters."""
        with runner.isolated_filesystem():
            # Test with unicode characters in filename
            unicode_config = Path('配置文件.yaml')
            _ = unicode_config.write_text('test: config')
            
            with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                mock_instance = MagicMock()
                mock_runner.return_value = mock_instance
                
                result = runner.invoke(cli, ['--config', str(unicode_config)])
                
                assert result.exit_code == 0
                mock_runner.assert_called_once()

    def test_log_level_validation_empty_string(self, runner: CliRunner) -> None:
        """Test log level validation with empty string."""
        result = runner.invoke(cli, ['--log-level', ''])
        
        assert result.exit_code != 0
        assert 'Invalid log level' in result.output

    def test_multiple_config_extensions_precedence(self, runner: CliRunner) -> None:
        """Test that .yaml takes precedence over .yml when both exist."""
        with runner.isolated_filesystem():
            # Create both .yaml and .yml files
            _ = Path('config.yml').write_text('format: yml')
            _ = Path('config.yaml').write_text('format: yaml')
            
            with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                mock_instance = MagicMock()
                mock_runner.return_value = mock_instance
                
                result = runner.invoke(cli, [])
                
                assert result.exit_code == 0
                mock_runner.assert_called_once()
                call_args = mock_runner.call_args
                assert call_args is not None
                # Should prefer .yaml over .yml
                assert call_args.kwargs['config_path'] == Path('config.yaml')

    def test_config_path_with_relative_paths(self, runner: CliRunner) -> None:
        """Test config path handling with relative paths."""
        with runner.isolated_filesystem():
            # Create nested directory structure
            nested_dir = Path('configs')
            nested_dir.mkdir()
            nested_config = nested_dir / 'nested.yaml'
            _ = nested_config.write_text('nested: config')
            
            with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
                mock_instance = MagicMock()
                mock_runner.return_value = mock_instance
                
                result = runner.invoke(cli, ['--config', 'configs/nested.yaml'])
                
                assert result.exit_code == 0
                mock_runner.assert_called_once()
                call_args = mock_runner.call_args
                assert call_args is not None
                assert call_args.kwargs['config_path'] == Path('configs/nested.yaml')

    def test_discover_config_file_direct_call(self) -> None:
        """Test discover_config_file function directly."""
        from mover_status.app.cli import discover_config_file
        
        # Test the function directly to ensure it returns the expected default
        with patch('pathlib.Path.exists', return_value=False):
            result = discover_config_file()
            assert result == Path('config.yaml')


# Shell completion and documentation generation test classes removed
# These features are not needed for containerized Docker environment
