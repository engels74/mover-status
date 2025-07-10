"""Command-line interface for Mover Status Monitor."""

from __future__ import annotations

import click
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError

if TYPE_CHECKING:
    pass


# Configuration file discovery paths in order of precedence
# 1. Current directory
CURRENT_DIR_CONFIG_FILES = [
    'config.yaml',
    'config.yml',
    'config.json',
    'config.toml',
]

# 2. User home directory
HOME_CONFIG_FILES = [
    '.mover-status.yaml',
    '.mover-status.yml',
    '.mover-status.json',
    '.mover-status.toml',
]

# 3. System configuration directories
SYSTEM_CONFIG_PATHS = [
    Path('/etc/mover-status/config.yaml'),
    Path('/etc/mover-status.yaml'),
    Path('/usr/local/etc/mover-status/config.yaml'),
    Path('/usr/local/etc/mover-status.yaml'),
]


def discover_config_file() -> Path:
    """Discover configuration file in standard locations.

    Searches for configuration files in the following order of precedence:
    1. Current directory (config.yaml, config.yml, config.json, config.toml)
    2. User home directory (~/.mover-status.yaml, etc.)
    3. System directories (/etc/mover-status/, etc.)

    Returns:
        Path to the first configuration file found, or default 'config.yaml'
        if no configuration file is discovered.
    """
    # 1. Check current directory
    for config_file in CURRENT_DIR_CONFIG_FILES:
        config_path = Path(config_file)
        if config_path.exists() and config_path.is_file():
            return config_path

    # 2. Check user home directory
    try:
        home_dir = Path.home()
        for config_file in HOME_CONFIG_FILES:
            config_path = home_dir / config_file
            if config_path.exists() and config_path.is_file():
                return config_path
    except (OSError, RuntimeError):
        # Path.home() can fail in some environments
        pass

    # 3. Check system directories
    for config_path in SYSTEM_CONFIG_PATHS:
        if config_path.exists() and config_path.is_file():
            return config_path

    # Default fallback
    return Path('config.yaml')


def validate_config_path(
    ctx: click.Context,  # pyright: ignore[reportUnusedParameter] # required by Click callback signature
    param: click.Parameter,  # pyright: ignore[reportUnusedParameter] # required by Click callback signature
    value: Path | None,
) -> Path | None:
    """Validate configuration file path.

    Args:
        ctx: Click context (required by Click callback signature)
        param: Click parameter (required by Click callback signature)
        value: Path value to validate

    Returns:
        Validated Path object

    Raises:
        click.BadParameter: If validation fails
    """
    if value is None:
        return value

    # Check if it's a directory
    if value.exists() and value.is_dir():
        raise click.BadParameter('Configuration path must be a file, not a directory')

    # Check file extension
    valid_extensions = {'.yaml', '.yml', '.json', '.toml'}
    if value.suffix.lower() not in valid_extensions:
        extensions_str = ", ".join(sorted(valid_extensions))
        raise click.BadParameter(
            f'Invalid configuration file extension. Supported extensions: {extensions_str}'
        )

    return value


def validate_log_level(
    ctx: click.Context,  # pyright: ignore[reportUnusedParameter] # required by Click callback signature
    param: click.Parameter,  # pyright: ignore[reportUnusedParameter] # required by Click callback signature
    value: str | None,
) -> str | None:
    """Validate and normalize log level.

    Args:
        ctx: Click context (required by Click callback signature)
        param: Click parameter (required by Click callback signature)
        value: Log level value to validate

    Returns:
        Normalized log level (uppercase)

    Raises:
        click.BadParameter: If validation fails
    """
    if value is None:
        return value

    # Normalize to uppercase for consistency
    normalized_value = value.upper().strip()

    # Validate against allowed values
    valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR'}
    if normalized_value not in valid_levels:
        raise click.BadParameter(
            f'Invalid log level "{value}". Valid options: {", ".join(sorted(valid_levels))}'
        )

    return normalized_value


def sanitize_string_input(value: str | None) -> str | None:
    """Sanitize string input by stripping whitespace and handling empty strings.

    Args:
        value: String value to sanitize

    Returns:
        Sanitized string or None if empty
    """
    if value is None:
        return None

    sanitized = value.strip()
    return sanitized if sanitized else None


