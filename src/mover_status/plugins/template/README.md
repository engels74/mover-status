# Plugin Template

This directory contains a template implementation for creating notification provider plugins for the Mover Status Monitor.

## Overview

The plugin system allows you to create custom notification providers that can be dynamically loaded and configured. Each provider must implement the `NotificationProvider` interface and provide proper configuration models.

## File Structure

- `provider.py` - Main provider implementation
- `config.py` - Configuration model for the provider
- `models.py` - Provider-specific data models

## Creating a New Provider

1. Copy this template directory to a new directory named after your provider
2. Implement the required methods in `provider.py`
3. Define your configuration schema in `config.py`
4. Add any provider-specific models in `models.py`
5. Update the plugin loader to recognize your provider

## Required Methods

... Placeholder text ...