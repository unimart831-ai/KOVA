"""Shopify OAuth install flow and webhook registration."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.urls import reverse

from apps.products.shopify_import import SHOPIFY_API_VERSION, _shopify_headers

logger = logging.getLogger(__name__)

SHOPIFY_OAUTH_SCOPES_DEFAULT = (
    "read_products,write_products,read_orders,read_inventory"
)

WEBHOOK_TOPICS = (
    "products/create",
    "products/update",
    "orders/create",
)


def shopify_scopes() -> str:
    return getattr(settings, "SHOPIFY_SCOPES", SHOPIFY_OAUTH_SCOPES_DEFAULT)


def shopify_configured() -> bool:
    return bool(getattr(settings, "SHOPIFY_API_KEY", "") and getattr(settings, "SHOPIFY_API_SECRET", ""))


def normalize_shop_domain(shop: str) -> str:
    shop = (shop or "").strip().lower()
    shop = shop.replace("https://", "").replace("http://", "").split("/")[0]
    if shop and not shop.endswith(".myshopify.com"):
        shop = f"{shop}.myshopify.com"
    return shop


def verify_shopify_oauth_hmac(query_params, secret: str) -> bool:
    """Verify Shopify OAuth callback query HMAC."""
    params = {k: v for k, v in query_params.items() if k not in ("hmac", "signature")}
    encoded = "&".join(f"{k}={params[k]}" for k in sorted(params))
    digest = hmac.new(secret.encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, query_params.get("hmac", ""))


def oauth_begin_url(request, shop_domain: str, state: str) -> str:
    callback = request.build_absolute_uri(reverse("analytics:shopify_oauth_callback"))
    params = urlencode({
        "client_id": settings.SHOPIFY_API_KEY,
        "scope": shopify_scopes(),
        "redirect_uri": callback,
        "state": state,
    })
    return f"https://{shop_domain}/admin/oauth/authorize?{params}"


def exchange_code_for_token(shop_domain: str, code: str) -> dict:
    url = f"https://{shop_domain}/admin/oauth/access_token"
    resp = requests.post(
        url,
        json={
            "client_id": settings.SHOPIFY_API_KEY,
            "client_secret": settings.SHOPIFY_API_SECRET,
            "code": code,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def register_shopify_webhooks(store, request=None) -> dict:
    """Register product + order webhooks for a connected store."""
    site = getattr(settings, "SITE_URL", "").rstrip("/")
    if not site and request:
        site = request.build_absolute_uri("/").rstrip("/")
    if not site:
        return {"registered": 0, "errors": ["SITE_URL not configured"]}

    product_url = f"{site}{reverse('analytics:shopify_product_webhook')}"
    order_url = f"{site}{reverse('analytics:shopify_order_webhook')}"
    topic_urls = {
        "products/create": product_url,
        "products/update": product_url,
        "orders/create": order_url,
    }

    registered = 0
    errors: list[str] = []
    headers = _shopify_headers(store.access_token)
    list_url = f"https://{store.shop_domain}/admin/api/{SHOPIFY_API_VERSION}/webhooks.json"

    try:
        existing_resp = requests.get(list_url, headers=headers, timeout=30)
        existing_resp.raise_for_status()
        existing_topics = {
            wh.get("topic")
            for wh in (existing_resp.json().get("webhooks") or [])
        }
    except Exception as exc:
        logger.warning("Could not list Shopify webhooks for %s: %s", store.shop_domain, exc)
        existing_topics = set()

    for topic in WEBHOOK_TOPICS:
        if topic in existing_topics:
            registered += 1
            continue
        address = topic_urls[topic]
        try:
            resp = requests.post(
                list_url,
                headers=headers,
                json={"webhook": {"topic": topic, "address": address, "format": "json"}},
                timeout=30,
            )
            if resp.status_code in (200, 201):
                registered += 1
            else:
                errors.append(f"{topic}: HTTP {resp.status_code}")
        except Exception as exc:
            errors.append(f"{topic}: {exc}")

    return {"registered": registered, "errors": errors}


def new_oauth_state() -> str:
    return secrets.token_urlsafe(32)
