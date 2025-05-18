# Mover Status Monitor - Development Plan

## Introduction

This document outlines a comprehensive, step-by-step development plan for refactoring the existing bash script (`moverStatus.sh`) into a new Python 3.13 application named "Mover Status Monitor". The plan strictly adheres to Test-Driven Development (TDD) and DRY (Don't Repeat Yourself) principles.

### Project Background

The Mover Status Monitor is designed to track the progress of Unraid's mover process, which transfers files from faster cache drives to the array. The original implementation is a bash script that monitors the process and sends notifications via Discord and Telegram webhooks. This refactoring aims to create a more maintainable, robust Python application with improved code organization and extensibility.

### Development Approach

The development follows these key principles:

1. **Test-Driven Development (TDD)**: For each component, we will:
   - Define test cases based on requirements
   - Write failing tests
   - Implement the functionality to make tests pass
   - Refactor the code for optimization

2. **Modular Design**: The application is structured into logical modules with clear responsibilities:
   - Configuration management
   - Core calculation logic
   - Notification system
   - Monitoring loop
   - Utility functions

3. **Provider-Based Architecture**: The notification system uses a provider pattern to support multiple notification platforms (Discord, Telegram) with a common interface.

4. **Layered Configuration**: Configuration is managed through a layered approach with defaults, file-based settings, and command-line overrides.

The plan is organized into logical phases that build upon each other, ensuring a systematic approach to development.

## Phase 1: Project Setup and Initial Structure

- [x] **Create Basic Project Structure**
  - [x] Create main package directory structure
  - [x] Create empty `__init__.py` files in all directories
  - [x] Set up `pyproject.toml` with basic metadata and dependencies
  - [x] Create `.gitignore` file
  - [x] Create basic `README.md` with project description

- [x] **Set Up Testing Framework**
  - [x] Create test directory structure mirroring the package structure
  - [x] Set up `conftest.py` with basic test fixtures
  - [x] Configure pytest in `pyproject.toml`
  - [x] Create a simple test to verify the testing setup works

## Phase 2: Configuration Management

- [x] **Module: `mover_status/config/default_config.py` and Provider-Specific Defaults**
  - [x] **Analyze `moverStatus.sh`:** Review all configurable settings in the bash script
  - [x] **Feature: Default Configuration Values**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: All required configuration keys are present
      - [x] Test case: Default values match expected types
      - [x] Test case: Configuration structure is as expected
    - [x] **TDD: Write Failing Tests:** Implement in `tests/test_config/test_default_config.py`
    - [x] **Implementation:**
      - [x] Create core default configuration dictionary in `default_config.py`
      - [x] Create provider-specific defaults in `notification/providers/*/defaults.py`
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation for modularity

- [x] **Module: `mover_status/config/config_manager.py`**
  - [x] **Analyze Requirements:** Review configuration loading/saving needs
  - [x] **Feature: Configuration Loading**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Load from YAML file
      - [x] Test case: Merge with defaults
      - [x] Test case: Handle missing file
      - [x] Test case: Handle invalid file
    - [x] **TDD: Write Failing Tests:** Implement in `tests/test_config/test_config_manager.py`
    - [x] **Implementation:** Create `ConfigManager` class with load methods
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation

  - [x] **Feature: Configuration Validation**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Validate required fields
      - [x] Test case: Validate field types
      - [x] Test case: Handle invalid values
    - [x] **TDD: Write Failing Tests:** Add to `tests/test_config/test_config_manager.py`
    - [x] **Implementation:** Add validation methods to `ConfigManager`
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation

  - [x] **Feature: Configuration Saving**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Save to YAML file
      - [x] Test case: Handle permission errors
    - [x] **TDD: Write Failing Tests:** Add to `tests/test_config/test_config_manager.py`
    - [x] **Implementation:** Add save methods to `ConfigManager`
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation

- [x] **Module: `mover_status/config/__init__.py`**
  - [x] Export necessary classes and functions
  - [x] Implement convenience functions if needed

## Phase 3: Utility Functions

- [x] **Module: `mover_status/utils/logger.py`**
  - [x] **Analyze `moverStatus.sh`:** Review logging requirements
  - [x] **Feature: Configurable Logger**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Console logging
      - [x] Test case: File logging
      - [x] Test case: Log levels
      - [x] Test case: Log formatting
    - [x] **TDD: Write Failing Tests:** Implement in `tests/test_utils/test_logger.py`
    - [x] **Implementation:** Create logger setup functions
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation

- [x] **Module: `mover_status/utils/process.py`**
  - [x] **Analyze `moverStatus.sh`:** Review process monitoring code
  - [x] **Feature: Process Detection**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Detect running process by name
      - [x] Test case: Handle non-existent process
    - [x] **TDD: Write Failing Tests:** Implement in `tests/test_utils/test_process.py`
    - [x] **Implementation:** Create process detection functions
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation

- [x] **Module: `mover_status/utils/data.py`**
  - [x] **Analyze `moverStatus.sh`:** Review data handling utilities
  - [x] **Feature: Directory Size Calculation**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Calculate directory size
      - [x] Test case: Handle exclusions
      - [x] Test case: Handle non-existent directory
    - [x] **TDD: Write Failing Tests:** Implement in `tests/test_utils/test_data.py`
    - [x] **Implementation:** Create directory size calculation functions
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation

- [x] **Module: `mover_status/utils/__init__.py`**
  - [x] Export necessary functions

## Phase 4: Core Calculation Logic

- [x] **Module: `mover_status/core/calculation/size.py`**
  - [x] **Analyze `moverStatus.sh`:** Review the `human_readable` function
  - [x] **Feature: Convert Bytes to Human-Readable Format**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Bytes (e.g., 500 bytes -> "500 Bytes")
      - [x] Test case: Kilobytes (e.g., 2048 bytes -> "2.0 KB")
      - [x] Test case: Megabytes (e.g., 3145728 bytes -> "3.0 MB")
      - [x] Test case: Gigabytes (e.g., 4294967296 bytes -> "4.0 GB")
      - [x] Test case: Terabytes (e.g., 5497558138880 bytes -> "5.0 TB")
      - [x] Test case: Zero bytes -> "0 Bytes"
      - [x] Test case: Large TB value with GB remainder
    - [x] **TDD: Write Failing Tests:** Implement in `tests/test_core/test_calculation/test_size.py`
    - [x] **Implementation:** Create `format_bytes` function
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation

- [ ] **Module: `mover_status/core/calculation/time.py`**
  - [ ] **Analyze `moverStatus.sh`:** Review the `calculate_etc` function
  - [ ] **Feature: Calculate Estimated Time of Completion**
    - [ ] **TDD: Define Test Cases:**
      - [ ] Test case: 0% progress (should return "Calculating...")
      - [ ] Test case: Mid-progress with consistent rate
      - [ ] Test case: Different platform outputs (Discord vs Telegram format)
    - [ ] **TDD: Write Failing Tests:** Implement in `tests/test_core/test_calculation/test_time.py`
    - [ ] **Implementation:** Create `calculate_eta` function
    - [ ] **TDD: Verify Tests Pass**
    - [ ] **Refactor:** Review and optimize the implementation

- [ ] **Module: `mover_status/core/calculation/progress.py`**
  - [ ] **Analyze `moverStatus.sh`:** Review progress calculation logic
  - [ ] **Feature: Calculate Progress Percentage**
    - [ ] **TDD: Define Test Cases:**
      - [ ] Test case: Calculate percentage from initial and current size
      - [ ] Test case: Handle edge cases (0%, 100%)
    - [ ] **TDD: Write Failing Tests:** Implement in `tests/test_core/test_calculation/test_progress.py`
    - [ ] **Implementation:** Create `calculate_progress` function
    - [ ] **TDD: Verify Tests Pass**
    - [ ] **Refactor:** Review and optimize the implementation

- [x] **Module: `mover_status/core/calculation/__init__.py`**
  - [x] Export calculation functions

## Phase 5: Version Checking

- [ ] **Module: `mover_status/core/version.py`**
  - [ ] **Analyze `moverStatus.sh`:** Review version checking logic
  - [ ] **Feature: Check Latest Version**
    - [ ] **TDD: Define Test Cases:**
      - [ ] Test case: Get latest version from GitHub
      - [ ] Test case: Compare with current version
      - [ ] Test case: Handle network errors
    - [ ] **TDD: Write Failing Tests:** Implement in `tests/test_core/test_version.py`
    - [ ] **Implementation:** Create version checking functions
    - [ ] **TDD: Verify Tests Pass**
    - [ ] **Refactor:** Review and optimize the implementation

## Phase 6: Notification System

- [ ] **Module: `mover_status/notification/base.py`**
  - [ ] **Analyze Requirements:** Define notification provider interface
  - [ ] **Feature: Abstract Notification Provider**
    - [ ] **TDD: Define Test Cases:**
      - [ ] Test case: Abstract base class cannot be instantiated
      - [ ] Test case: Required methods are defined
    - [ ] **TDD: Write Failing Tests:** Implement in `tests/test_notification/test_base.py`
    - [ ] **Implementation:** Create `NotificationProvider` abstract base class
    - [ ] **TDD: Verify Tests Pass**
    - [ ] **Refactor:** Review and optimize the implementation

- [ ] **Module: `mover_status/notification/formatter.py`**
  - [ ] **Analyze `moverStatus.sh`:** Review message formatting logic
  - [ ] **Feature: Common Message Formatting**
    - [ ] **TDD: Define Test Cases:**
      - [ ] Test case: Format message with placeholders
      - [ ] Test case: Handle missing placeholders
    - [ ] **TDD: Write Failing Tests:** Implement in `tests/test_notification/test_formatter.py`
    - [ ] **Implementation:** Create message formatting functions
    - [ ] **TDD: Verify Tests Pass**
    - [ ] **Refactor:** Review and optimize the implementation

- [ ] **Module: `mover_status/notification/providers/telegram/formatter.py`**
  - [ ] **Analyze `moverStatus.sh`:** Review Telegram-specific formatting
  - [ ] **Feature: Telegram Message Formatting**
    - [ ] **TDD: Define Test Cases:**
      - [ ] Test case: Format message with HTML tags
      - [ ] Test case: Format ETA for Telegram
    - [ ] **TDD: Write Failing Tests:** Implement in `tests/test_notification/providers/test_telegram.py`
    - [ ] **Implementation:** Create Telegram-specific formatting functions
    - [ ] **TDD: Verify Tests Pass**
    - [ ] **Refactor:** Review and optimize the implementation

- [ ] **Module: `mover_status/notification/providers/telegram/provider.py`**
  - [ ] **Analyze `moverStatus.sh`:** Review Telegram notification logic
  - [ ] **Feature: Telegram Notification Provider**
    - [ ] **TDD: Define Test Cases:**
      - [ ] Test case: Send notification to Telegram
      - [ ] Test case: Handle API errors
      - [ ] Test case: Validate configuration
    - [ ] **TDD: Write Failing Tests:** Add to `tests/test_notification/providers/test_telegram.py`
    - [ ] **Implementation:** Create `TelegramProvider` class
    - [ ] **TDD: Verify Tests Pass**
    - [ ] **Refactor:** Review and optimize the implementation

- [ ] **Module: `mover_status/notification/providers/discord/formatter.py`**
  - [ ] **Analyze `moverStatus.sh`:** Review Discord-specific formatting
  - [ ] **Feature: Discord Message Formatting**
    - [ ] **TDD: Define Test Cases:**
      - [ ] Test case: Format message with markdown
      - [ ] Test case: Format ETA for Discord
      - [ ] Test case: Create embed structure
    - [ ] **TDD: Write Failing Tests:** Implement in `tests/test_notification/providers/test_discord.py`
    - [ ] **Implementation:** Create Discord-specific formatting functions
    - [ ] **TDD: Verify Tests Pass**
    - [ ] **Refactor:** Review and optimize the implementation

- [ ] **Module: `mover_status/notification/providers/discord/provider.py`**
  - [ ] **Analyze `moverStatus.sh`:** Review Discord notification logic
  - [ ] **Feature: Discord Notification Provider**
    - [ ] **TDD: Define Test Cases:**
      - [ ] Test case: Send notification to Discord webhook
      - [ ] Test case: Handle API errors
      - [ ] Test case: Validate webhook URL
    - [ ] **TDD: Write Failing Tests:** Add to `tests/test_notification/providers/test_discord.py`
    - [ ] **Implementation:** Create `DiscordProvider` class
    - [ ] **TDD: Verify Tests Pass**
    - [ ] **Refactor:** Review and optimize the implementation

- [ ] **Module: `mover_status/notification/manager.py`**
  - [ ] **Analyze Requirements:** Define notification management needs
  - [ ] **Feature: Notification Provider Management**
    - [ ] **TDD: Define Test Cases:**
      - [ ] Test case: Register providers
      - [ ] Test case: Send notifications to all providers
      - [ ] Test case: Handle provider errors
    - [ ] **TDD: Write Failing Tests:** Implement in `tests/test_notification/test_manager.py`
    - [ ] **Implementation:** Create `NotificationManager` class
    - [ ] **TDD: Verify Tests Pass**
    - [ ] **Refactor:** Review and optimize the implementation

- [ ] **Module: `mover_status/notification/__init__.py`**
  - [ ] Export notification classes and functions

## Phase 7: Core Monitoring Logic

- [ ] **Module: `mover_status/core/monitor.py`**
  - [ ] **Analyze `moverStatus.sh`:** Review the main monitoring loop
  - [ ] **Feature: Monitor Session Class**
    - [ ] **TDD: Define Test Cases:**
      - [ ] Test case: Initialize monitoring session
      - [ ] Test case: Track monitoring state
    - [ ] **TDD: Write Failing Tests:** Implement in `tests/test_core/test_monitor.py`
    - [ ] **Implementation:** Create `MonitorSession` class
    - [ ] **TDD: Verify Tests Pass**
    - [ ] **Refactor:** Review and optimize the implementation

  - [ ] **Feature: Process Detection and Monitoring**
    - [ ] **TDD: Define Test Cases:**
      - [ ] Test case: Detect mover process start
      - [ ] Test case: Detect mover process end
      - [ ] Test case: Calculate initial size
    - [ ] **TDD: Write Failing Tests:** Add to `tests/test_core/test_monitor.py`
    - [ ] **Implementation:** Add process monitoring methods
    - [ ] **TDD: Verify Tests Pass**
    - [ ] **Refactor:** Review and optimize the implementation

  - [ ] **Feature: Progress Tracking**
    - [ ] **TDD: Define Test Cases:**
      - [ ] Test case: Track progress over time
      - [ ] Test case: Calculate percentage complete
      - [ ] Test case: Determine notification thresholds
    - [ ] **TDD: Write Failing Tests:** Add to `tests/test_core/test_monitor.py`
    - [ ] **Implementation:** Add progress tracking methods
    - [ ] **TDD: Verify Tests Pass**
    - [ ] **Refactor:** Review and optimize the implementation

  - [ ] **Feature: Main Monitoring Loop**
    - [ ] **TDD: Define Test Cases:**
      - [ ] Test case: Run monitoring loop
      - [ ] Test case: Handle process completion
      - [ ] Test case: Restart monitoring
    - [ ] **TDD: Write Failing Tests:** Add to `tests/test_core/test_monitor.py`
    - [ ] **Implementation:** Create main monitoring loop
    - [ ] **TDD: Verify Tests Pass**
    - [ ] **Refactor:** Review and optimize the implementation

- [ ] **Module: `mover_status/core/__init__.py`**
  - [ ] Export core classes and functions

## Phase 8: Dry Run Mode

- [ ] **Module: `mover_status/core/dry_run.py`**
  - [ ] **Analyze `moverStatus.sh`:** Review dry run implementation
  - [ ] **Feature: Dry Run Simulation**
    - [ ] **TDD: Define Test Cases:**
      - [ ] Test case: Simulate monitoring session
      - [ ] Test case: Generate test notifications
    - [ ] **TDD: Write Failing Tests:** Implement in `tests/test_core/test_dry_run.py`
    - [ ] **Implementation:** Create dry run simulation functions
    - [ ] **TDD: Verify Tests Pass**
    - [ ] **Refactor:** Review and optimize the implementation

## Phase 9: Main Application Entry Point

- [ ] **Module: `mover_status/__main__.py`**
  - [ ] **Analyze Requirements:** Define CLI interface
  - [ ] **Feature: Command Line Interface**
    - [ ] **TDD: Define Test Cases:**
      - [ ] Test case: Parse command line arguments
      - [ ] Test case: Handle help command
      - [ ] Test case: Handle version command
      - [ ] Test case: Handle configuration file path
    - [ ] **TDD: Write Failing Tests:** Implement in `tests/test_main.py`
    - [ ] **Implementation:** Create CLI argument parser
    - [ ] **TDD: Verify Tests Pass**
    - [ ] **Refactor:** Review and optimize the implementation

  - [ ] **Feature: Application Initialization**
    - [ ] **TDD: Define Test Cases:**
      - [ ] Test case: Initialize configuration
      - [ ] Test case: Set up logging
      - [ ] Test case: Initialize notification providers
    - [ ] **TDD: Write Failing Tests:** Add to `tests/test_main.py`
    - [ ] **Implementation:** Create application initialization code
    - [ ] **TDD: Verify Tests Pass**
    - [ ] **Refactor:** Review and optimize the implementation

  - [ ] **Feature: Main Application Loop**
    - [ ] **TDD: Define Test Cases:**
      - [ ] Test case: Start monitoring
      - [ ] Test case: Handle dry run mode
      - [ ] Test case: Handle keyboard interrupts
    - [ ] **TDD: Write Failing Tests:** Add to `tests/test_main.py`
    - [ ] **Implementation:** Create main application loop
    - [ ] **TDD: Verify Tests Pass**
    - [ ] **Refactor:** Review and optimize the implementation

- [ ] **Module: `mover_status/__init__.py`**
  - [ ] Define package version
  - [ ] Export public interface

## Phase 10: Packaging and Installation

- [ ] **Complete `pyproject.toml`**
  - [ ] Add all dependencies
  - [ ] Configure build system
  - [ ] Set up entry points

- [ ] **Create Installation Script**
  - [ ] **Analyze Requirements:** Review installation needs for Unraid
  - [ ] **Implementation:** Create `scripts/install.sh`
  - [ ] Test installation script

## Phase 11: Documentation and Final Review

- [ ] **Complete README.md**
  - [ ] Add detailed installation instructions
  - [ ] Add usage examples
  - [ ] Add configuration guide
  - [ ] Add troubleshooting section

- [ ] **Create Additional Documentation**
  - [ ] Create user guide
  - [ ] Create developer guide
  - [ ] Document API

- [ ] **Final Code Review**
  - [ ] Review all code for consistency
  - [ ] Ensure all tests pass
  - [ ] Check code coverage
  - [ ] Optimize performance where needed

- [ ] **Final Testing**
  - [ ] Test on Unraid system
  - [ ] Test with real mover process
  - [ ] Test with different configuration options

## Conclusion

This development plan provides a comprehensive, step-by-step approach to refactoring the existing bash script into a modern Python application. By following Test-Driven Development principles, we ensure that each component is thoroughly tested and meets the requirements before moving on to the next phase.

The plan is organized into logical phases that build upon each other, starting with the basic project structure and ending with a complete, well-documented application. Each phase focuses on a specific aspect of the application, such as configuration management, utility functions, core calculation logic, notification system, and monitoring logic.

By adhering to this plan, we will create a robust, maintainable, and well-tested application that provides the same functionality as the original bash script but with improved code organization, better error handling, and more flexibility for future enhancements.
