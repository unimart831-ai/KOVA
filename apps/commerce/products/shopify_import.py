"""Import products from a connected Shopify store."""

from __future__ import annotations

import logging
import re
from decimal import Decimal

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

SHOPIFY_API_VERSION = "2024-10"
SHOPIFY_PAGE_LIMIT = 250


def _shopify_headers(access_token: str) -> dict:
    return {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }


def _parse_price(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _strip_html(body: str) -> str:
    body = (body or "").replace("<br>", "\n").replace("<br/>", "\n")
    while "<" in body and ">" in body:
        start = body.find("<")
        end = body.find(">", start)
        if end == -1:
            break
        body = body[:start] + body[end + 1:]
    return body.strip()[:2000]


def _next_page_url(link_header: str) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        if 'rel="next"' in part:
            match = re.search(r"<([^>]+)>", part)
            if match:
                return match.group(1)
    return None


def upsert_shopify_product(store, item: dict) -> tuple[str | None, str | None]:
    """
    Upsert one Shopify product payload into Kova catalog.
    Returns (product_id, action) where action is 'created' or 'updated'.
    """
    from apps.commerce.products.commerce_seo import ensure_commerce_seo_copy
    from apps.commerce.products.models import Product

    user = store.user
    ext_id = str(item.get("id") or "")
    if not ext_id:
        return None, None

    title = (item.get("title") or "Shopify product")[:200]
    body = _strip_html(item.get("body_html") or "")
    images = [img.get("src") for img in (item.get("images") or []) if img.get("src")]
    variant = (item.get("variants") or [{}])[0]
    price = _parse_price(variant.get("price"))
    qty = variant.get("inventory_quantity")
    handle = item.get("handle") or ""
    product_url = f"https://{store.shop_domain}/products/{handle}"

    stock_status = Product.StockStatus.IN_STOCK
    if qty is not None:
        if qty <= 0:
            stock_status = Product.StockStatus.OUT_OF_STOCK
        elif qty <= 5:
            stock_status = Product.StockStatus.LOW_STOCK

    product_data = {
        "name": title,
        "description": body,
        "price": price,
        "currency": "USD",
        "stock_status": stock_status,
        "quantity": qty if qty is not None else None,
        "product_url": product_url,
        "source": Product.Source.API,
        "additional_images": images[:12],
        "marketplace_metadata": {
            "shopify": True,
            "shop_domain": store.shop_domain,
            "shopify_handle": handle,
            "shopify_product_id": ext_id,
        },
        "last_synced_at": timezone.now(),
        "is_active": item.get("status") == "active",
    }

    existing = Product.objects.filter(user=user, external_id=ext_id).first()
    if existing:
        for key, val in product_data.items():
            setattr(existing, key, val)
        existing.save()
        return str(existing.pk), "updated"

    product = Product.objects.create(user=user, external_id=ext_id, **product_data)
    ensure_commerce_seo_copy(product, user.profile)
    return str(product.pk), "created"


def fetch_shopify_products(store) -> tuple[list[dict], str | None]:
    """Fetch all active products using Shopify cursor pagination."""
    products: list[dict] = []
    url = (
        f"https://{store.shop_domain}/admin/api/{SHOPIFY_API_VERSION}/products.json"
        f"?limit={SHOPIFY_PAGE_LIMIT}&status=active"
    )

    while url:
        try:
            resp = requests.get(url, headers=_shopify_headers(store.access_token), timeout=60)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            logger.error("Shopify product fetch failed for %s: %s", store.shop_domain, exc)
            return products, str(exc)

        products.extend(payload.get("products") or [])
        url = _next_page_url(resp.headers.get("Link", ""))

    return products, None


def sync_shopify_store_products(store) -> dict:
    """
    Pull products from Shopify Admin API into the user's Kova catalog.
    Upserts by external_id = shopify product id.
    """
    from apps.commerce.products.models import Product
    from apps.commerce.products.tasks import snap_to_sell_analyze
    from apps.core.utils import fire_task

    raw_products, error = fetch_shopify_products(store)
    if error and not raw_products:
        return {"error": error, "created": 0, "updated": 0}

    created = 0
    updated = 0
    queued_ids: list[str] = []
    errors: list[dict] = []

    for item in raw_products:
        try:
            pid, action = upsert_shopify_product(store, item)
            if not pid:
                continue
            if action == "created":
                created += 1
            elif action == "updated":
                updated += 1
            queued_ids.append(pid)
        except Exception as exc:
            errors.append({"shopify_id": item.get("id"), "error": str(exc)})

    store.products_synced = Product.objects.filter(
        user=store.user,
        source=Product.Source.API,
        marketplace_metadata__shopify=True,
        is_active=True,
    ).count()
    store.last_product_sync = timezone.now()
    store.save(update_fields=["products_synced", "last_product_sync", "updated_at"])

    autopilot_queued = 0
    profile = store.user.profile
    if profile.commerce_autopilot and queued_ids:
        for pid in queued_ids[:30]:
            product = Product.objects.filter(pk=pid).first()
            if product and product.all_image_urls:
                fire_task(snap_to_sell_analyze, pid, skip_quick_post=False)
                autopilot_queued += 1

    result = {
        "created": created,
        "updated": updated,
        "total_shopify": len(raw_products),
        "autopilot_queued": autopilot_queued,
        "errors": errors[:20],
    }
    if error:
        result["warning"] = error
    return result
