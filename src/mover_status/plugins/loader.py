"""Dynamic plugin loader for notification providers.

This module loads enabled notification provider plugins on demand,
validates the resulting objects implement the NotificationProvider Protocol,
and surfaces detailed diagnostics when loading fails (requirements 3.1–3.5).

Requirements:
    - 6.4: NO logging or exposure of secrets in error messages or diagnostic output
"""

from __future__ import annotations

import importlib
import inspect
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType, ModuleType
from typing import TypeIs, cast

from mover_status.plugins.discovery import PluginMetadata, discover_plugins
from mover_status.types import NotificationProvider
from mover_status.utils.sanitization import sanitize_exception

__all__ = ["LoadedPlugin", "PluginLoader", "PluginLoaderError"]

logger = logging.getLogger(__name__)

_DEFAULT_FACTORY = "create_provider"
_EMPTY_KWARGS: Mapping[str, object] = MappingProxyType({})


@dataclass(slots=True, frozen=True)
class LoadedPlugin:
    """Represents a successfully loaded provider plugin."""

    identifier: str
    provider: NotificationProvider
    metadata: PluginMetadata


class PluginLoaderError(Exception):
    """Raised when a plugin cannot be loaded or validated."""

    def __init__(self, message: str, *, metadata: PluginMetadata | None = None) -> None:
        super().__init__(message)
        self.metadata: PluginMetadata | None = metadata


class PluginLoader:
    """Loader responsible for initializing enabled provider plugins."""

    def __init__(self, *, logger_obj: logging.Logger | None = None) -> None:
        self._logger: logging.Logger = logger_obj or logger

    def load_enabled_plugins(
        self,
        *,
        provider_flags: Mapping[str, bool],
        factory_kwargs: Mapping[str, Mapping[str, object]] | None = None,
        force_rescan: bool = False,
    ) -> tuple[LoadedPlugin, ...]:
        """Load plugins for providers enabled in configuration.

        Args:
            provider_flags: Mapping of provider identifiers/flags to booleans.
            factory_kwargs: Optional mapping of provider identifiers to keyword
                arguments forwarded to the plugin factory.
            force_rescan: Whether to force rediscovery of plugin packages.
        """
        enabled_plugins = discover_plugins(
            enabled_only=True,
            provider_flags=provider_flags,
            force_rescan=force_rescan,
        )
        loaded: list[LoadedPlugin] = []
        for metadata in enabled_plugins:
            kwargs: Mapping[str, object]
            if factory_kwargs:
                kwargs = factory_kwargs.get(metadata.identifier, _EMPTY_KWARGS)
            else:
                kwargs = _EMPTY_KWARGS
            try:
                provider = self._initialize_provider(metadata, kwargs)
            except PluginLoaderError as exc:
                self._logger.exception(
                    "Failed to load provider plugin",
                    extra={
                        "plugin_identifier": metadata.identifier,
                        "plugin_entrypoint": metadata.entrypoint,
                        "plugin_error": sanitize_exception(exc),
                    },
                )
                continue
            loaded.append(
                LoadedPlugin(
                    identifier=metadata.identifier,
                    provider=provider,
                    metadata=metadata,
                )
            )
        return tuple(loaded)

    def _initialize_provider(
        self,
        metadata: PluginMetadata,
        init_kwargs: Mapping[str, object],
    ) -> NotificationProvider:
        module_name, attr_path = self._resolve_entrypoint(metadata)
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - importlib provides detail
            msg = f"Unable to import plugin module '{module_name}' for provider '{metadata.identifier}': {exc}"
            raise PluginLoaderError(msg, metadata=metadata) from exc

        try:
            target = self._resolve_attribute(module, attr_path)
        except AttributeError as exc:
            msg = (
                f"Entrypoint attribute '{attr_path}' not found in module '{module_name}' "
                f"for provider '{metadata.identifier}'"
            )
            raise PluginLoaderError(msg, metadata=metadata) from exc

        try:
            candidate = self._evaluate_entrypoint(target, init_kwargs)
        except Exception as exc:  # pragma: no cover - factory errors bubble up detail
            msg = f"Plugin entrypoint call failed for provider '{metadata.identifier}': {exc}"
            raise PluginLoaderError(msg, metadata=metadata) from exc

        if not isinstance(candidate, NotificationProvider):
            msg = (
                "Plugin entrypoint did not return a NotificationProvider instance "
                f"(provider='{metadata.identifier}', object={type(candidate).__name__})"
            )
            raise PluginLoaderError(msg, metadata=metadata)
        return candidate

    @staticmethod
    def _resolve_entrypoint(metadata: PluginMetadata) -> tuple[str, str]:
        entrypoint = metadata.entrypoint
        if entrypoint:
            module_name, attr_path = (
                entrypoint.split(":", maxsplit=1) if ":" in entrypoint else (entrypoint, _DEFAULT_FACTORY)
            )
        else:
            module_name = f"{metadata.package}.provider"
            attr_path = _DEFAULT_FACTORY

        module_name = module_name.strip()
        attr_path = attr_path.strip()
        if not module_name or not attr_path:
            msg = (
                f"Invalid entrypoint definition for provider '{metadata.identifier}': "
                f"entrypoint={metadata.entrypoint!r}"
            )
            raise PluginLoaderError(msg, metadata=metadata)
        return module_name, attr_path

    @staticmethod
    def _resolve_attribute(module: ModuleType, attr_path: str) -> object:
        target: object = module
        for part in attr_path.split("."):
            target = cast(object, getattr(target, part))
        return target

    @staticmethod
    def _evaluate_entrypoint(
        target: object,
        init_kwargs: Mapping[str, object],
    ) -> object:
        kwargs = dict(init_kwargs)

        if inspect.isclass(target):
            class_factory = cast(type[object], target)
            return class_factory(**kwargs)
        if _is_callable_object(target):
            return target(**kwargs)
        return target


def _is_callable_object(value: object) -> TypeIs[Callable[..., object]]:
    """Type predicate that narrows objects implementing __call__."""

    return callable(value)
