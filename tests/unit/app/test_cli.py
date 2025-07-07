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
        with patch('mover_status.app.runner.ApplicationRunner') as mock_runner:
            mock_instance = MagicMock()
            mock_runner.return_value = mock_instance
            
            result = runner.invoke(cli, [])
            
            assert result.exit_code == 0
            mock_runner.assert_called_once()
            call_args = mock_runner.call_args
            assert call_args is not None
            
            # Check default values
            assert call_args.kwargs['config_path'] == Path('config.yaml')
            assert call_args.kwargs['dry_run'] is False
            assert call_args.kwargs['log_level'] == 'INFO'
            assert call_args.kwargs['run_once'] is False
