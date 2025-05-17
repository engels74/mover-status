# Mover Status Monitor - Python 3.13 Project Overview

## Project Structure

```
mover_status/
│
├── pyproject.toml           # Project metadata and dependencies
├── README.md                # Project documentation
├── .gitignore               # Git ignore file
│
├── mover_status/            # Main package
│   ├── __init__.py          # Package initialization
│   ├── __main__.py          # Entry point for running as module
│   │
│   ├── config/              # Configuration management
│   │   ├── __init__.py
│   │   ├── config_manager.py  # Manage configuration loading/saving
│   │   └── default_config.py  # Default configuration values
│   │
│   ├── core/                # Core functionality
│   │   ├── __init__.py
│   │   ├── monitor.py          # Main monitoring logic
│   │   ├── version.py          # Version checking
│   │   │
│   │   └── calculation/        # Separate calculation module
│   │       ├── __init__.py
│   │       ├── progress.py     # Calculate progress percentages
│   │       ├── time.py         # ETA and time-related calculations
│   │       └── size.py         # Data size formatting and calculations
│   │
│   ├── notification/        # Notification system
│   │   ├── __init__.py
│   │   ├── base.py             # Abstract base class for notifications
│   │   ├── manager.py          # Manages notification providers
│   │   ├── formatter.py        # Common message formatting
│   │   │
│   │   └── providers/          # Individual notification providers
│   │       ├── __init__.py
│   │       ├── telegram/
│   │       │   ├── __init__.py
│   │       │   ├── provider.py     # Telegram implementation
│   │       │   └── formatter.py    # Telegram-specific formatting
│   │       │
│   │       └── discord/
│   │           ├── __init__.py
│   │           ├── provider.py     # Discord implementation
│   │           └── formatter.py    # Discord-specific formatting
│   │
│   └── utils/               # Utility functions
│       ├── __init__.py
│       ├── logger.py         # Logging utilities
│       ├── data.py           # Data size conversion utilities
│       └── process.py        # Process monitoring utilities
│
├── tests/                   # Test suite
│   ├── __init__.py
│   ├── conftest.py           # Test fixtures and configuration
│   ├── test_config/          # Tests for configuration
│   ├── test_core/            # Tests for core functionality
│   │   └── test_calculation/
│   │       ├── test_progress.py
│   │       ├── test_time.py
│   │       └── test_size.py
│   ├── test_notification/    # Tests for notification system
│   │   ├── test_base.py
│   │   ├── test_manager.py
│   │   └── providers/
│   │       ├── test_telegram.py
│   │       └── test_discord.py
│   └── test_utils/           # Tests for utilities
│
└── scripts/                 # Installation scripts
    └── install.sh           # Unraid installation script
```

## File Descriptions

### Project Configuration

- **pyproject.toml**: Defines project metadata, dependencies, and build configuration using modern Python packaging standards.
- **README.md**: Project documentation with installation, usage, and configuration instructions.
- **.gitignore**: Specifies intentionally untracked files to ignore in Git.

### Core Package

#### Root Files

- **mover_status/\_\_init\_\_.py**: Package initialization, defines package version and public interface.
- **mover_status/\_\_main\_\_.py**: Entry point that allows running the package as a module with `python -m mover_status`.

#### Configuration

- **config/\_\_init\_\_.py**: Exports configuration functionality.
- **config/config_manager.py**: Handles loading, validation, and saving of configuration from YAML/JSON/INI.
- **config/default_config.py**: Defines default configuration values and structure.

#### Core Functionality

- **core/\_\_init\_\_.py**: Exports core monitoring functionality.
- **core/monitor.py**: Implements the main monitoring loop that watches the mover process and tracks progress.
- **core/version.py**: Handles version checking and update notifications.

- **core/calculation/\_\_init\_\_.py**: Exports calculation functions.
- **core/calculation/progress.py**: Calculates progress percentages based on current/initial data sizes.
- **core/calculation/time.py**: Calculates estimated completion times based on progress rate.
- **core/calculation/size.py**: Handles data size calculations and conversions to human-readable formats.

#### Notification System