def format_validation_error(error: ValidationError) -> str:
    """Format a Pydantic ValidationError into a user-friendly message.
    
    Args:
        error: The Pydantic ValidationError to format
        
    Returns:
        A formatted error message with helpful guidance
    """
    error_message = click.style("Configuration Error:", fg="red", bold=True)
    
    # Check if this is specifically about placeholder values
    for error_detail in error.errors():
        if error_detail.get("type") == "value_error":
            # Get the actual error message from the ValidationError
            msg = error_detail.get("msg", "")
            
            # Check if this looks like our placeholder validation error
            if "placeholder values" in msg:
                # Split the message and format it nicely
                parts = msg.split(". Please update: ")
                error_message += f"\n\n{parts[0]}.\n"
                
                if len(parts) > 1:
                    error_message += f"\n{click.style('Required changes:', fg='yellow', bold=True)}\n"
                    changes = parts[1].split("; ")
                    for change in changes:
                        if change.strip():
                            error_message += f"  • {change.strip()}\n"
                
                error_message += f"\n{click.style('Next steps:', fg='green', bold=True)}\n"
                error_message += "  1. Edit your configuration file (config.yaml)\n"
                error_message += "  2. Replace placeholder values with your actual credentials\n"
                error_message += "  3. For help getting credentials, see the comments in the config file\n"
                error_message += f"\n{click.style('Configuration file path:', fg='cyan')} config.yaml\n"
                return error_message
            
            # Handle other specific provider configuration errors
            elif "Provider(s)" in msg and ("are not configured" in msg or "missing" in msg):
                error_message += f"\n\n{msg}\n"
                error_message += f"\n{click.style('Tip:', fg='blue', bold=True)} Make sure your enabled providers are properly configured in the providers section.\n"
                return error_message
    
    # Generic validation error formatting - show each error
    error_message += "\n\nThe following configuration issues were found:\n"
    
    for i, error_detail in enumerate(error.errors(), 1):
        location = " -> ".join(str(loc) for loc in error_detail.get("loc", []))
        error_type = error_detail.get("type", "unknown")
        message = error_detail.get("msg", "Unknown error")
        
        if location:
            error_message += f"\n{i}. {click.style(location, fg='yellow')}: {message}"
        else:
            error_message += f"\n{i}. {message}"
            
        if error_type != "unknown" and error_type != "value_error":
            error_message += f" ({error_type})"
    
    error_message += f"\n\n{click.style('Tip:', fg='blue', bold=True)} Check your configuration file for syntax errors or missing required values.\n"
    
    return error_message


def _validate_configuration_file(config_path: Path) -> None:
    """Validate a configuration file and report results.
    
    Args:
        config_path: Path to the configuration file to validate
        
    Raises:
        click.ClickException: If validation fails
    """
    click.echo(f"Validating configuration file: {click.style(str(config_path), fg='cyan')}")
    
    try:
        # Import necessary modules and use runner's logic
        from mover_status.app.runner import ApplicationRunner
        
        # Create a temporary runner just to validate the configuration
        # This will trigger all the improved error handling logic
        runner = ApplicationRunner(
            config_path=config_path,
            dry_run=True,  # Safe default
            log_level="INFO",
            run_once=True
        )
        
        # If we get here, validation passed
        click.echo(f"{click.style('✓', fg='green', bold=True)} Configuration is valid!")
        
        # Show summary of configuration
        click.echo(f"\n{click.style('Configuration Summary:', fg='blue', bold=True)}")
        click.echo(f"  • Monitoring interval: {runner.config.monitoring.interval}s")
        click.echo(f"  • Enabled providers: {', '.join(runner.config.notifications.enabled_providers)}")
        click.echo(f"  • Notification events: {', '.join(runner.config.notifications.events)}")
        click.echo(f"  • Log level: {runner.config.logging.level}")
        
        if runner.config.monitoring.dry_run:
            click.echo(f"  • {click.style('Dry run mode enabled', fg='yellow')}")
    
    except ValidationError as e:
        formatted_error = format_validation_error(e)
        click.echo(formatted_error, err=True)
        raise click.ClickException("Configuration validation failed")
    
    except FileNotFoundError as e:
        click.echo(f"{click.style('Configuration File Error:', fg='red', bold=True)}\n", err=True)
        click.echo(str(e), err=True)
        raise click.ClickException("Configuration file not found")
    
    except Exception as e:
        # Check if this is a wrapped ValidationError
        if hasattr(e, '__cause__') and isinstance(e.__cause__, ValidationError):
            formatted_error = format_validation_error(e.__cause__)
            click.echo(formatted_error, err=True)
            raise click.ClickException("Configuration validation failed")
        
        click.echo(f"{click.style('ERROR:', fg='red', bold=True)} Failed to load configuration: {e}", err=True)
        raise click.ClickException(f"Configuration loading failed: {e}")


