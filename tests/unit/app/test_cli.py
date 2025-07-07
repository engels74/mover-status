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


class TestCLIShellCompletion:
    """Test CLI shell completion functionality."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    def test_completion_command_exists(self, runner: CliRunner) -> None:
        """Test completion command is available."""
        result = runner.invoke(cli, ['completion', '--help'])
        
        assert result.exit_code == 0
        assert 'Generate shell completion scripts' in result.output
        assert '--shell' in result.output
        assert '--install' in result.output

    def test_completion_bash_generation(self, runner: CliRunner) -> None:
        """Test bash completion script generation."""
        result = runner.invoke(cli, ['completion', '--shell', 'bash'])
        
        assert result.exit_code == 0
        # Should provide installation instructions
        assert 'bashrc' in result.output.lower()
        assert 'COMPLETE' in result.output

    def test_completion_zsh_generation(self, runner: CliRunner) -> None:
        """Test zsh completion script generation."""
        result = runner.invoke(cli, ['completion', '--shell', 'zsh'])
        
        assert result.exit_code == 0
        # Should provide installation instructions
        assert 'zshrc' in result.output.lower()
        assert 'COMPLETE' in result.output

    def test_completion_fish_generation(self, runner: CliRunner) -> None:
        """Test fish completion script generation."""
        result = runner.invoke(cli, ['completion', '--shell', 'fish'])
        
        assert result.exit_code == 0
        # Should provide installation instructions
        assert 'fish' in result.output.lower()
        assert 'COMPLETE' in result.output

    def test_completion_invalid_shell(self, runner: CliRunner) -> None:
        """Test completion with invalid shell type."""
        result = runner.invoke(cli, ['completion', '--shell', 'invalid'])
        
        assert result.exit_code != 0
        assert 'Invalid value' in result.output

    def test_completion_install_bash(self, runner: CliRunner) -> None:
        """Test bash completion installation."""
        with runner.isolated_filesystem():
            # Create a fake bashrc file
            bashrc_path = Path('.bashrc')
            _ = bashrc_path.write_text('# existing content\n')
            
            with patch('os.path.expanduser', return_value=str(bashrc_path.resolve())):
                result = runner.invoke(cli, ['completion', '--shell', 'bash', '--install'])
                
                assert result.exit_code == 0
                assert 'completion installed' in result.output
                
                # Check that completion was added to bashrc
                content = bashrc_path.read_text()
                assert 'cli' in content  # prog_name from Click context
                assert 'COMPLETE' in content

    def test_completion_install_already_exists(self, runner: CliRunner) -> None:
        """Test completion installation when already installed."""
        with runner.isolated_filesystem():
            # Create a bashrc with completion already installed
            bashrc_path = Path('.bashrc')
            completion_line = 'eval "$(_CLI_COMPLETE=bash_source cli)"'
            _ = bashrc_path.write_text(f'# existing content\n{completion_line}\n')
            
            with patch('os.path.expanduser', return_value=str(bashrc_path.resolve())):
                result = runner.invoke(cli, ['completion', '--shell', 'bash', '--install'])
                
                assert result.exit_code == 0
                assert 'already installed' in result.output

    def test_completion_install_zsh(self, runner: CliRunner) -> None:
        """Test zsh completion installation."""
        with runner.isolated_filesystem():
            # Create a fake zshrc file
            zshrc_path = Path('.zshrc')
            _ = zshrc_path.write_text('# existing content\n')
            
            with patch('os.path.expanduser', return_value=str(zshrc_path.resolve())):
                result = runner.invoke(cli, ['completion', '--shell', 'zsh', '--install'])
                
                assert result.exit_code == 0
                assert 'completion installed' in result.output
                
                # Check that completion was added to zshrc
                content = zshrc_path.read_text()
                assert 'cli' in content  # prog_name from Click context
                assert 'COMPLETE' in content

    def test_completion_install_fish(self, runner: CliRunner) -> None:
        """Test fish completion installation."""
        with runner.isolated_filesystem():
            # Create a fake fish config directory and file
            fish_config_dir = Path('.config/fish')
            fish_config_dir.mkdir(parents=True)
            fish_config_path = fish_config_dir / 'config.fish'
            _ = fish_config_path.write_text('# existing content\n')
            
            # Mock expanduser to return the fish config path
            with patch('os.path.expanduser', return_value=str(fish_config_path.resolve())):
                # Mock makedirs to do nothing (it's already created)
                with patch('os.makedirs'):
                    result = runner.invoke(cli, ['completion', '--shell', 'fish', '--install'])
                    
                    assert result.exit_code == 0
                    assert 'completion installed' in result.output
                    
                    # Check that completion was added to fish config
                    content = fish_config_path.read_text()
                    assert 'cli' in content  # prog_name from Click context
                    assert 'COMPLETE' in content

    def test_completion_install_file_error(self, runner: CliRunner) -> None:
        """Test completion installation with file access error."""
        with patch('os.path.expanduser', return_value='/nonexistent/path/.bashrc'):
            result = runner.invoke(cli, ['completion', '--shell', 'bash', '--install'])
            
            assert result.exit_code != 0
            assert 'Failed to install completion' in result.output

    def test_completion_short_form_options(self, runner: CliRunner) -> None:
        """Test completion command with short form options."""
        result = runner.invoke(cli, ['completion', '-s', 'bash', '-i'])
        
        # Should not fail, but may not actually install without proper filesystem setup
        assert result.exit_code in [0, 1]  # Allow both success and expected failure


class TestCLIDocumentationGeneration:
    """Test CLI documentation generation functionality."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    def test_docs_command_exists(self, runner: CliRunner) -> None:
        """Test docs command is available."""
        result = runner.invoke(cli, ['docs', '--help'])
        
        assert result.exit_code == 0
        assert 'Generate documentation' in result.output
        assert '--format' in result.output
        assert '--output' in result.output

    def test_docs_text_format(self, runner: CliRunner) -> None:
        """Test text documentation generation."""
        result = runner.invoke(cli, ['docs', '--format', 'text'])
        
        assert result.exit_code == 0
        assert 'MOVER STATUS MONITOR' in result.output
        assert 'SYNOPSIS' in result.output
        assert 'DESCRIPTION' in result.output
        assert 'OPTIONS' in result.output
        assert 'EXAMPLES' in result.output

    def test_docs_man_format(self, runner: CliRunner) -> None:
        """Test man page documentation generation."""
        result = runner.invoke(cli, ['docs', '--format', 'man'])
        
        assert result.exit_code == 0
        assert '.TH MOVER-STATUS' in result.output
        assert '.SH NAME' in result.output
        assert '.SH SYNOPSIS' in result.output
        assert '.SH DESCRIPTION' in result.output
        assert '.SH OPTIONS' in result.output
        assert '.SH EXAMPLES' in result.output

    def test_docs_markdown_format(self, runner: CliRunner) -> None:
        """Test markdown documentation generation."""
        result = runner.invoke(cli, ['docs', '--format', 'markdown'])
        
        assert result.exit_code == 0
        assert '# Mover Status Monitor CLI' in result.output
        assert '## Synopsis' in result.output
        assert '## Description' in result.output
        assert '## Options' in result.output
        assert '## Examples' in result.output
        assert '```bash' in result.output

    def test_docs_default_format(self, runner: CliRunner) -> None:
        """Test docs command with default format."""
        result = runner.invoke(cli, ['docs'])
        
        assert result.exit_code == 0
        # Should default to text format
        assert 'MOVER STATUS MONITOR' in result.output

    def test_docs_invalid_format(self, runner: CliRunner) -> None:
        """Test docs command with invalid format."""
        result = runner.invoke(cli, ['docs', '--format', 'invalid'])
        
        assert result.exit_code != 0
        assert 'Invalid value' in result.output

    def test_docs_output_to_file(self, runner: CliRunner) -> None:
        """Test docs command output to file."""
        with runner.isolated_filesystem():
            output_file = Path('test_docs.txt')
            
            result = runner.invoke(cli, ['docs', '--format', 'text', '--output', str(output_file)])
            
            assert result.exit_code == 0
            assert 'Documentation written' in result.output
            assert output_file.exists()
            
            content = output_file.read_text()
            assert 'MOVER STATUS MONITOR' in content

    def test_docs_output_file_error(self, runner: CliRunner) -> None:
        """Test docs command with file write error."""
        with runner.isolated_filesystem():
            # Create a directory with the same name as the intended output file
            Path('test_docs.txt').mkdir()
            
            result = runner.invoke(cli, ['docs', '--output', 'test_docs.txt'])
            
            assert result.exit_code != 0
            assert 'Failed to write documentation' in result.output

    def test_docs_short_form_options(self, runner: CliRunner) -> None:
        """Test docs command with short form options."""
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ['docs', '-f', 'markdown', '-o', 'test.md'])
            
            assert result.exit_code == 0
            assert Path('test.md').exists()

    def test_docs_comprehensive_content(self, runner: CliRunner) -> None:
        """Test that documentation includes all CLI features."""
        result = runner.invoke(cli, ['docs', '--format', 'markdown'])
        
        assert result.exit_code == 0
        
        # Check that all main CLI options are documented
        assert '--config' in result.output
        assert '--dry-run' in result.output
        assert '--log-level' in result.output
        assert '--once' in result.output
        assert '--version' in result.output
        
        # Check that all commands are documented
        assert 'completion' in result.output
        assert 'docs' in result.output
        
        # Check that examples are comprehensive
        assert 'mover-status' in result.output
        assert 'config.yaml' in result.output
        assert 'completion' in result.output


