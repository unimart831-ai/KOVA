"""
Photoroom API helpers — edit results, uncertainty score, sandbox quotas.

See https://docs.photoroom.com/image-editing-api-plus-plan/
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

SANDBOX_DAILY_CACHE_KEY = "photoroom:sandbox:daily:{date}"
SANDBOX_MONTHLY_CACHE_KEY = "photoroom:sandbox:monthly:{year}-{month}"

# Variants that assume a clean cutout — skip when segmentation is uncertain.
HIGH_UNCERTAINTY_VARIANT_IDS = frozenset({
    "ghost_mannequin",
    "virtual_model",
    "flat_lay",
})


@dataclass(frozen=True)
class PhotoroomEditResult:
    """v2/edit response with optional cutout confidence."""

    content: bytes | None
    uncertainty_score: float | None = None
    sandbox_limited: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return bool(self.content) and not self.sandbox_limited


def parse_uncertainty_score(headers) -> float | None:
    """Parse x-uncertainty-score (0–1); None if missing or -1 (unavailable)."""
    if not headers:
        return None
    raw = headers.get("x-uncertainty-score") or headers.get("X-Uncertainty-Score")
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return min(max(value, 0.0), 1.0)


def uncertainty_is_high(score: float | None) -> bool:
    if score is None:
        return False
    threshold = float(getattr(settings, "PHOTOROOM_UNCERTAINTY_HIGH_THRESHOLD", 0.6))
    return score >= threshold


def merge_uncertainty(current: float | None, new: float | None) -> float | None:
    """Keep the highest (worst) uncertainty seen in a pipeline."""
    if new is None:
        return current
    if current is None:
        return new
    return max(current, new)


def beautify_mode_for_category(category: str) -> str:
    """Map product category to beautify.mode per Photoroom docs."""
    if category == "food":
        return "ai.food"
    if category == "electronics":
        return "ai.car"
    return "ai.auto"


def _sandbox_active() -> bool:
    key = (getattr(settings, "PHOTOROOM_API_KEY", "") or "").strip()
    if not key:
        return False
    if getattr(settings, "PHOTOROOM_SANDBOX", False):
        return True
    return key.startswith("sandbox_")


def get_sandbox_usage() -> dict:
    """Daily and monthly sandbox call counts (cache-backed)."""
    now = timezone.now()
    day_key = SANDBOX_DAILY_CACHE_KEY.format(date=now.strftime("%Y-%m-%d"))
    month_key = SANDBOX_MONTHLY_CACHE_KEY.format(
        year=now.year, month=now.month,
    )
    daily = int(cache.get(day_key) or 0)
    monthly = int(cache.get(month_key) or 0)
    daily_limit = int(getattr(settings, "PHOTOROOM_SANDBOX_DAILY_LIMIT", 100))
    monthly_limit = int(getattr(settings, "PHOTOROOM_SANDBOX_MONTHLY_LIMIT", 1000))
    return {
        "daily": daily,
        "daily_limit": daily_limit,
        "monthly": monthly,
        "monthly_limit": monthly_limit,
        "daily_remaining": max(0, daily_limit - daily),
        "monthly_remaining": max(0, monthly_limit - monthly),
    }


def check_sandbox_quota() -> tuple[bool, str | None]:
    """Return (allowed, error_message) when sandbox limits would be exceeded."""
    if not _sandbox_active():
        return True, None
    usage = get_sandbox_usage()
    if usage["daily"] >= usage["daily_limit"]:
        return False, (
            f"Photoroom sandbox daily limit reached ({usage['daily_limit']} calls). "
            "Try again tomorrow or use a production API key."
        )
    if usage["monthly"] >= usage["monthly_limit"]:
        return False, (
            f"Photoroom sandbox monthly limit reached ({usage['monthly_limit']} calls)."
        )
    return True, None


def record_sandbox_call() -> None:
    """Increment sandbox usage counters after a successful API call."""
    if not _sandbox_active():
        return
    now = timezone.now()
    day_key = SANDBOX_DAILY_CACHE_KEY.format(date=now.strftime("%Y-%m-%d"))
    month_key = SANDBOX_MONTHLY_CACHE_KEY.format(
        year=now.year, month=now.month,
    )
    try:
        cache.incr(day_key)
    except ValueError:
        cache.set(day_key, 1, timeout=86400 * 2)
    try:
        cache.incr(month_key)
    except ValueError:
        # ~32 days
        cache.set(month_key, 1, timeout=86400 * 32)


def probe_cutout_uncertainty(image_url: str) -> tuple[float | None, PhotoroomEditResult]:
    """
    Lightweight cutout to read x-uncertainty-score before apparel AI variants.
    Uses minimal output size to reduce latency/cost.
    """
    from apps.products.photoroom_plus import photoroom_edit

    params = {
        "removeBackground": "true",
        "background.color": "FFFFFF",
        "outputSize": "512x512",
        "padding": "0.1",
        "shadow.mode": "ai.soft",
        "export.format": "jpeg",
        "referenceBox": "originalImage",
    }
    result = photoroom_edit(image_url, params)
    return result.uncertainty_score, result
