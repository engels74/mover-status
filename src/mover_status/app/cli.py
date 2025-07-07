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
@click.version_option(version=__version__, prog_name='Mover Status Monitor')
@click.pass_context
def cli(
    ctx: click.Context,
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
    # If no subcommand is provided, run the main monitoring functionality
    if ctx.invoked_subcommand is None:
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


@cli.command()
@click.option(
    '--shell', '-s',
    type=click.Choice(['bash', 'zsh', 'fish']),
    default='bash',
    help='Shell type for completion script'
)
@click.option(
    '--install', '-i',
    is_flag=True,
    help='Install completion script to appropriate location'
)
def completion(shell: str, install: bool) -> None:
    """Generate shell completion scripts.
    
    This command generates shell completion scripts for bash, zsh, and fish.
    The completion scripts provide tab completion for all CLI options and
    configuration file paths.
    
    Examples:
    
        # Generate bash completion script
        mover-status completion --shell bash
        
        # Generate and install zsh completion
        mover-status completion --shell zsh --install
        
        # Generate fish completion
        mover-status completion --shell fish
    """
    import os
    
    # Get the completion script using Click's built-in functionality
    ctx = click.get_current_context()
    prog_name = ctx.find_root().info_name or 'mover-status'
    
    if shell == 'bash':
        completion_script = f'_{prog_name.upper().replace("-", "_")}_COMPLETE=bash_source {prog_name}'
        install_path = os.path.expanduser('~/.bashrc')
        completion_line = f'eval "$({completion_script})"'
    elif shell == 'zsh':
        completion_script = f'_{prog_name.upper().replace("-", "_")}_COMPLETE=zsh_source {prog_name}'
        install_path = os.path.expanduser('~/.zshrc')
        completion_line = f'eval "$({completion_script})"'
    elif shell == 'fish':
        completion_script = f'_{prog_name.upper().replace("-", "_")}_COMPLETE=fish_source {prog_name}'
        install_path = os.path.expanduser('~/.config/fish/config.fish')
        completion_line = f'eval ({completion_script})'
    else:
        raise click.ClickException(f'Unsupported shell: {shell}')
    
    if install:
        # Install completion to appropriate shell configuration file
        try:
            # Ensure the directory exists for fish
            if shell == 'fish':
                os.makedirs(os.path.dirname(install_path), exist_ok=True)
            
            # Check if completion is already installed
            if os.path.exists(install_path):
                with open(install_path, 'r') as f:
                    content = f.read()
                    if completion_line in content:
                        click.echo(f'{shell} completion already installed in {install_path}')
                        return
            
            # Add completion to shell configuration
            with open(install_path, 'a') as f:
                _ = f.write(f'\n# {prog_name} completion\n')
                _ = f.write(f'{completion_line}\n')
            
            click.echo(f'{shell} completion installed to {install_path}')
            click.echo(f'Restart your shell or run: source {install_path}')
            
        except (OSError, IOError) as e:
            raise click.ClickException(f'Failed to install completion: {e}')
    else:
        # Provide installation instructions instead of trying to generate script
        click.echo(f'# Add this to your {shell} configuration file:')
        click.echo(completion_line)
        click.echo(f'#')
        click.echo(f'# For {shell}, add the following line to your shell configuration:')
        if shell == 'bash':
            click.echo(f'# echo "{completion_line}" >> ~/.bashrc')
        elif shell == 'zsh':
            click.echo(f'# echo "{completion_line}" >> ~/.zshrc')
        elif shell == 'fish':
            click.echo(f'# echo "{completion_line}" >> ~/.config/fish/config.fish')


@cli.command()
@click.option(
    '--format', '-f',
    type=click.Choice(['text', 'man', 'markdown']),
    default='text',
    help='Output format for documentation'
)
@click.option(
    '--output', '-o',
    type=click.Path(),
    help='Output file (defaults to stdout)'
)
def docs(format: str, output: str | None) -> None:
    """Generate documentation for the CLI.
    
    This command generates comprehensive documentation for all CLI commands
    and options in various formats.
    
    Examples:
    
        # Generate text documentation
        mover-status docs
        
        # Generate man page
        mover-status docs --format man
        
        # Generate markdown documentation
        mover-status docs --format markdown --output README-CLI.md
    """
    import io
    from contextlib import redirect_stdout
    
    # Get the root context for documentation
    ctx = click.get_current_context()
    
    output_stream = io.StringIO()
    
    with redirect_stdout(output_stream):
        if format == 'text':
            _generate_text_docs(ctx)
        elif format == 'man':
            _generate_man_docs(ctx)
        elif format == 'markdown':
            _generate_markdown_docs(ctx)
    
    content = output_stream.getvalue()
    
    if output:
        try:
            with open(output, 'w') as f:
                _ = f.write(content)
            click.echo(f'Documentation written to {output}')
        except (OSError, IOError) as e:
            raise click.ClickException(f'Failed to write documentation: {e}')
    else:
        click.echo(content)


def _generate_text_docs(ctx: click.Context) -> None:  # pyright: ignore[reportUnusedParameter] # needed for future extension
    """Generate text documentation."""
    print('MOVER STATUS MONITOR')
    print('===================')
    print()
    print('NAME')
    print('    mover-status - Track Unraid mover progress')
    print()
    print('SYNOPSIS')
    print('    mover-status [OPTIONS] [COMMAND]')
    print()
    print('DESCRIPTION')
    print('    Mover Status Monitor tracks Unraid mover operations and sends')
    print('    notifications about progress, completion, and any issues that')
    print('    occur during the data movement process.')
    print()
    print('OPTIONS')
    print('    --config, -c PATH')
    print('        Configuration file path (supports .yaml, .yml, .json, .toml)')
    print('        If not specified, searches for config files in standard locations')
    print()
    print('    --dry-run, -d')
    print('        Run without sending notifications')
    print()
    print('    --log-level, -l LEVEL')
    print('        Logging verbosity level (DEBUG, INFO, WARNING, ERROR)')
    print('        Default: INFO')
    print()
    print('    --once, -o')
    print('        Run once and exit (instead of continuous monitoring)')
    print()
    print('    --version')
    print('        Show version information')
    print()
    print('    --help')
    print('        Show help message')
    print()
    print('COMMANDS')
    print('    completion    Generate shell completion scripts')
    print('    docs          Generate documentation')
    print()
    print('EXAMPLES')
    print('    # Run with default configuration')
    print('    mover-status')
    print()
    print('    # Use custom config file')
    print('    mover-status --config /path/to/config.yaml')
    print()
    print('    # Run in dry-run mode')
    print('    mover-status --dry-run')
    print()
    print('    # Run once and exit')
    print('    mover-status --once')
    print()
    print('    # Enable debug logging')
    print('    mover-status --log-level DEBUG')
    print()
    print('    # Generate bash completion')
    print('    mover-status completion --shell bash')
    print()
    print('    # Install zsh completion')
    print('    mover-status completion --shell zsh --install')


def _generate_man_docs(ctx: click.Context) -> None:  # pyright: ignore[reportUnusedParameter] # needed for future extension
    """Generate man page documentation."""
    print('.TH MOVER-STATUS 1 "December 2024" "mover-status 0.1.0" "User Commands"')
    print('.SH NAME')
    print('mover-status \\- Track Unraid mover progress')
    print('.SH SYNOPSIS')
    print('.B mover-status')
    print('[\\fIOPTIONS\\fR] [\\fICOMMAND\\fR]')
    print('.SH DESCRIPTION')
    print('Mover Status Monitor tracks Unraid mover operations and sends')
    print('notifications about progress, completion, and any issues that')
    print('occur during the data movement process.')
    print('.SH OPTIONS')
    print('.TP')
    print('\\fB\\-c\\fR, \\fB\\-\\-config\\fR \\fIPATH\\fR')
    print('Configuration file path (supports .yaml, .yml, .json, .toml).')
    print('If not specified, searches for config files in standard locations.')
    print('.TP')
    print('\\fB\\-d\\fR, \\fB\\-\\-dry\\-run\\fR')
    print('Run without sending notifications.')
    print('.TP')
    print('\\fB\\-l\\fR, \\fB\\-\\-log\\-level\\fR \\fILEVEL\\fR')
    print('Logging verbosity level (DEBUG, INFO, WARNING, ERROR).')
    print('Default: INFO.')
    print('.TP')
    print('\\fB\\-o\\fR, \\fB\\-\\-once\\fR')
    print('Run once and exit (instead of continuous monitoring).')
    print('.TP')
    print('\\fB\\-\\-version\\fR')
    print('Show version information.')
    print('.TP')
    print('\\fB\\-\\-help\\fR')
    print('Show help message.')
    print('.SH COMMANDS')
    print('.TP')
    print('\\fBcompletion\\fR')
    print('Generate shell completion scripts.')
    print('.TP')
    print('\\fBdocs\\fR')
    print('Generate documentation.')
    print('.SH EXAMPLES')
    print('.TP')
    print('Run with default configuration:')
    print('\\fBmover-status\\fR')
    print('.TP')
    print('Use custom config file:')
    print('\\fBmover-status --config /path/to/config.yaml\\fR')
    print('.TP')
    print('Run in dry-run mode:')
    print('\\fBmover-status --dry-run\\fR')
    print('.TP')
    print('Generate bash completion:')
    print('\\fBmover-status completion --shell bash\\fR')


def _generate_markdown_docs(ctx: click.Context) -> None:  # pyright: ignore[reportUnusedParameter] # needed for future extension
    """Generate markdown documentation."""
    print('# Mover Status Monitor CLI')
    print()
    print('Track Unraid mover progress with comprehensive monitoring and notifications.')
    print()
    print('## Synopsis')
    print()
    print('```bash')
    print('mover-status [OPTIONS] [COMMAND]')
    print('```')
    print()
    print('## Description')
    print()
    print('Mover Status Monitor tracks Unraid mover operations and sends')
    print('notifications about progress, completion, and any issues that')
    print('occur during the data movement process.')
    print()
    print('## Options')
    print()
    print('### `--config, -c PATH`')
    print('Configuration file path (supports .yaml, .yml, .json, .toml).')
    print('If not specified, searches for config files in standard locations.')
    print()
    print('### `--dry-run, -d`')
    print('Run without sending notifications.')
    print()
    print('### `--log-level, -l LEVEL`')
    print('Logging verbosity level (DEBUG, INFO, WARNING, ERROR).')
    print('Default: INFO.')
    print()
    print('### `--once, -o`')
    print('Run once and exit (instead of continuous monitoring).')
    print()
    print('### `--version`')
    print('Show version information.')
    print()
    print('### `--help`')
    print('Show help message.')
    print()
    print('## Commands')
    print()
    print('### `completion`')
    print('Generate shell completion scripts.')
    print()
    print('### `docs`')
    print('Generate documentation.')
    print()
    print('## Examples')
    print()
    print('### Basic Usage')
    print()
    print('```bash')
    print('# Run with default configuration')
    print('mover-status')
    print()
    print('# Use custom config file')
    print('mover-status --config /path/to/config.yaml')
    print()
    print('# Run in dry-run mode')
    print('mover-status --dry-run')
    print()
    print('# Run once and exit')
    print('mover-status --once')
    print()
    print('# Enable debug logging')
    print('mover-status --log-level DEBUG')
    print('```')
    print()
    print('### Shell Completion')
    print()
    print('```bash')
    print('# Generate bash completion')
    print('mover-status completion --shell bash')
    print()
    print('# Install zsh completion')
    print('mover-status completion --shell zsh --install')
    print()
    print('# Generate fish completion')
    print('mover-status completion --shell fish')
    print('```')
    print()
    print('### Documentation')
    print()
    print('```bash')
    print('# Generate text documentation')
    print('mover-status docs')
    print()
    print('# Generate man page')
    print('mover-status docs --format man')
    print()
    print('# Generate markdown documentation')
    print('mover-status docs --format markdown --output README-CLI.md')
    print('```')


if __name__ == '__main__':
    cli()
