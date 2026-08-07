"""RevenueFunnel service — assemble and advance the revenue journey.

Wraps the RevenueFunnel model so callers (post-purchase, publishing) can create
a funnel for a product, mark stages complete, and record conversions with
attributed revenue — without touching JSON stage bookkeeping directly.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.utils import timezone

logger = logging.getLogger(__name__)


def ensure_funnel_for_product(product, *, source_post=None):
    """Get or create the (single) funnel for a product. Idempotent."""
    from apps.commerce.products.models import RevenueFunnel

    funnel, created = RevenueFunnel.objects.get_or_create(
        user=product.user,
        product=product,
        defaults={
            "name": product.name[:200],
            "landing_url": _landing_url(product),
            "currency": product.currency or "KES",
        },
    )
    changed = []
    if created or not funnel.landing_url:
        funnel.landing_url = _landing_url(product)
        changed.append("landing_url")
        _touch_stage(funnel, "landing")
        changed.append("stages")
    if source_post is not None and funnel.source_post_id is None:
        funnel.source_post = source_post
        changed.append("source_post")
        _touch_stage(funnel, "reel")
    if changed:
        funnel.save(update_fields=list(set(changed)) + ["updated_at"])
    return funnel


def mark_stage(funnel, stage: str) -> None:
    """Mark a funnel stage complete (idempotent per stage)."""
    from apps.commerce.products.models import RevenueFunnel

    if stage not in RevenueFunnel.STAGES:
        return
    if _touch_stage(funnel, stage):
        funnel.save(update_fields=["stages", "updated_at"])


def record_conversion(funnel, payment) -> None:
    """Attribute a completed payment to the funnel — revenue + conversion count."""
    from django.db.models import F

    from apps.commerce.products.models import RevenueFunnel

    amount = Decimal(str(payment.amount or 0))
    _touch_stage(funnel, "checkout")
    RevenueFunnel.objects.filter(pk=funnel.pk).update(
        conversions=F("conversions") + 1,
        attributed_revenue=F("attributed_revenue") + amount,
        status=RevenueFunnel.Status.CONVERTED,
        currency=payment.currency or funnel.currency,
        stages=funnel.stages,
        updated_at=timezone.now(),
    )


# ── helpers ─────────────────────────────────────────────────────────────────


def _touch_stage(funnel, stage: str) -> bool:
    """Set a stage done=True with a timestamp. Returns True if it changed."""
    stages = dict(funnel.stages or {})
    entry = stages.get(stage) or {}
    if entry.get("done"):
        return False
    stages[stage] = {"done": True, "at": timezone.now().isoformat()}
    funnel.stages = stages
    return True


def _landing_url(product) -> str:
    try:
        from apps.commerce.products.commerce_links import commerce_link_path

        return commerce_link_path(product, product.user.profile)
    except Exception:
        return (getattr(product, "product_url", "") or "")[:500]
