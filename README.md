# Mover Status Monitor

A Python 3.13 application to monitor Unraid's mover process and send notifications via Discord and Telegram.

## Overview

Mover Status Monitor tracks the progress of Unraid's mover process, which transfers files from faster cache drives to the array. It provides real-time progress updates and notifications through Discord and Telegram.

## Features

- Real-time monitoring of the mover process
- Progress tracking with percentage completion
- Estimated time of completion calculation
- Configurable notification thresholds
- Support for Discord and Telegram notifications
- Human-readable data size formatting
- Dry run mode for testing notifications
- Configurable exclusion paths

## Installation

### Prerequisites

- Python 3.13 or higher
- Unraid server with mover process

### Basic Installation

```bash
# Clone the repository
git clone https://github.com/engels74/mover-status.git
cd mover-status

# Install the package
uv pip install -e .
```

### Unraid Installation

For Unraid systems, use the installation script:

```bash
bash scripts/install.sh
```

## Configuration

Create a configuration file in YAML format:
- `config.yaml`

Example configuration (YAML):

```yaml
notification:
  telegram:
    enabled: true
    bot_token: "your_bot_token"
    chat_id: "your_chat_id"
  discord:
    enabled: true
    webhook_url: "https://discord.com/api/webhooks/your_webhook"
    name_override: "Mover Bot"
  increment: 25  # Notification frequency in percentage increments

monitoring:
  mover_executable: "/usr/local/sbin/mover"
  exclusions:
    - "/mnt/cache/excluded_folder1"
    - "/mnt/cache/excluded_folder2"

debug:
  enabled: false
```

## Usage

```bash
# Run with default configuration
mover-status

# Specify a configuration file
mover-status --config /path/to/config.yaml

# Run in dry run mode (test notifications)
mover-status --dry-run

# Show help
mover-status --help
```

## Development

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/engels74/mover-status.git
cd mover-status

# Install development dependencies
uv pip install -e ".[dev]"
```

### Running Tests

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=mover_status

# Type checking
uvx basedpyright
```

## License

This project is licensed under the GNU Affero General Public License v3 or later (AGPLv3+) - see the LICENSE file for details.

## Acknowledgements

This project is a Python rewrite of the original bash script `moverStatus.sh`.
