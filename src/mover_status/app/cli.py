"""Command-line interface for Mover Status Monitor."""

from __future__ import annotations

import click
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

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
    default=Path('config.yaml'),
    help='Configuration file path'
)
@click.option(
    '--dry-run', '-d',
    is_flag=True,
    help='Run without sending notifications'
)
@click.option(
    '--log-level', '-l',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR'], case_sensitive=False),
    default='INFO',
    help='Logging verbosity level'
)
@click.option(
    '--once', '-o',
    is_flag=True,
    help='Run once and exit (instead of continuous monitoring)'
)
@click.version_option(version=__version__, prog_name='Mover Status Monitor')
def cli(
    config: Path,
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
    
    # Create application runner with provided options
    runner = ApplicationRunner(
        config_path=config,
        dry_run=dry_run,
        log_level=log_level.upper(),
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