class TestCLIEnhancedHelp:
    """Test enhanced CLI help system."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    def test_main_help_includes_commands(self, runner: CliRunner) -> None:
        """Test main help includes new commands."""
        result = runner.invoke(cli, ['--help'])
        
        assert result.exit_code == 0
        assert 'completion' in result.output
        assert 'docs' in result.output

    def test_help_includes_examples(self, runner: CliRunner) -> None:
        """Test help output includes comprehensive examples."""
        result = runner.invoke(cli, ['--help'])
        
        assert result.exit_code == 0
        assert 'Examples:' in result.output
        assert 'mover-status' in result.output
        assert '--config' in result.output
        assert '--dry-run' in result.output

    def test_completion_help_detailed(self, runner: CliRunner) -> None:
        """Test completion command help is detailed."""
        result = runner.invoke(cli, ['completion', '--help'])
        
        assert result.exit_code == 0
        assert 'Generate shell completion scripts' in result.output
        assert 'Examples:' in result.output
        assert 'bash' in result.output
        assert 'zsh' in result.output
        assert 'fish' in result.output

    def test_docs_help_detailed(self, runner: CliRunner) -> None:
        """Test docs command help is detailed."""
        result = runner.invoke(cli, ['docs', '--help'])
        
        assert result.exit_code == 0
        assert 'Generate documentation' in result.output
        assert 'Examples:' in result.output
        assert 'text' in result.output
        assert 'man' in result.output
        assert 'markdown' in result.output
