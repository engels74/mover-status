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

- [x] **Module: `mover_status/core/calculation/time.py`**
  - [x] **Analyze `moverStatus.sh`:** Review the `calculate_etc` function
  - [x] **Feature: Calculate Estimated Time of Completion**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: 0% progress (should return "Calculating...")
      - [x] Test case: Mid-progress with consistent rate
      - [x] Test case: Different platform outputs (Discord vs Telegram format)
    - [x] **TDD: Write Failing Tests:** Implement in `tests/test_core/test_calculation/test_time.py`
    - [x] **Implementation:** Create `calculate_eta` function
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation

- [x] **Module: `mover_status/core/calculation/progress.py`**
  - [x] **Analyze `moverStatus.sh`:** Review progress calculation logic
  - [x] **Feature: Calculate Progress Percentage**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Calculate percentage from initial and current size
      - [x] Test case: Handle edge cases (0%, 100%)
    - [x] **TDD: Write Failing Tests:** Implement in `tests/test_core/test_calculation/test_progress.py`
    - [x] **Implementation:** Create `calculate_progress` function
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation

- [x] **Module: `mover_status/core/calculation/__init__.py`**
  - [x] Export calculation functions

## Phase 5: Version Checking

- [x] **Module: `mover_status/core/version.py`**
  - [x] **Analyze `moverStatus.sh`:** Review version checking logic
  - [x] **Feature: Check Latest Version**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Get latest version from GitHub
      - [x] Test case: Compare with current version
      - [x] Test case: Handle network errors
    - [x] **TDD: Write Failing Tests:** Implement in `tests/test_core/test_version.py`
    - [x] **Implementation:** Create version checking functions
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation

## Phase 6: Notification System

- [x] **Module: `mover_status/notification/base.py`**
  - [x] **Analyze Requirements:** Define notification provider interface
  - [x] **Feature: Abstract Notification Provider**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Abstract base class cannot be instantiated
      - [x] Test case: Required methods are defined
    - [x] **TDD: Write Failing Tests:** Implement in `tests/test_notification/test_base.py`
    - [x] **Implementation:** Create `NotificationProvider` abstract base class
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation

- [x] **Module: `mover_status/notification/formatter.py`**
  - [x] **Analyze `moverStatus.sh`:** Review message formatting logic
  - [x] **Feature: Common Message Formatting**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Format message with placeholders
      - [x] Test case: Handle missing placeholders
      - [x] Test case: Integrate with platform-agnostic calculation values
    - [x] **TDD: Write Failing Tests:** Implement in `tests/test_notification/test_formatter.py`
    - [x] **Implementation:** Create message formatting functions
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation
  - [x] **Feature: Raw Value Formatting**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Format ETA timestamp (convert None to "Calculating...")
      - [x] Test case: Format byte values for display
      - [x] Test case: Format progress percentage for display
    - [x] **TDD: Write Failing Tests:** Add to `tests/test_notification/test_formatter.py`
    - [x] **Implementation:** Create common formatter functions for raw calculation values
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation
  - [x] **Feature: Modular Formatting Architecture**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Common formatter handles basic conversions before provider-specific formatting
      - [x] Test case: Provider formatters use common formatter functions for shared logic
    - [x] **TDD: Write Failing Tests:** Add to `tests/test_notification/test_formatter.py`
    - [x] **Implementation:** Create modular formatting architecture
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation

- [x] **Module: `mover_status/notification/providers/telegram/formatter.py`**
  - [x] **Analyze `moverStatus.sh`:** Review Telegram-specific formatting
  - [x] **Feature: Telegram Message Formatting**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Format message with HTML tags
      - [x] Test case: Format ETA for Telegram
      - [x] Test case: Use common formatter for basic ETA conversion then apply Telegram-specific formatting
      - [x] Test case: Format valid timestamp into human-readable format for Telegram
    - [x] **TDD: Write Failing Tests:** Implement in `tests/test_notification/providers/test_telegram.py`
    - [x] **Implementation:** Create Telegram-specific formatting functions that leverage common formatters
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation

- [x] **Module: `mover_status/notification/providers/telegram/provider.py`**
  - [x] **Analyze `moverStatus.sh`:** Review Telegram notification logic
  - [x] **Feature: Telegram Notification Provider**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Send notification to Telegram
      - [x] Test case: Handle API errors
      - [x] Test case: Validate configuration
    - [x] **TDD: Write Failing Tests:** Add to `tests/test_notification/providers/test_telegram.py`
    - [x] **Implementation:** Create `TelegramProvider` class
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation

- [x] **Module: `mover_status/notification/providers/discord/formatter.py`**
  - [x] **Analyze `moverStatus.sh`:** Review Discord-specific formatting
  - [x] **Feature: Discord Message Formatting**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Format message with markdown
      - [x] Test case: Format ETA for Discord
      - [x] Test case: Use common formatter for basic ETA conversion then apply Discord-specific formatting
      - [x] Test case: Format valid timestamp into Discord's <t:timestamp:R> format
      - [x] Test case: Create embed structure
    - [x] **TDD: Write Failing Tests:** Implement in `tests/test_notification/providers/test_discord.py`
    - [x] **Implementation:** Create Discord-specific formatting functions that leverage common formatters
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation

- [x] **Module: `mover_status/notification/providers/discord/provider.py`**
  - [x] **Analyze `moverStatus.sh`:** Review Discord notification logic
  - [x] **Feature: Discord Notification Provider**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Send notification to Discord webhook
      - [x] Test case: Handle API errors
      - [x] Test case: Validate webhook URL
    - [x] **TDD: Write Failing Tests:** Add to `tests/test_notification/providers/test_discord.py`
    - [x] **Implementation:** Create `DiscordProvider` class
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation

- [x] **Module: `mover_status/notification/manager.py`**
  - [x] **Analyze Requirements:** Define notification management needs
  - [x] **Feature: Notification Provider Management**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Register providers
      - [x] Test case: Send notifications to all providers
      - [x] Test case: Handle provider errors
    - [x] **TDD: Write Failing Tests:** Implement in `tests/test_notification/test_manager.py`
    - [x] **Implementation:** Create `NotificationManager` class
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation

- [x] **Module: `mover_status/notification/__init__.py`**
  - [x] Export notification classes and functions

## Phase 7: Core Monitoring Logic

- [x] **Module: `mover_status/core/monitor.py`**
  - [x] **Analyze `moverStatus.sh`:** Review the main monitoring loop
  - [x] **Feature: Monitor Session Class**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Initialize monitoring session
      - [x] Test case: Track monitoring state
    - [x] **TDD: Write Failing Tests:** Implement in `tests/test_core/test_monitor.py`
    - [x] **Implementation:** Create `MonitorSession` class
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation

  - [x] **Feature: Process Detection and Monitoring**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Detect mover process start
      - [x] Test case: Detect mover process end
      - [x] Test case: Calculate initial size
    - [x] **TDD: Write Failing Tests:** Add to `tests/test_core/test_monitor.py`
    - [x] **Implementation:** Add process monitoring methods
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation

  - [x] **Feature: Progress Tracking**
    - [x] **TDD: Define Test Cases:**
      - [x] Test case: Track progress over time
      - [x] Test case: Calculate percentage complete
      - [x] Test case: Determine notification thresholds
    - [x] **TDD: Write Failing Tests:** Add to `tests/test_core/test_monitor.py`
    - [x] **Implementation:** Add progress tracking methods
    - [x] **TDD: Verify Tests Pass**
    - [x] **Refactor:** Review and optimize the implementation

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
