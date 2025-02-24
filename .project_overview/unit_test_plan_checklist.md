# MoverStatus Unit Test Plan

This document outlines the comprehensive unit test plan for the MoverStatus application. Tests are organized by module and functionality.

## Core Module Tests

### Calculator Tests (`tests/core/test_calculator.py`)

- [x] TransferStats data class

  - [x] Default & custom initialization
  - [x] Property calculations

- [x] TransferCalculator class
  - [x] Initialization & settings
  - [x] initialize_transfer: valid size, errors (0, negative, max)
  - [x] update_progress: updates, edge cases, rate & time calc
  - [x] reset method
  - [x] monitor_transfer: valid/invalid callbacks, cancel, errors

### Monitor Tests (`tests/core/test_monitor.py`)

- [x] DirectoryScanner class

  - [x] Initialization, path exclusion, cache, and async scanning

- [x] MonitorStats class

  - [x] Initialization and state updates

- [x] MoverMonitor class
  - [x] Core functionality (init, events, notifications)
  - [x] Process monitoring and version checking
  - [x] Async operations (context manager, shutdown)

### Process Tests (`tests/core/test_process.py`)

- [x] `ProcessState` enumeration
- [x] `ProcessStats` data class
- [x] `ProcessManager` class
  - [x] Process discovery
  - [x] Resource usage statistics
  - [x] Error handling
  - [x] Async operations

## Configuration Tests

### Settings Tests (`tests/config/test_settings.py`)

- [x] Test `Settings` class:
  - [x] Environment variables
  - [x] YAML loading
  - [x] Validation rules
  - [x] Default values
  - [x] Active providers

### Provider Settings Tests

- [x] Test Discord Settings (`tests/config/providers/discord/test_settings.py`)

  - [x] Test webhook URL validation
  - [x] Test username validation
  - [x] Test rate limiting configuration
  - [x] Test message customization

- [x] Test Telegram Settings (`tests/config/providers/telegram/test_settings.py`)
  - [x] Test bot token validation
  - [x] Test chat ID validation
  - [x] Test API configuration
  - [x] Test rate limiting settings

## Notification Tests

### Base Tests (`
