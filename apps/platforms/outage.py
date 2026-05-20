"""
Platform outage detection.

Tracks consecutive publish failures per platform using Django cache.
When N+ failures occur across different users within a time window,
the platform is considered to be having an outage.

Thresholds:
  - 3+ failures within 10 minutes  → outage detected
  - 1 success resets the counter

Usage:
    from apps.platforms.outage import record_failure, record_success, get_outages

    record_failure("facebook")       # call on 5xx / outage errors
    record_success("facebook")       # call on any successful publish
    outages = get_outages()          # {"facebook": True, "linkedin": False, ...}
"""
from __future__ import annotations

from django.core.cache import cache

_PREFIX = "kova:platform_outage:"
_FAIL_KEY = "{}{}:failures"
_OUTAGE_KEY = "{}{}:is_outage"
_FAIL_TTL = 600       # failure counter expires in 10 minutes
_OUTAGE_TTL = 3600    # outage flag stays set for 1 hour (cleared by success)
_THRESHOLD = 3        # failures needed to declare outage


def record_failure(platform: str) -> bool:
    """
    Increment the failure counter for a platform.
    Returns True if this failure triggers an outage declaration.
    """
    key = _FAIL_KEY.format(_PREFIX, platform)
    try:
        count = cache.get(key, 0) + 1
        cache.set(key, count, _FAIL_TTL)
        if count >= _THRESHOLD:
            cache.set(_OUTAGE_KEY.format(_PREFIX, platform), True, _OUTAGE_TTL)
            return True
    except Exception:
        pass
    return False


def record_success(platform: str) -> None:
    """
    Reset failure state for a platform after a successful publish.
    Clears both the failure counter and the outage flag.
    """
    try:
        cache.delete(_FAIL_KEY.format(_PREFIX, platform))
        cache.delete(_OUTAGE_KEY.format(_PREFIX, platform))
    except Exception:
        pass


def is_outage(platform: str) -> bool:
    """Return True if the platform is currently flagged as having an outage."""
    try:
        return bool(cache.get(_OUTAGE_KEY.format(_PREFIX, platform), False))
    except Exception:
        return False


def get_outages() -> dict[str, bool]:
    """Return outage status for all tracked platforms."""
    platforms = ["facebook", "instagram", "linkedin", "tiktok", "whatsapp"]
    return {p: is_outage(p) for p in platforms}
