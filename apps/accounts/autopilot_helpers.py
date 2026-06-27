"""
Operations Autopilot helpers — shared gates for lead nurture, publishing, and WA automations.
All toggles default off; callers check these before autonomous actions.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_WA_FOLLOWUP_MESSAGE = (
    "Hi! Still interested? Reply here and we'll help."
)

MAX_FAQ_ENTRIES = 5
FAQ_DAILY_CAP = 3
FAQ_OWNER_QUIET_MINUTES = 5
FOLLOWUP_NUDGE_COOLDOWN_DAYS = 7


def whatsapp_autopilot_allowed(user) -> bool:
    """Pro+ plans with WhatsApp enabled may use WA autopilot toggles."""
    from apps.billing.models import get_user_plan_limits

    limits = get_user_plan_limits(user)
    from apps.billing.whatsapp_access import whatsapp_inbox_allowed

    return whatsapp_inbox_allowed(limits)


def should_auto_enroll_leads(user) -> bool:
    profile = getattr(user, "profile", None)
    return bool(profile and profile.autopilot_auto_enroll_leads)


def effective_autopilot_platforms(user) -> set[str] | None:
    """Platforms selected for autopilot. None = all connected accounts."""
    profile = getattr(user, "profile", None)
    if not profile:
        return None
    selected = profile.autopilot_platforms or []
    if not selected:
        return None
    return {str(p).lower() for p in selected}


def platform_allowed_for_autopilot(user, platform: str) -> bool:
    allowed = effective_autopilot_platforms(user)
    if allowed is None:
        return True
    return (platform or "").lower() in allowed


def filter_social_accounts_for_autopilot(user, queryset):
    """Limit SocialAccount queryset to autopilot_platforms when configured."""
    allowed = effective_autopilot_platforms(user)
    if allowed is not None:
        queryset = queryset.filter(platform__in=allowed)
    return queryset


def should_auto_publish_approved(user) -> bool:
    profile = getattr(user, "profile", None)
    if not profile:
        return False
    if profile.emergency_pause or profile.auto_publish_paused:
        return False
    from apps.content.safety import is_publishing_paused

    paused, _ = is_publishing_paused(user)
    if paused:
        return False
    return bool(profile.autopilot_auto_publish_approved)


def normalize_faq_answers(raw: Any) -> list[dict]:
    """Validate FAQ list: up to 5 entries with keywords + reply."""
    if not raw:
        return []
    if not isinstance(raw, list):
        return []
    cleaned = []
    for item in raw[:MAX_FAQ_ENTRIES]:
        if not isinstance(item, dict):
            continue
        keywords = item.get("keywords") or []
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]
        elif isinstance(keywords, list):
            keywords = [str(k).strip().lower() for k in keywords if str(k).strip()]
        else:
            keywords = []
        reply = (item.get("reply") or "").strip()
        if keywords and reply:
            cleaned.append({"keywords": keywords, "reply": reply})
    return cleaned


def match_faq_reply(message_text: str, faq_answers: list[dict]) -> str | None:
    """First keyword match wins (case-insensitive)."""
    text = (message_text or "").lower()
    if not text.strip():
        return None
    for entry in faq_answers:
        for keyword in entry.get("keywords") or []:
            kw = (keyword or "").strip().lower()
            if kw and kw in text:
                return entry.get("reply") or None
    return None
