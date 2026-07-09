"""Celery tasks for media orchestration."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="media_queue.process_queues")
def process_media_queues():
    """Deprecated no-op — Visual Publisher queue removed.

    django-celery-beat may still schedule this until ``prune_stale_beat_tasks``
    runs on deploy. Registering the task prevents worker KeyError spam.
    """
    logger.debug("media_queue.process_queues is deprecated; skipping")
    return {"deprecated": True, "processed": 0}


@shared_task(name="media.plan_asset_media")
def plan_asset_media_task(product_id: str, analysis: dict | None = None):
  from apps.products.models import Product
  from apps.media.orchestrator import apply_flux_enhancement_if_needed, plan_media_for_product

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