- **notification/\_\_init\_\_.py**: Exports notification functionality.
- **notification/base.py**: Abstract base class defining the interface all notification providers must implement.
- **notification/manager.py**: Manages the lifecycle of notification providers and routes messages.
- **notification/formatter.py**: Common message formatting logic shared across providers.

- **notification/providers/\_\_init\_\_.py**: Provider registry for auto-discovery of notification backends.
- **notification/providers/telegram/provider.py**: Telegram-specific implementation of the notification interface.
- **notification/providers/telegram/formatter.py**: Telegram-specific message formatting (HTML).
- **notification/providers/discord/provider.py**: Discord-specific implementation using webhooks.
- **notification/providers/discord/formatter.py**: Discord-specific message formatting (embeds/markdown).

#### Utilities

- **utils/\_\_init\_\_.py**: Exports utility functions.
- **utils/logger.py**: Configurable logging setup with console and file outputs.
- **utils/data.py**: Data conversion utilities.
- **utils/process.py**: Utilities for monitoring system processes.

### Tests

- **tests/\_\_init\_\_.py**: Package initialization for test suite.
- **tests/conftest.py**: PyTest fixtures and test configuration.
- **tests/test_\*/**: Test modules that mirror the package structure.

### Scripts

- **scripts/install.sh**: Installation script for Unraid systems.

## Key Design Features

### Notification System

The notification system employs a provider-based architecture using dependency injection and the strategy pattern. A centralized notification manager orchestrates multiple provider instances, each implementing a common interface. This design allows:

- Adding new notification providers without modifying existing code
- Configuring multiple instances of the same provider with different settings
- Handling provider-specific formatting requirements through adapter classes
- Testing notification logic in isolation with mock providers

### Calculation Logic

The calculation subsystem applies the single responsibility principle by isolating mathematical operations and conversions. Each calculation module has a specific focus:

- Progress calculation determines completion percentage from file system metrics
- Time calculation handles rate-of-change analysis and ETA prediction
- Size formatting manages human-readable conversions of byte values

This separation facilitates unit testing and allows algorithm improvements without affecting the monitoring logic.

### Monitoring Loop

The monitoring subsystem employs an event-driven observer pattern. It:

- Maintains a stateful monitoring session
- Polls the system at configurable intervals
- Triggers notifications based on configurable thresholds
- Handles process detection, termination, and restart scenarios
- Manages throttling and rate limiting of notifications

### Configuration Management

The configuration system uses a layered approach with:

- Hardcoded defaults as fallbacks
- File-based configuration in standard formats
- Command-line argument overrides
- Dynamic configuration validation
- Type checking and schema enforcement

## Understanding Unraid's Mover

The Unraid mover is a background process that moves files from the faster cache drives to the array. Here's how it works:

### Mover Execution Flow

1. **Entry Point (`/usr/local/sbin/mover`)**: A simple bash script that calls the PHP implementation with current process context.

   ```bash
   #!/bin/bash
   PPPID=$(ps h -o ppid= "$PPID" 2>/dev/null)
   P_COMMAND=$(ps h -o %c "$PPPID" 2>/dev/null)
   /usr/local/emhttp/plugins/ca.mover.tuning/mover.php "$P_COMMAND" "$*"
   ```

2. **Implementation (`mover.php`)**: The PHP script that contains the actual mover logic:
   - Determines if it was called by cron or manually
   - Checks if conditions allow the mover to run (parity check not in progress, etc.)
   - Applies nice/ionice settings for CPU/IO priority
   - Executes the mover process with appropriate arguments

3. **Execution Control**: The script can be triggered in several ways:
   - Cron job at scheduled times
   - Manual triggering via the UI
   - With special arguments like "force" or "stop"

4. **Logging**: The script logs its activities through the system logger for troubleshooting.

### Monitoring Approach

Our Python 3.13 rewrite monitors this process by:

1. Watching for the mover process to start
2. Calculating the initial size of the cache directory
3. Periodically checking the remaining size to determine progress
4. Calculating percentage complete and ETA based on rate of change
5. Sending notifications at configured intervals
6. Detecting when the process completes and sending a final notification

By observing the cache directory size changes rather than parsing process output, this approach works regardless of how the mover is invoked or configured.
