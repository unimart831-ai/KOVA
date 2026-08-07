"""Post-purchase loop — what happens the moment money lands.

On a completed commerce payment Kova closes the loop:
  1. Attribute the sale to the product's RevenueFunnel (revenue + conversion).
  2. Build a cross-sell so the buyer's next purchase is one tap away.
  3. Record the follow-up + review stages (the review request itself is already
     scheduled via the lead→converted signal, so we don't duplicate it).

Everything is best-effort and idempotent — a failure here must never break the
payment path.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

MAX_CROSS_SELL = 3


def run_post_purchase(payment) -> dict:
    """Close the revenue loop for a completed payment. Returns a summary."""
    from apps.commerce.products.models import CommercePayment

    summary = {"funnel": False, "cross_sell": []}
    if payment.status != CommercePayment.Status.COMPLETED or not payment.product_id:
        return summary

    product = payment.product

    # 1. Attribute to the funnel.
    try:
        from apps.commerce.products.revenue_funnel import (
            ensure_funnel_for_product,
            mark_stage,
            record_conversion,
        )

        funnel = ensure_funnel_for_product(product, source_post=_source_post_for(product))
        record_conversion(funnel, payment)
        summary["funnel"] = True

        # 2. Cross-sell recommendations.
        cross_sell = build_cross_sell(product)
        summary["cross_sell"] = [p.name for p in cross_sell]
        if cross_sell:
            mark_stage(funnel, "upsell")

        # 3. Review stage — already scheduled via lead→converted; mark it.
        mark_stage(funnel, "followup")
        if _review_scheduled(payment):
            mark_stage(funnel, "review")
    except Exception:
        logger.exception("Post-purchase funnel step failed for payment %s", payment.pk)

    return summary


def build_cross_sell(product) -> list:
    """Related products to recommend after buying `product`."""
    try:
        from apps.commerce.products.commerce_links import related_public_products

        return list(
            related_public_products(
                product.user,
                product.pk,
                category_id=product.category_id,
                limit=MAX_CROSS_SELL,
            )
        )
    except Exception:
        return []


def _source_post_for(product):
    """Best-effort: the most recent published post for this product."""
    try:
        from apps.create.content.models import Post

        return (
            Post.objects.filter(user=product.user, product=product, status="published")
            .order_by("-published_at")
            .first()
        )
    except Exception:
        return None


def _review_scheduled(payment) -> bool:
    try:
        from apps.commerce.reviews.models import ReviewRequest

        return ReviewRequest.objects.filter(user=payment.user, customer_phone=payment.phone_number).exists()
    except Exception:
        return False
