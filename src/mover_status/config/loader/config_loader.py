"""Configuration loader that handles main config and provider-specific configs."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from .yaml_loader import YamlLoader
from .env_loader import EnvLoader
from ..manager.config_merger import ConfigMerger
from ..manager.provider_config_manager import ProviderConfigManager


class ConfigLoader:
    """Loader for complete configuration including provider-specific files."""

    def __init__(self, config_dir: Path | None = None) -> None:
        """Initialize configuration loader.
        
        Args:
            config_dir: Configuration directory (defaults to current directory)
        """
        self.config_dir: Path = config_dir or Path.cwd()
        self.yaml_loader: YamlLoader = YamlLoader()
        self.env_loader: EnvLoader = EnvLoader(convert_types=True)
        self.merger: ConfigMerger = ConfigMerger()
        self.provider_manager: ProviderConfigManager = ProviderConfigManager(self.config_dir)

    def load_complete_config(self) -> dict[str, object]:
        """Load complete configuration from all sources.
        
        This method:
        1. Loads main configuration file
        2. Loads enabled provider configuration files
        3. Applies environment variable overrides
        4. Merges everything with proper precedence
        
        Returns:
            Complete merged configuration
        """
        # Load main configuration
        main_config_path = self.config_dir / "config.yaml"
        if not main_config_path.exists():
            # Try alternative names
            for alt_name in ["config.yml", "config.json"]:
                alt_path = self.config_dir / alt_name
                if alt_path.exists():
                    main_config_path = alt_path
                    break
        
        main_config: dict[str, object] = {}
        if main_config_path.exists():
            main_config = self.yaml_loader.load(main_config_path)
        
        # Start with main config
        merged_config = main_config.copy()
        
        # Ensure providers section exists
        if "providers" not in merged_config:
            merged_config["providers"] = {}
        
        providers_section = merged_config["providers"]
        if not isinstance(providers_section, dict):
            providers_section = {}
            merged_config["providers"] = providers_section
        
        # Load enabled provider configs
        enabled_providers = self._get_enabled_providers(main_config)

        for provider in enabled_providers:
            provider_config = self.provider_manager.load_provider_config(provider)
            if provider_config is None:
                # Auto-create default config if missing
                provider_config = self.provider_manager.ensure_provider_config(provider)

            # Merge provider config into main config
            if provider not in providers_section:
                providers_section[provider] = {}

            provider_section: object = providers_section[provider]  # pyright: ignore[reportUnknownVariableType] # Dynamic config data
            if isinstance(provider_section, dict):
                # Merge with existing provider section - provider_config is guaranteed to be dict[str, object]
                provider_section.update(provider_config)  # pyright: ignore[reportUnknownMemberType] # Dict update after isinstance check
            else:
                # Replace with provider config
                providers_section[provider] = provider_config
        
        # Apply environment overrides last (highest precedence)
        env_config = self.env_loader.load()
        final_config = self.merger.merge(merged_config, env_config)
        
        return final_config



    def _get_enabled_providers(self, config: dict[str, object]) -> list[Literal["telegram", "discord"]]:
        """Get list of enabled providers from config.
        
        Args:
            config: Main configuration
            
        Returns:
            List of enabled provider names
        """
        enabled: list[Literal["telegram", "discord"]] = []
        
        # Check notifications.enabled_providers (primary source)
        notifications: object = config.get("notifications", {})
        if isinstance(notifications, dict):
            enabled_providers: object = notifications.get("enabled_providers", [])  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType] # Dynamic config data
            if isinstance(enabled_providers, list):
                for provider in enabled_providers:  # pyright: ignore[reportUnknownVariableType] # List iteration after isinstance check
                    if provider == "telegram":
                        enabled.append("telegram")
                    elif provider == "discord":
                        enabled.append("discord")
        
        # Also check providers section for enabled flags
        providers: object = config.get("providers", {})
        if isinstance(providers, dict):
            for provider_name in ["telegram", "discord"]:
                provider_config: object = providers.get(provider_name, {})  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType] # Dynamic config data
                if isinstance(provider_config, dict):
                    enabled_value: object = provider_config.get("enabled", False)  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType] # Dynamic config data
                    if enabled_value:
                        if provider_name == "telegram" and "telegram" not in enabled:
                            enabled.append("telegram")
                        elif provider_name == "discord" and "discord" not in enabled:
                            enabled.append("discord")
        
        return enabled 