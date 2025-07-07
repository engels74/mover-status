"""Entry point for the mover status monitor application."""

from __future__ import annotations

from mover_status.app.cli import cli


def main() -> None:
    """Initialize and run the mover status monitor application."""
    cli()


if __name__ == "__main__":
    main()