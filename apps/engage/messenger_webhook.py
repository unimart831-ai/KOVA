"""
Facebook Page Messenger webhook — real-time DM delivery.

Meta Page webhooks deliver Messenger DMs to Kova without waiting for the
30-minute Engage Agent polling cycle. Polling via ``fetch_dms_for_user`` remains
as a fallback when webhooks are unavailable.

Security:
- GET: Meta verification challenge — reuses ``WHATSAPP_VERIFY_TOKEN`` (same Meta app).
- POST: HMAC-SHA256 via ``FACEBOOK_APP_SECRET`` (falls back to ``WHATSAPP_APP_SECRET``).

Register in Meta Developer Portal → Webhooks → Page → ``messages`` field:
  Callback URL: https://<domain>/engage/webhook/messenger/
  Verify token: value of ``WHATSAPP_VERIFY_TOKEN``
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from apps.platforms.models import SocialAccount

logger = logging.getLogger(__name__)


@csrf_exempt
def messenger_webhook(request):
    """Handle Meta Page Messenger webhook (GET verify, POST events)."""
    if request.method == "GET":
        return _handle_verification(request)
    if request.method == "POST":
        return _handle_event(request)
    return HttpResponse(status=405)


def _handle_verification(request):
    mode = request.GET.get("hub.mode", "")
    token = request.GET.get("hub.verify_token", "")
    challenge = request.GET.get("hub.challenge", "")
    verify_token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", "")

    if mode == "subscribe" and verify_token and token == verify_token:
        logger.info("Messenger webhook verified successfully")
        return HttpResponse(challenge, content_type="text/plain")

    logger.warning("Messenger webhook verification failed: mode=%s", mode)
    return HttpResponse("Forbidden", status=403)


def _verify_signature(payload: bytes, signature: str) -> bool:
    app_secret = (
        getattr(settings, "FACEBOOK_APP_SECRET", "")
        or getattr(settings, "WHATSAPP_APP_SECRET", "")
    )
    if not app_secret:
        if settings.DEBUG:
            logger.warning(
                "FACEBOOK_APP_SECRET not set — skipping Messenger signature check (dev only)"
            )
            return True
        logger.error("FACEBOOK_APP_SECRET not set in production — rejecting unsigned webhook")
        return False

    expected = hmac.new(app_secret.encode(), payload, hashlib.sha256).hexdigest()
    provided = signature.replace("sha256=", "") if signature else ""
    return hmac.compare_digest(expected, provided)


def _handle_event(request):
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not settings.DEBUG and not signature:
        logger.warning("Messenger webhook missing X-Hub-Signature-256 in production")
        return HttpResponse("Missing signature", status=403)
    if not _verify_signature(request.body, signature):
        logger.warning("Messenger webhook signature verification failed")
        return HttpResponse("Invalid signature", status=403)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return HttpResponse("Invalid JSON", status=400)

    if body.get("object") != "page":
        return HttpResponse("Not a page event", status=404)

    for entry in body.get("entry", []):
        page_id = str(entry.get("id", ""))
        if not page_id:
            continue
        social_account = _find_facebook_account_by_page_id(page_id)
        if not social_account:
            logger.warning("No Facebook SocialAccount for page_id=%s", page_id)
            continue

        for event in entry.get("messaging", []):
            _process_messaging_event(social_account, page_id, event)

    return HttpResponse("ok", status=200)


def _process_messaging_event(social_account, page_id: str, event: dict) -> None:
    message = event.get("message") or {}
    if not message or message.get("is_echo"):
        return

    mid = message.get("mid", "")
    if not mid:
        return

    sender = event.get("sender", {})
    sender_id = str(sender.get("id", ""))
    if not sender_id or sender_id == page_id:
        return

    text = message.get("text", "")
    if not text and message.get("attachments"):
        text = "[Attachment]"

    sender_name = _lookup_sender_name(social_account, page_id, sender_id)

    try:
        from apps.engage.dm_inbox import bridge_messenger_message_to_inbox

        bridge_messenger_message_to_inbox(
            social_account=social_account,
            sender_id=sender_id,
            sender_name=sender_name,
            message_text=text,
            message_id=mid,
        )
    except Exception:
        logger.exception("Messenger inbox bridge failed for mid=%s", mid[:16])


def _lookup_sender_name(social_account, page_id: str, sender_id: str) -> str:
    meta = social_account.metadata or {}
    pages = meta.get("pages", [])
    page_token = social_account.access_token
    for page in pages:
        if str(page.get("id")) == page_id:
            page_token = page.get("access_token", page_token)
            break

    try:
        import httpx
        from apps.platforms.providers.instagram_facebook import FB_API_BASE, HTTP_TIMEOUT

        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            resp = client.get(
                f"{FB_API_BASE}/{sender_id}",
                params={"fields": "name", "access_token": page_token},
            )
            if resp.is_success:
                return resp.json().get("name", "") or sender_id
    except Exception:
        logger.debug("Messenger sender name lookup failed for %s", sender_id)

    return sender_id


def _find_facebook_account_by_page_id(page_id: str):
    """Match a connected Facebook account by Page ID in metadata.pages."""
    page_id = str(page_id)
    for account in SocialAccount.objects.filter(platform="facebook", is_active=True):
        meta = account.metadata or {}
        if meta.get("selected_page_id") == page_id:
            return account
        for page in meta.get("pages", []):
            if str(page.get("id")) == page_id:
                return account
    return None