# Import version from package
try:
    from importlib.metadata import version
    __version__ = version("mover-status")
except ImportError:
    __version__ = "unknown"


@click.group(invoke_without_command=True)
@click.option(
    '--config', '-c',
    type=click.Path(path_type=Path),
    default=None,
    callback=validate_config_path,
    help='Configuration file path (supports .yaml, .yml, .json, .toml). If not specified, searches for config files in standard locations.'
)
@click.option(
    '--dry-run', '-d',
    is_flag=True,
    help='Run without sending notifications'
)
@click.option(
    '--log-level', '-l',
    type=str,
    default='INFO',
    callback=validate_log_level,
    help='Logging verbosity level (DEBUG, INFO, WARNING, ERROR)'
)
@click.option(
    '--once', '-o',
    is_flag=True,
    help='Run once and exit (instead of continuous monitoring)'
)
@click.option(
    '--validate-config',
    is_flag=True,
    help='Validate configuration file and exit (do not start monitoring)'
)
@click.version_option(version=__version__, prog_name='Mover Status Monitor')
@click.pass_context
def cli(
    ctx: click.Context,
    config: Path | None,
    dry_run: bool,
    log_level: str,
    once: bool,
    validate_config: bool,
) -> None:
    """Mover Status Monitor - Track Unraid mover progress.
    
    This tool monitors Unraid mover operations and sends notifications
    about progress, completion, and any issues that occur during the
    data movement process.
    
    Examples:
    
        # Validate configuration file
        mover-status --validate-config
        
        # Run with default configuration
        mover-status
        
        # Use custom config file
        mover-status --config /path/to/config.yaml
        
        # Run in dry-run mode (no notifications sent)
        mover-status --dry-run
        
        # Run once and exit
        mover-status --once
        
        # Enable debug logging
        mover-status --log-level DEBUG
    """
    # If no subcommand is provided, run the main monitoring functionality
    if ctx.invoked_subcommand is None:
        from mover_status.app.runner import ApplicationRunner

        # Discover configuration file if not explicitly provided
        config_path = config if config is not None else discover_config_file()

        if validate_config:
            # Validate configuration and exit
            _validate_configuration_file(config_path)
            return

        try:
            # Create application runner with provided options
            # log_level is already normalized by the validation callback
            runner = ApplicationRunner(
                config_path=config_path,
                dry_run=dry_run,
                log_level=log_level,
                run_once=once
            )
            
            # Run the application
            runner.run()
        except KeyboardInterrupt:
            click.echo("\nShutting down gracefully...")
        except ValidationError as e:
            # Handle Pydantic validation errors with helpful formatting
            formatted_error = format_validation_error(e)
            click.echo(formatted_error, err=True)
            raise click.ClickException("Configuration validation failed")
        except FileNotFoundError as e:
            # Handle missing configuration files with helpful message
            click.echo(f"{click.style('Configuration File Error:', fg='red', bold=True)}\n", err=True)
            click.echo(str(e), err=True)
            raise click.ClickException("Configuration file not found")
        except Exception as e:
            # Check if this is a wrapped ValidationError
            if hasattr(e, '__cause__') and isinstance(e.__cause__, ValidationError):
                formatted_error = format_validation_error(e.__cause__)
                click.echo(formatted_error, err=True)
                raise click.ClickException("Configuration validation failed")
            
            # Handle other exceptions
            click.echo(f"Error: {e}", err=True)
            raise click.ClickException(str(e))


# Shell completion functionality removed - not needed for containerized Docker environment


# Documentation generation functionality removed - not needed for containerized Docker environment


if __name__ == '__main__':
    cli()
