"""AI reply draft actions — web inbox, owner WhatsApp commands, notifications."""

from __future__ import annotations

import logging

from django.urls import reverse
from django.utils import timezone

from apps.core.platforms.providers.registry import get_provider
from apps.messaging.whatsapp.models import WhatsAppConversation, WhatsAppMessage

logger = logging.getLogger(__name__)


def pending_ai_drafts_qs(user):
    """Outbound AI drafts awaiting owner approval."""
    from apps.core.platforms.models import SocialAccount

    wa_accounts = SocialAccount.objects.filter(
        user=user, platform="whatsapp", is_active=True,
    )
    return WhatsAppMessage.objects.filter(
        conversation__social_account__in=wa_accounts,
        direction=WhatsAppMessage.Direction.OUTBOUND,
        status=WhatsAppMessage.MessageStatus.PENDING,
        is_ai_generated=True,
    ).select_related("conversation", "conversation__social_account").order_by("-created_at")


def pending_draft_count(user) -> int:
    return pending_ai_drafts_qs(user).count()


def list_pending_drafts(user, *, limit: int = 5) -> list[WhatsAppMessage]:
    return list(pending_ai_drafts_qs(user)[:limit])


def format_drafts_whatsapp_summary(user, *, limit: int = 3) -> str:
    drafts = list_pending_drafts(user, limit=limit)
    if not drafts:
        return "No AI reply drafts waiting — inbox is clear."

    lines = [f"{len(drafts)} AI draft{'s' if len(drafts) != 1 else ''} need your OK:"]
    for idx, draft in enumerate(drafts, start=1):
        convo = draft.conversation
        who = convo.contact_name or convo.contact_wa_id or "Customer"
        preview = (draft.content or "").replace("\n", " ")[:100]
        lines.append(f"{idx}. {who}: \"{preview}\"")
    lines.append("\nReply APPROVE REPLY or APPROVE REPLY 2 to send. REJECT REPLY to discard.")
    site = __import__("django.conf", fromlist=["settings"]).settings.SITE_URL.rstrip("/")
    lines.append(f"Inbox: {site}/whatsapp/inbox/")
    return "\n".join(lines)


def _resolve_draft(user, index: int = 1) -> WhatsAppMessage | None:
    drafts = list_pending_drafts(user, limit=max(index, 1))
    if index < 1 or index > len(drafts):
        return None
    return drafts[index - 1]


def send_draft_message(draft: WhatsAppMessage, *, edited_text: str = "") -> tuple[bool, str]:
    """Approve and send a pending AI draft. Returns (success, error_message)."""
    conversation = draft.conversation
    if draft.status != WhatsAppMessage.MessageStatus.PENDING:
        return False, "Draft already handled."

    if not conversation.is_window_open:
        return False, "24-hour reply window expired — open the inbox to use a template."

    message_text = (edited_text or draft.content or "").strip()
    if not message_text:
        return False, "Draft is empty."

    provider = get_provider("whatsapp")
    if not provider:
        return False, "WhatsApp provider unavailable."

    result = provider.send_text_message(
        access_token=conversation.social_account.access_token,
        to=conversation.contact_wa_id,
        body=message_text,
    )
    if not result.get("success"):
        return False, (result.get("error") or "Send failed")[:200]

    if edited_text:
        draft.content = message_text
    draft.wamid = result.get("wamid", "")
    draft.status = WhatsAppMessage.MessageStatus.SENT
    draft.save(update_fields=["content", "wamid", "status"])

    conversation.last_message_at = timezone.now()
    conversation.save(update_fields=["last_message_at", "updated_at"])
    _increment_analytics(conversation, approved=True)
    return True, ""


def approve_draft(user, *, index: int = 1) -> tuple[bool, str, WhatsAppMessage | None]:
    draft = _resolve_draft(user, index)
    if not draft:
        return False, "No draft at that position.", None
    ok, err = send_draft_message(draft)
    if not ok:
        return False, err, draft
    who = draft.conversation.contact_name or "customer"
    return True, f"Sent AI reply to {who}.", draft


def reject_draft(user, *, index: int = 1) -> tuple[bool, str]:
    draft = _resolve_draft(user, index)
    if not draft:
        return False, "No draft at that position."
    draft.status = WhatsAppMessage.MessageStatus.FAILED
    draft.error_message = "Rejected by owner"
    draft.save(update_fields=["status", "error_message"])
    _increment_analytics(draft.conversation, approved=False)
    return True, "Draft discarded."


def notify_owner_draft_created(draft: WhatsAppMessage) -> None:
    """In-app + optional owner WhatsApp ping when AI saves a medium-confidence draft."""
    user = draft.conversation.social_account.user
    convo = draft.conversation
    who = convo.contact_name or convo.contact_wa_id or "A customer"
    preview = (draft.content or "").replace("\n", " ")[:120]

    try:
        from apps.messaging.notifications.models import Notification

        Notification.objects.create(
            user=user,
            title="WhatsApp: AI draft ready",
            message=f"{who}: \"{preview}\" — approve or edit before sending.",
            notification_type="whatsapp_draft",
            link=reverse("whatsapp:conversation", kwargs={"pk": convo.pk}),
        )
    except Exception as exc:
        logger.warning("Draft notification failed: %s", exc)


def _increment_analytics(conversation, *, approved: bool) -> None:
    try:
        from apps.messaging.whatsapp.models import WhatsAppAnalytics

        today = timezone.now().date()
        analytics, _ = WhatsAppAnalytics.objects.get_or_create(
            user=conversation.social_account.user,
            period_date=today,
        )
        field = "ai_drafts_approved" if approved else "ai_drafts_rejected"
        current = int(getattr(analytics, field, 0) or 0)
        setattr(analytics, field, current + 1)
        analytics.save(update_fields=[field, "updated_at"])
    except Exception:
        pass
