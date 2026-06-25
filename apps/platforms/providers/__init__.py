# Import providers so they self-register on startup.
from apps.platforms.providers import instagram_facebook  # noqa: F401
from apps.platforms.providers import linkedin  # noqa: F401
from apps.platforms.providers import tiktok  # noqa: F401
from apps.platforms.providers import whatsapp  # noqa: F401
from apps.platforms.providers.registry import get_provider, register_provider

__all__ = ["get_provider", "register_provider"]
