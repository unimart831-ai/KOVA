"""Helpers for marketplace product sync — images and autopilot triggers."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def merge_sync_images(data: dict) -> list[str]:
    """Combine primary image_url and additional_images from a sync payload."""
    images: list[str] = []
    primary = (data.get("image_url") or "").strip()
    if primary:
        images.append(primary)
    for url in data.get("additional_images") or []:
        url = (url or "").strip()
        if url and url not in images:
            images.append(url)
    return images[:12]


def apply_sync_images_to_product_data(product_data: dict, data: dict) -> dict:
    images = merge_sync_images(data)
    if images:
        product_data["additional_images"] = images
    return product_data


def trigger_marketplace_autopilot(user, mp, product_ids: list) -> int:
    """
    Run Snap/Autopilot for synced products that have images.
    Returns count of products queued.
    """
    if not mp.auto_snap_on_sync or not product_ids:
        return 0

    from apps.products.models import Product
    from apps.products.tasks import snap_to_sell_analyze
    from apps.utils import fire_task

    queued = 0
    for pid in product_ids[:50]:
        product = Product.objects.filter(pk=pid, user=user).first()
        if not product or not product.all_image_urls:
            continue
        fire_task(snap_to_sell_analyze, str(product.pk), skip_quick_post=False)
        queued += 1
    return queued
