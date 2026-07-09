"""
Channels Redis layer configuration helpers.

Railway internal Redis (redis.railway.internal) can exceed redis-py's default
5s socket timeouts under cold start or network jitter. Celery uses sync redis
with different defaults; Channels uses channels_redis + redis.asyncio.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def build_channels_redis_hosts(
    redis_url: str,
    *,
    socket_connect_timeout: float = 15.0,
    socket_timeout: float = 15.0,
    socket_keepalive: bool = True,
    retry_on_timeout: bool = True,
    health_check_interval: int = 30,
) -> list[dict[str, Any]]:
    """Build channels_redis ``hosts`` entry with Railway-friendly timeouts.

    Pass the full ``REDIS_URL`` (``redis://`` or ``rediss://``) so TLS and auth
    are parsed by redis.asyncio — do not split host/port for Channels.
    """
    host: dict[str, Any] = {
        "address": redis_url,
        "socket_connect_timeout": socket_connect_timeout,
        "socket_timeout": socket_timeout,
        "socket_keepalive": socket_keepalive,
        "retry_on_timeout": retry_on_timeout,
        "health_check_interval": health_check_interval,
    }
    # Self-signed TLS (common on managed Redis); internal Railway redis:// skips this.
    if urlparse(redis_url).scheme == "rediss":
        host["ssl_cert_reqs"] = None
    return [host]


def build_channels_redis_layer_config(
    redis_url: str,
    *,
    socket_connect_timeout: float = 15.0,
    socket_timeout: float = 15.0,
    capacity: int = 1500,
    expiry: int = 60,
    group_expiry: int = 86_400,
) -> dict[str, Any]:
    """Full ``CONFIG`` dict for ``channels_redis.core.RedisChannelLayer``."""
    return {
        "hosts": build_channels_redis_hosts(
            redis_url,
            socket_connect_timeout=socket_connect_timeout,
            socket_timeout=socket_timeout,
        ),
        # Defaults are 100/60/86400; raise capacity for many concurrent WS tabs.
        "capacity": capacity,
        "expiry": expiry,
        "group_expiry": group_expiry,
    }
