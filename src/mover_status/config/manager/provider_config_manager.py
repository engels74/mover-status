"""Provider-specific configuration file manager."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
import yaml

from ..loader.yaml_loader import YamlLoader


ProviderName = Literal["telegram", "discord"]


class ProviderConfigManager:
    """Manager for provider-specific configuration files."""

    # Default templates for provider configurations
    PROVIDER_TEMPLATES: dict[ProviderName, dict[str, object]] = {
        "telegram": {
            "bot_token": "YOUR_BOT_TOKEN",
            "chat_ids": ["YOUR_CHAT_ID"],
            "format": {
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "disable_notification": False,
            },
            "notifications": {
                "events": ["started", "progress", "completed", "failed"],
                "rate_limits": {
                    "progress": 300,
                    "status": 60,
                },
            },
            "retry": {
                "max_attempts": 3,
                "backoff_factor": 2.0,
                "timeout": 30,
            },
        },
        "discord": {
            "webhook_url": "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN",
            "username": "Mover Status Bot",
            "avatar_url": None,
            "embeds": {
                "enabled": True,
                "colors": {
                    "started": 0x00ff00,
                    "progress": 0x0099ff,
                    "completed": 0x00cc00,
                    "failed": 0xff0000,
                },
                "thumbnail": True,
                "timestamp": True,
            },
            "notifications": {
                "mentions": {
                    "started": [],
                    "failed": [],
                    "completed": [],
                },
                "rate_limits": {
                    "progress": 300,
                    "status": 60,
                },
            },
            "retry": {
                "max_attempts": 3,
                "backoff_factor": 2.0,
                "timeout": 30,
            },
        },
    }

    def __init__(self, config_dir: Path) -> None:
        """Initialize provider config manager.
        
        Args:
            config_dir: Directory where config files are stored
        """
        self.config_dir: Path = config_dir
        self.yaml_loader: YamlLoader = YamlLoader()

    def get_provider_config_path(self, provider: ProviderName) -> Path:
        """Get the path to a provider's configuration file.
        
        Args:
            provider: Provider name
            
        Returns:
            Path to the provider's config file
        """
        return self.config_dir / f"config_{provider}.yaml"

    def ensure_provider_config(self, provider: ProviderName) -> dict[str, object]:
        """Ensure provider config file exists, creating it if necessary.
        
        Args:
            provider: Provider name
            
        Returns:
            Provider configuration dictionary
        """
        config_path = self.get_provider_config_path(provider)
        
        if not config_path.exists():
            # Create default config
            default_config = self.get_provider_template(provider)
            self._save_config(config_path, default_config)
            return default_config
        
        # Load existing config
        return self.yaml_loader.load(config_path)

    def load_provider_config(self, provider: ProviderName) -> dict[str, object] | None:
        """Load provider configuration if file exists.
        
        Args:
            provider: Provider name
            
        Returns:
            Provider configuration or None if file doesn't exist
            
        Raises:
            ConfigLoadError: If file exists but cannot be loaded
        """
        config_path = self.get_provider_config_path(provider)
        
        if not config_path.exists():
            return None
            
        return self.yaml_loader.load(config_path)

    def save_provider_config(self, provider: ProviderName, config: dict[str, object]) -> None:
        """Save provider configuration to file.
        
        Args:
            provider: Provider name
            config: Configuration to save
        """
        config_path = self.get_provider_config_path(provider)
        self._save_config(config_path, config)

    def disable_provider(self, provider: ProviderName) -> None:
        """Disable a provider (keeps config file for later use).
        
        Args:
            provider: Provider name
        """
        # We don't delete the config file - just mark as disabled in main config
        # This method is here for interface consistency
        # In a real implementation, this would update the main config to set enabled=False
        _ = provider  # Use the parameter to avoid warning

    def get_provider_template(self, provider: ProviderName) -> dict[str, object]:
        """Get default template for a provider.
        
        Args:
            provider: Provider name
            
        Returns:
            Default configuration template
        """
        return self.PROVIDER_TEMPLATES.get(provider, {}).copy()

    def _save_config(self, path: Path, config: dict[str, object]) -> None:
        """Save configuration to YAML file.
        
        Args:
            path: Path to save to
            config: Configuration to save
        """
        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True) 