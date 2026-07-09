"""
Owner alerts — proactive WhatsApp notifications to business owners.

Sends operational alerts (payment received, new lead, etc.) to the owner's
personal WhatsApp via Kova's master number — the same channel as the Daily
Brief. This keeps WhatsApp as the primary notification surface, per the
WhatsApp-first product vision.

All sends are best-effort: failures are logged, never raised.
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(name="briefs.send_owner_alert", ignore_result=True)
def send_owner_alert_task(user_id: int, body: str):
    """Async wrapper so callers (signals, webhooks) never block on the WA API."""
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user:
        send_owner_alert(user, body)


def send_owner_alert(user, body: str) -> bool:
    """Send a plain-text alert to the owner's WhatsApp via the master number.

    Returns True when the message was accepted by the API, False otherwise
    (missing phone, missing master credentials, or send failure).
    """
    if not user or not body:
        return False

    phone = (getattr(user, "phone_number", "") or "").strip()
    if not phone:
        return False

    from apps.accounts.phone_utils import phone_to_whatsapp_digits

    wa_id = phone_to_whatsapp_digits(phone)
    if not wa_id:
        return False

    token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "") or ""
    phone_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "") or ""
    if not (token and phone_id):
        logger.debug("Owner alert skipped for user %s — master WA creds missing", user.pk)
        return False

    from apps.platforms.providers.whatsapp import WhatsAppProvider

    try:
        result = WhatsAppProvider().send_text_message(
            access_token=token,
            to=wa_id,
            body=body[:4096],
            phone_number_id=phone_id,
        )
    except Exception:
        logger.exception("Owner alert send crashed for user %s", user.pk)
        return False

    if not result.get("success"):
        logger.info("Owner alert not delivered to user %s: %s", user.pk, result.get("error"))
        return False
    return True


def queue_owner_alert(user, body: str) -> None:
    """Queue the alert on Celery; fall back to a synchronous send if the
    broker is unavailable (e.g. eager mode in tests/dev)."""
    try:
        send_owner_alert_task.delay(user.pk, body)
    except Exception:
        logger.debug("Celery unavailable — sending owner alert synchronously")
        send_owner_alert(user, body)


def notify_owner_hot_lead(lead) -> None:
    """Stronger alert for HOT leads."""
    if getattr(lead, "temperature", "") != "hot":
        notify_owner_new_lead(lead)
        return
    who = lead.name or lead.phone or lead.email or "Someone"
    body = (
        f"🔥 *Hot lead needs you*\n\n"
        f"{who}"
        f"{chr(10) + '📞 ' + lead.phone if lead.phone else ''}\n\n"
        f"Reply LEADS · or open inbox to respond."
    )
    queue_owner_alert(lead.user, body)


def notify_owner_complaint(user, *, platform: str, preview: str) -> None:
    body = (
        f"⚠️ *Complaint on {platform}*\n"
        f"\"{preview[:160]}{'…' if len(preview) > 160 else ''}\"\n\n"
        f"Reply REPLIES to review AI draft · APPROVE REPLY to send."
    )
    queue_owner_alert(user, body)


def notify_owner_unanswered_dms(user, count: int) -> None:
    if count <= 0:
        return
    body = (
        f"💬 *{count} conversation{'s' if count != 1 else ''} waiting*\n"
        f"Reply REPLIES to review AI drafts."
    )
    queue_owner_alert(user, body)


def notify_owner_new_lead(lead) -> None:
    """Alert the owner on their personal WhatsApp when a new lead is captured."""
    source_labels = {
        "form_submission": "your page form",
        "social_dm": "a WhatsApp/DM conversation",
        "social_comment": "a social media comment",
        "booking": "a booking",
        "qr_scan": "a QR scan",
        "walk_in": "a walk-in",
        "commerce_purchase": "a purchase",
        "manual": "manual entry",
    }
    source = source_labels.get(lead.source_type, lead.source_type or "your online presence")
    who = lead.name or lead.phone or lead.email or "Someone"

    body = (
        f"🔥 *New lead!*\n\n"
        f"{who} just came in via {source}."
        f"{chr(10) + 'Phone: ' + lead.phone if lead.phone else ''}\n\n"
        f"Reply LEADS to see everyone waiting."
    )
    queue_owner_alert(lead.user, body)
