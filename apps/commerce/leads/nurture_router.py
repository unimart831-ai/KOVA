"""
Unified Nurture Router — selects the optimal communication channel per lead.

Instead of blasting all channels, picks the ONE channel where this lead
is most likely to engage, based on their history:

- High WhatsApp engagement → nurture via WhatsApp
- High email engagement → nurture via email
- No engagement data → default to WhatsApp (Africa's #1)
- High social engagement → retarget via social content

Also handles cross-channel sequences where steps can be on different channels.
"""
from __future__ import annotations

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


class NurtureChannel:
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    SMS = "sms"
    SOCIAL = "social"


class ChannelPreference:
    """Computed channel preference for a lead."""
    def __init__(self, primary: str, secondary: str, scores: dict):
        self.primary = primary
        self.secondary = secondary
        self.scores = scores

    def __repr__(self):
        return f"ChannelPreference(primary={self.primary}, scores={self.scores})"


def detect_channel_preference(lead) -> ChannelPreference:
    """
    Analyze a lead's activity history to determine their preferred channel.
    Returns ChannelPreference with primary and secondary channels.
    """
    from apps.commerce.leads.models import LeadActivity

    scores = {
        NurtureChannel.WHATSAPP: 0,
        NurtureChannel.EMAIL: 0,
        NurtureChannel.SOCIAL: 0,
    }

    activities = lead.activities.all()[:50]

    for activity in activities:
        atype = activity.activity_type

        if atype == LeadActivity.ActivityType.WHATSAPP_SENT:
            scores[NurtureChannel.WHATSAPP] += 5
        elif atype in (LeadActivity.ActivityType.EMAIL_OPENED, LeadActivity.ActivityType.EMAIL_CLICKED):
            scores[NurtureChannel.EMAIL] += 4
        elif atype == LeadActivity.ActivityType.EMAIL_SENT:
            scores[NurtureChannel.EMAIL] += 1
        elif atype == LeadActivity.ActivityType.SOCIAL_INTERACTION:
            scores[NurtureChannel.SOCIAL] += 3
        elif atype == LeadActivity.ActivityType.COMMERCE_PURCHASE:
            meta = activity.metadata or {}
            if meta.get("phone"):
                scores[NurtureChannel.WHATSAPP] += 3

    # Source platform bonuses
    if lead.source_platform == "whatsapp":
        scores[NurtureChannel.WHATSAPP] += 10
    elif lead.source_platform in ("instagram", "facebook", "twitter", "linkedin", "tiktok"):
        scores[NurtureChannel.SOCIAL] += 5

    if lead.email and "@kova.page" not in lead.email:
        scores[NurtureChannel.EMAIL] += 3

    if lead.phone and lead.phone.strip():
        scores[NurtureChannel.WHATSAPP] += 3

    # Default: WhatsApp wins in Africa if no clear signal
    if all(v == 0 for v in scores.values()):
        if lead.phone:
            scores[NurtureChannel.WHATSAPP] = 5
        elif lead.email and "@kova.page" not in lead.email:
            scores[NurtureChannel.EMAIL] = 5
        else:
            scores[NurtureChannel.SOCIAL] = 3

    sorted_channels = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary = sorted_channels[0][0]
    secondary = sorted_channels[1][0] if len(sorted_channels) > 1 else primary

    return ChannelPreference(primary=primary, secondary=secondary, scores=scores)


