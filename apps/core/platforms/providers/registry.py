"""
Provider registry — maps platform names to provider instances.
"""

from __future__ import annotations

from typing import Optional

from apps.core.platforms.providers.base import BaseProvider

provider_registry: dict[str, BaseProvider] = {}


def register_provider(provider: BaseProvider):
    """Register a provider instance by its platform_name."""
    provider_registry[provider.platform_name] = provider


def get_provider(platform_name: str) -> Optional[BaseProvider]:
    """Get the provider instance for a platform. Returns None if not found."""
    return provider_registry.get(platform_name)
