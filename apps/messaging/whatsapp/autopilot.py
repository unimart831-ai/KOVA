"""
WhatsApp Operations Autopilot — FAQ auto-replies and 24h follow-up nudges.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.core.accounts.autopilot_helpers import (
    DEFAULT_WA_FOLLOWUP_MESSAGE,
    FAQ_DAILY_CAP,
    FAQ_OWNER_QUIET_MINUTES,
    FOLLOWUP_NUDGE_COOLDOWN_DAYS,
    match_faq_reply,
    normalize_faq_answers,
    whatsapp_autopilot_allowed,
)

logger = logging.getLogger(__name__)


def _owner_replied_recently(conversation) -> bool:
    from apps.messaging.whatsapp.models import WhatsAppMessage

    cutoff = timezone.now() - timedelta(minutes=FAQ_OWNER_QUIET_MINUTES)
    return WhatsAppMessage.objects.filter(
        conversation=conversation,
        direction=WhatsAppMessage.Direction.OUTBOUND,
        created_at__gte=cutoff,
        is_ai_generated=False,
    ).exists()


def _faq_count_today(conversation) -> int:
    ctx = conversation.context or {}
    stats = ctx.get("faq_auto_stats") or {}
    today = timezone.now().date().isoformat()
    if stats.get("date") != today:
        return 0
    return int(stats.get("count") or 0)


def _record_faq_auto_reply(conversation) -> None:
    ctx = conversation.context or {}
    today = timezone.now().date().isoformat()
    stats = ctx.get("faq_auto_stats") or {}
    if stats.get("date") != today:
        stats = {"date": today, "count": 0}
    stats["count"] = int(stats.get("count") or 0) + 1
    ctx["faq_auto_stats"] = stats
    conversation.context = ctx
    conversation.save(update_fields=["context", "updated_at"])


def try_faq_auto_reply(conversation, inbound_message) -> bool:
    """
    Send an FAQ auto-reply if profile toggle is on and rules match.
    Returns True if a reply was sent.
    """
    from apps.messaging.whatsapp.models import WhatsAppMessage

    user = conversation.social_account.user
    profile = getattr(user, "profile", None)
    if not profile or not profile.autopilot_wa_faq_replies:
        return False
    if profile.emergency_pause:
        return False
    if not whatsapp_autopilot_allowed(user):
        return False
    if inbound_message.message_type != WhatsAppMessage.MessageType.TEXT:
        return False
    if _owner_replied_recently(conversation):
        return False
    if _faq_count_today(conversation) >= FAQ_DAILY_CAP:
        return False

    faq_answers = normalize_faq_answers(profile.wa_faq_answers)
    reply = match_faq_reply(inbound_message.content, faq_answers)
    if not reply:
        return False

    try:
        from apps.messaging.whatsapp.services import send_text_message

        send_text_message(
            to=conversation.contact_wa_id,
            body=reply,
            social_account=conversation.social_account,
            is_ai_generated=True,
            confidence_score=1.0,
        )
        _record_faq_auto_reply(conversation)
        logger.info(
            "FAQ auto-reply sent for conversation %s (user %s)",
            conversation.pk,
            user.email,
        )
        return True
    except Exception as exc:
        logger.warning("FAQ auto-reply failed for conversation %s: %s", conversation.pk, exc)
        return False


def _last_followup_nudge_at(conversation):
    ctx = conversation.context or {}
    raw = ctx.get("last_followup_nudge_at")
    if not raw:
        return None
    try:
        return timezone.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _record_followup_nudge(conversation) -> None:
    ctx = conversation.context or {}
    ctx["last_followup_nudge_at"] = timezone.now().isoformat()
    conversation.context = ctx
    conversation.save(update_fields=["context", "updated_at"])


def _conversation_needs_followup(conversation, *, now, cutoff_24h):
    from apps.messaging.whatsapp.models import WhatsAppMessage

    last_msg = (
        WhatsAppMessage.objects.filter(conversation=conversation)
        .order_by("-created_at")
        .first()
    )
    if not last_msg or last_msg.direction != WhatsAppMessage.Direction.INBOUND:
        return False
    if last_msg.created_at > cutoff_24h:
        return False

    has_recent_outbound = WhatsAppMessage.objects.filter(
        conversation=conversation,
        direction=WhatsAppMessage.Direction.OUTBOUND,
        created_at__gte=cutoff_24h,
    ).exists()
    if has_recent_outbound:
        return False

    last_nudge = _last_followup_nudge_at(conversation)
    if last_nudge and (now - last_nudge) < timedelta(days=FOLLOWUP_NUDGE_COOLDOWN_DAYS):
        return False

    return True


@shared_task(name="whatsapp.send_followup_nudges", soft_time_limit=10 * 60, time_limit=12 * 60)
def send_followup_nudges():
    """
    Hourly: nudge conversations where the customer wrote last and no reply in 24h.
    Respects 24h service window (session message only); skips if window closed.
    """
    from apps.core.accounts.models import UserProfile
    from apps.messaging.whatsapp.models import WhatsAppConversation, WhatsAppMessage

    now = timezone.now()

    cutoff_24h = now - timedelta(hours=24)

    profiles = UserProfile.objects.filter(
        autopilot_wa_followup_24h=True,
        emergency_pause=False,
    ).select_related("user")

    sent = 0
    skipped = 0

    for profile in profiles:
        if not whatsapp_autopilot_allowed(profile.user):
            continue

        conversations = WhatsAppConversation.objects.filter(
            social_account__user=profile.user,
            social_account__platform="whatsapp",
            social_account__is_active=True,
            status=WhatsAppConversation.Status.ACTIVE,
            last_message_at__lte=cutoff_24h,
        ).select_related("social_account")

        for conversation in conversations:
            if not _conversation_needs_followup(
                conversation, now=now, cutoff_24h=cutoff_24h
            ):
                skipped += 1
                continue

            if not conversation.is_window_open:
                skipped += 1
                continue

            body = DEFAULT_WA_FOLLOWUP_MESSAGE
            try:
                from apps.messaging.whatsapp.services import send_text_message

                send_text_message(
                    to=conversation.contact_wa_id,
                    body=body,
                    social_account=conversation.social_account,
                    is_ai_generated=True,
                    confidence_score=1.0,
                )
                _record_followup_nudge(conversation)
                sent += 1
            except Exception as exc:
                logger.debug(
                    "Follow-up nudge skipped for conversation %s: %s",
                    conversation.pk,
                    exc,
                )
                skipped += 1

    logger.info("WA follow-up nudges: %d sent, %d skipped", sent, skipped)
    return {"sent": sent, "skipped": skipped}