def route_nurture_step(
    lead,
    step_content: str,
    subject: str = "",
    *,
    preferred_channel: str | None = None,
) -> dict:
    """
    Route a nurture message to the best channel for this lead.

    Returns:
        {
            "channel": "whatsapp" | "email" | "social",
            "sent": bool,
            "details": {...}
        }
    """
    preference = detect_channel_preference(lead)
    primary = preference.primary
    secondary = preference.secondary

    if preferred_channel == NurtureChannel.WHATSAPP and lead.phone:
        primary = NurtureChannel.WHATSAPP
        secondary = NurtureChannel.EMAIL if lead.email and "@kova.page" not in lead.email else primary
    elif preferred_channel == NurtureChannel.EMAIL:
        primary = NurtureChannel.EMAIL
        secondary = NurtureChannel.WHATSAPP if lead.phone else primary

    if primary == NurtureChannel.WHATSAPP:
        result = _send_via_whatsapp(lead, step_content)
    elif primary == NurtureChannel.EMAIL:
        result = _send_via_email(lead, step_content, subject)
    else:
        result = _queue_social_retarget(lead, step_content)

    # If primary fails, try secondary
    if not result.get("sent") and secondary != primary:
        if secondary == NurtureChannel.WHATSAPP:
            result = _send_via_whatsapp(lead, step_content)
        elif secondary == NurtureChannel.EMAIL:
            result = _send_via_email(lead, step_content, subject)

    result["channel"] = primary
    result["preference"] = preference.scores
    return result


def _send_via_whatsapp(lead, content: str) -> dict:
    """Send nurture message via WhatsApp."""
    phone = lead.phone
    if not phone:
        return {"sent": False, "reason": "no_phone"}

    try:
        from apps.messaging.whatsapp.services import send_text_message
        send_text_message(to=phone, body=content, user=lead.user)

        from apps.commerce.leads.models import LeadActivity
        LeadActivity.objects.create(
            lead=lead,
            activity_type=LeadActivity.ActivityType.WHATSAPP_SENT,
            description=f"Nurture: {content[:80]}",
            metadata={"channel": "whatsapp", "routed": True},
        )
        return {"sent": True, "channel": "whatsapp"}
    except Exception as e:
        logger.debug("WhatsApp nurture send failed for lead %s: %s", lead.pk, e)
        return {"sent": False, "reason": str(e)}


def _send_via_email(lead, content: str, subject: str = "") -> dict:
    """Send nurture message via email using the shared email service."""
    email = lead.email
    if not email or "@kova.page" in email:
        return {"sent": False, "reason": "no_real_email"}

    try:
        from apps.messaging.emails.services import email_service

        profile = getattr(lead.user, "profile", None)
        business_name = getattr(profile, "company_name", "") if profile else ""

        email_service._send(
            email_type="lead_nurture",
            to_email=email,
            context={
                "lead_name": lead.name or email.split("@")[0],
                "business_name": business_name,
                "email_body": content,
            },
            user=lead.user,
            subject=subject or "We have something for you",
        )

        from apps.commerce.leads.models import LeadActivity
        LeadActivity.objects.create(
            lead=lead,
            activity_type=LeadActivity.ActivityType.EMAIL_SENT,
            description=f"Nurture email: {subject or content[:60]}",
            metadata={"channel": "email", "routed": True, "subject": subject},
        )
        return {"sent": True, "channel": "email"}
    except Exception as e:
        logger.debug("Email nurture send failed for lead %s: %s", lead.pk, e)
        return {"sent": False, "reason": str(e)}


def _queue_social_retarget(lead, content: str) -> dict:
    """
    Queue a social retargeting action (create content aimed at this lead's interest).
    This is a soft-touch — we can't DM them, but we can create content they'd engage with.
    """
    try:
        metadata = lead.metadata or {}
        metadata["retarget_queued"] = timezone.now().isoformat()
        metadata["retarget_reason"] = content[:200]
        lead.metadata = metadata
        lead.save(update_fields=["metadata"])

        from apps.commerce.leads.models import LeadActivity
        LeadActivity.objects.create(
            lead=lead,
            activity_type=LeadActivity.ActivityType.SOCIAL_INTERACTION,
            description=f"Retarget queued: {content[:60]}",
            metadata={"channel": "social", "routed": True, "action": "retarget"},
        )
        return {"sent": True, "channel": "social", "action": "retarget_queued"}
    except Exception:
        return {"sent": False, "reason": "retarget_failed"}
