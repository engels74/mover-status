"""Command-line interface for Mover Status Monitor."""

from __future__ import annotations

import click
from pathlib import Path
from typing import TYPE_CHECKING

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


# Import version from package
try:
    from importlib.metadata import version
    __version__ = version("mover-status")
except ImportError:
    __version__ = "unknown"


@click.command()
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
@click.version_option(version=__version__, prog_name='Mover Status Monitor')
def cli(
    config: Path | None,
    dry_run: bool,
    log_level: str,
    once: bool,
) -> None:
    """Mover Status Monitor - Track Unraid mover progress.
    
    This tool monitors Unraid mover operations and sends notifications
    about progress, completion, and any issues that occur during the
    data movement process.
    
    Examples:
    
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
    from mover_status.app.runner import ApplicationRunner

    # Discover configuration file if not explicitly provided
    config_path = config if config is not None else discover_config_file()

    # Create application runner with provided options
    # log_level is already normalized by the validation callback
    runner = ApplicationRunner(
        config_path=config_path,
        dry_run=dry_run,
        log_level=log_level,
        run_once=once
    )
    
    try:
        # Run the application
        runner.run()
    except KeyboardInterrupt:
        click.echo("\nShutting down gracefully...")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e))


if __name__ == '__main__':
    cli()
