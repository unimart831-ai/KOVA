"""Outbound webhooks to marketplace partners."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

import requests
from celery import shared_task
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


def _webhook_enabled(mp, event: str) -> bool:
    if not mp.webhook_url:
        return False
    allowed = mp.get_setting("webhook_events")
    if allowed is None:
        return True
    if isinstance(allowed, list):
        return event in allowed
    return True


def _sign_payload(secret: str, body: bytes) -> str:
    if not secret:
        return ""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _log_delivery(
    mp,
    event: str,
    payload: dict,
    *,
    status: str,
    response_code: int | None = None,
    attempts: int = 1,
    error_message: str = "",
):
    from apps.partners.models import WebhookDeliveryLog

    body_preview = json.dumps(payload, default=str, sort_keys=True)
    payload_hash = hashlib.sha256(body_preview.encode()).hexdigest()
    try:
        WebhookDeliveryLog.objects.create(
            marketplace=mp,
            event=event,
            payload_hash=payload_hash,
            status=status,
            response_code=response_code,
            attempts=attempts,
            error_message=(error_message or "")[:2000],
        )
    except Exception:
        logger.exception("Failed to write webhook delivery log for %s/%s", mp.slug, event)


@shared_task(name="partners.dispatch_marketplace_webhook", bind=True, max_retries=3)
def dispatch_marketplace_webhook(self, marketplace_id: int, event: str, payload: dict):
    from apps.partners.models import MarketplacePartner

    try:
        mp = MarketplacePartner.objects.get(pk=marketplace_id, is_active=True)
    except MarketplacePartner.DoesNotExist:
        return {"skipped": "partner_not_found"}

    if not _webhook_enabled(mp, event):
        _log_delivery(mp, event, payload, status="skipped", attempts=self.request.retries + 1)
        return {"skipped": "event_disabled"}

    body = json.dumps({
        "event": event,
        "marketplace": mp.slug,
        "timestamp": timezone.now().isoformat(),
        "data": payload,
    }, default=str).encode()

    headers = {"Content-Type": "application/json", "User-Agent": "Kova-Marketplace-Webhook/1.0"}
    signature = _sign_payload(mp.webhook_secret, body)
    if signature:
        headers["X-Kova-Signature"] = signature

    attempt = self.request.retries + 1
    try:
        resp = requests.post(mp.webhook_url, data=body, headers=headers, timeout=15)
        resp.raise_for_status()
        _log_delivery(
            mp, event, payload,
            status="success",
            response_code=resp.status_code,
            attempts=attempt,
        )
        return {"ok": True, "status": resp.status_code}
    except Exception as exc:
        logger.warning("Marketplace webhook %s failed for %s: %s", event, mp.slug, exc)
        _log_delivery(
            mp, event, payload,
            status="failed",
            response_code=getattr(getattr(exc, "response", None), "status_code", None),
            attempts=attempt,
            error_message=str(exc),
        )
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


def notify_seller_activated(mp, seller, *, auto_activated: bool = False):
    dispatch_marketplace_webhook.delay(
        mp.pk,
        "seller.activated",
        {
            "external_seller_id": seller.external_seller_id,
            "seller_email": seller.user.email,
            "business_name": seller.business_name,
            "seller_status": seller.status,
            "auto_activated": auto_activated,
            "is_sandbox": bool(getattr(mp, "is_sandbox", False)),
        },
    )


def notify_product_synced(mp, seller, *, created: int, updated: int, product_ids: list[str]):
    dispatch_marketplace_webhook.delay(
        mp.pk,
        "product.synced",
        {
            "external_seller_id": seller.external_seller_id,
            "seller_email": seller.user.email,
            "created": created,
            "updated": updated,
            "product_ids": product_ids[:100],
        },
    )


def notify_content_generated(product, *, posts_created: int = 0, seed_id: str | None = None):
    mp = getattr(product, "marketplace_partner", None)
    if not mp:
        return

    from apps.partners.models import MarketplaceSellerAccount

    seller = MarketplaceSellerAccount.objects.filter(
        marketplace=mp, user=product.user,
    ).first()
    if seller and posts_created:
        MarketplaceSellerAccount.objects.filter(pk=seller.pk).update(
            content_generated=models.F("content_generated") + posts_created,
        )

    dispatch_marketplace_webhook.delay(
        mp.pk,
        "content.generated",
        {
            "external_seller_id": seller.external_seller_id if seller else "",
            "product_id": str(product.pk),
            "external_product_id": product.external_id,
            "product_name": product.name,
            "posts_created": posts_created,
            "seed_id": seed_id,
        },
    )


def notify_post_published(post):
    product = post.product
    if not product or not product.marketplace_partner_id:
        return

    mp = product.marketplace_partner
    from apps.partners.models import MarketplaceSellerAccount

    seller = MarketplaceSellerAccount.objects.filter(
        marketplace=mp, user=post.user,
    ).first()

    dispatch_marketplace_webhook.delay(
        mp.pk,
        "post.published",
        {
            "external_seller_id": seller.external_seller_id if seller else "",
            "product_id": str(product.pk),
            "external_product_id": product.external_id,
            "post_id": str(post.pk),
            "platform": post.platform or "",
            "platform_post_url": post.platform_post_url or "",
        },
    )
