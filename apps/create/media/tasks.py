"""Celery tasks for media orchestration."""

from __future__ import annotations

from celery import shared_task


@shared_task(name="media.plan_asset_media")
def plan_asset_media_task(product_id: str, analysis: dict | None = None):
    from apps.commerce.products.models import Product
    from apps.create.media.orchestrator import apply_flux_enhancement_if_needed, plan_media_for_product

    try:
        product = Product.objects.select_related("user").get(pk=product_id)
    except Product.DoesNotExist:
        return {"error": "not_found"}

    plan = plan_media_for_product(product, analysis=analysis)
    flux_url = apply_flux_enhancement_if_needed(product, plan)
    return {
        "product_id": product_id,
        "plan": plan.to_metadata(),
        "flux_edit_url": flux_url,
    }
