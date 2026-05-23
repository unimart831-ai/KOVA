"""Import products from a connected Shopify store."""

from __future__ import annotations

import logging
from decimal import Decimal

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

SHOPIFY_API_VERSION = "2024-10"


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


def sync_shopify_store_products(store) -> dict:
    """
    Pull products from Shopify Admin API into the user's Kova catalog.
    Upserts by external_id = shopify product id.
    """
    from apps.products.commerce_seo import ensure_commerce_seo_copy
    from apps.products.models import Product

    user = store.user
    url = (
        f"https://{store.shop_domain}/admin/api/{SHOPIFY_API_VERSION}/products.json"
        f"?limit=50&status=active"
    )

    try:
        resp = requests.get(url, headers=_shopify_headers(store.access_token), timeout=30)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        logger.error("Shopify product sync failed for %s: %s", store.shop_domain, exc)
        return {"error": str(exc), "created": 0, "updated": 0}

    raw_products = payload.get("products") or []
    created = 0
    updated = 0
    queued_ids: list[str] = []
    errors: list[dict] = []

    for item in raw_products:
        try:
            ext_id = str(item.get("id") or "")
            if not ext_id:
                continue

            title = (item.get("title") or "Shopify product")[:200]
            body = (item.get("body_html") or "").replace("<br>", "\n").replace("<br/>", "\n")
            while "<" in body and ">" in body:
                start = body.find("<")
                end = body.find(">", start)
                if end == -1:
                    break
                body = body[:start] + body[end + 1:]
            body = body.strip()[:2000]

            images = [img.get("src") for img in (item.get("images") or []) if img.get("src")]
            variant = (item.get("variants") or [{}])[0]
            price = _parse_price(variant.get("price"))
            qty = variant.get("inventory_quantity")
            handle = item.get("handle") or ""
            product_url = f"https://{store.shop_domain.replace('.myshopify.com', '')}.com/products/{handle}"
            if store.shop_domain:
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
                updated += 1
                queued_ids.append(str(existing.pk))
            else:
                product = Product.objects.create(user=user, external_id=ext_id, **product_data)
                ensure_commerce_seo_copy(product, user.profile)
                created += 1
                queued_ids.append(str(product.pk))
        except Exception as exc:
            errors.append({"shopify_id": item.get("id"), "error": str(exc)})

    store.products_synced = Product.objects.filter(
        user=user,
        source=Product.Source.API,
        marketplace_metadata__shopify=True,
        is_active=True,
    ).count()
    store.last_product_sync = timezone.now()
    store.save(update_fields=["products_synced", "last_product_sync", "updated_at"])

    autopilot_queued = 0
    profile = user.profile
    if profile.commerce_autopilot and queued_ids:
        from apps.products.tasks import snap_to_sell_analyze
        from apps.utils import fire_task

        for pid in queued_ids[:30]:
            product = Product.objects.filter(pk=pid).first()
            if product and product.all_image_urls:
                fire_task(snap_to_sell_analyze, pid, skip_quick_post=False)
                autopilot_queued += 1

    return {
        "created": created,
        "updated": updated,
        "total_shopify": len(raw_products),
        "autopilot_queued": autopilot_queued,
        "errors": errors[:20],
    }
