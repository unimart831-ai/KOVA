"""
Daily Brief multi-channel delivery — email, WhatsApp, and real-time push.

Called once after DailyBrief.objects.create() from generate_daily_brief().
"""

from __future__ import annotations

import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)

WHATSAPP_BODY_MAX = 200
HEADLINE_MAX = 80


def extract_your_move(summary: str) -> str:
    """Pull the actionable 'Your move today' paragraph from the brief summary."""
    if not summary:
        return ""
    for paragraph in summary.split("\n\n"):
        stripped = paragraph.strip()
        if stripped.lower().startswith("your move"):
            return stripped
    parts = [p.strip() for p in summary.split("\n\n") if p.strip()]
    return parts[-1] if len(parts) >= 3 else ""


def _truncate(text: str, max_len: int) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def build_mobile_digest(brief, llm_digest: dict | None = None) -> dict:
    """Build channel-native digest for WhatsApp / push notifications.

    Uses LLM output when present; falls back to structured brief fields.
    """
    llm_digest = llm_digest or (brief.performance_summary or {}).get("mobile_digest") or {}
    your_move = extract_your_move(brief.summary)
    if your_move.lower().startswith("your move today:"):
        your_move = your_move.split(":", 1)[-1].strip()

    pending = brief.posts_pending or 0
    score = brief.kova_score or 0
    delta = brief.kova_score_delta or 0
    delta_str = f"+{delta}" if delta > 0 else str(delta) if delta else ""

    decisions = (brief.performance_summary or {}).get("decisions_needed") or []
    urgent = sum(
        1 for d in decisions
        if isinstance(d, dict) and d.get("urgency") == "now"
    )

    fallback_headline_parts = []
    if pending:
        fallback_headline_parts.append(f"{pending} post{'s' if pending != 1 else ''} waiting")
    if urgent:
        fallback_headline_parts.append(f"{urgent} need{'s' if urgent == 1 else ''} you now")
    if delta_str:
        fallback_headline_parts.append(f"Score {score} ({delta_str})")
    elif score:
        fallback_headline_parts.append(f"Score {score}/100")

    fallback_headline = " · ".join(fallback_headline_parts) or "Your daily brief is ready"

    site_url = getattr(settings, "SITE_URL", "https://kovaagent.com").rstrip("/")
    brief_url = f"{site_url}/brief/?utm_source=whatsapp"

    fallback_wa = _truncate(
        f"{fallback_headline}. "
        + (your_move or "Open your brief for today's plan.")
        + f" {brief_url}",
        WHATSAPP_BODY_MAX,
    )

    headline = _truncate(llm_digest.get("headline") or fallback_headline, HEADLINE_MAX)
    whatsapp_body = _truncate(llm_digest.get("whatsapp_body") or fallback_wa, WHATSAPP_BODY_MAX)

    return {
        "headline": headline,
        "whatsapp_body": whatsapp_body,
        "your_move": your_move,
        "brief_url": brief_url,
        "score_line": f"{score}/100" + (f" ({delta_str})" if delta_str else ""),
    }


def deliver_daily_brief(user, brief) -> dict:
    """Deliver the brief across enabled channels. Returns delivery summary."""
    from apps.billing.models import get_user_plan_limits

    limits = get_user_plan_limits(user)
    digest = build_mobile_digest(brief)
    results = {"email": False, "whatsapp": False, "websocket": False}

    try:
        results["websocket"] = _notify_brief_ready(user, brief, digest)
    except Exception:
        logger.exception("brief_ready websocket failed for %s", user.email)

    if limits.get("email_brief") and getattr(user, "brief_email_enabled", True):
        try:
            results["email"] = _send_brief_email(user, brief, digest)
        except Exception:
            logger.exception("Email brief failed for %s", user.email)

    if limits.get("whatsapp_brief") and getattr(user, "brief_whatsapp_enabled", True):
        try:
            results["whatsapp"] = _send_brief_whatsapp(user, brief, digest)
        except Exception:
            logger.exception("WhatsApp brief failed for %s", user.email)

    logger.info(
        "Brief delivery for %s: email=%s whatsapp=%s ws=%s",
        user.email, results["email"], results["whatsapp"], results["websocket"],
    )
    return results


def _notify_brief_ready(user, brief, digest: dict) -> bool:
    from apps.notifications.realtime import send_user_event

    decisions = (brief.performance_summary or {}).get("decisions_needed") or []
    send_user_event(
        user.pk,
        "brief_ready",
        {
            "type": "brief_ready",
            "brief_date": str(brief.date),
            "kova_score": brief.kova_score,
            "kova_score_delta": brief.kova_score_delta,
            "headline": digest.get("headline", ""),
            "decisions_count": len(decisions),
            "posts_pending": brief.posts_pending,
            "brief_url": digest.get("brief_url", ""),
        },
    )
    return True


def _send_brief_email(user, brief, digest: dict) -> bool:
    from apps.emails.services import email_service

    decisions = (brief.performance_summary or {}).get("decisions_needed") or []
    site_url = getattr(settings, "SITE_URL", "https://kovaagent.com").rstrip("/")

    email_service.send_daily_brief(
        user,
        brief=brief,
        your_move=digest.get("your_move", ""),
        top_decisions=decisions[:3],
        brief_url=f"{site_url}/brief/?utm_source=email",
        approve_url=f"{site_url}/content/studio/?utm_source=email",
    )
    return True


def _send_brief_whatsapp(user, brief, digest: dict) -> bool:
    template_name = getattr(settings, "KOVA_DAILY_BRIEF_TEMPLATE_NAME", "") or ""
    if not template_name:
        logger.debug("Daily brief WA: KOVA_DAILY_BRIEF_TEMPLATE_NAME not set — skipping")
        return False

    phone_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "") or ""
    token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "") or ""
    if not (phone_id and token):
        logger.debug("Daily brief WA: master WhatsApp creds missing — skipping")
        return False

    from apps.accounts.phone_utils import phone_to_whatsapp_digits

    raw_phone = (getattr(user, "phone_number", "") or "").strip()
    to_number = phone_to_whatsapp_digits(raw_phone)
    if not to_number:
        logger.debug("Daily brief WA: user %s has no valid phone — skipping", user.email)
        return False

    from apps.utils.greetings import greeting_name

    first_name = greeting_name(user)
    summary_snippet = _truncate(digest.get("whatsapp_body") or digest.get("headline", ""), 160)
    score_line = digest.get("score_line") or f"{brief.kova_score or 0}/100"

    from apps.briefs.whatsapp_buttons import build_daily_brief_template_components

    components = build_daily_brief_template_components(
        first_name, summary_snippet, score_line,
    )

    from apps.platforms.providers.whatsapp import WhatsAppProvider

    provider = WhatsAppProvider()
    result = provider.send_template_message(
        access_token=token,
        to=to_number,
        template_name=template_name,
        language_code=getattr(settings, "KOVA_DAILY_BRIEF_TEMPLATE_LANG", "en"),
        components=components,
        phone_number_id=phone_id,
    )
    if result.get("success"):
        logger.info("Daily brief WhatsApp sent to %s (%s)", user.email, to_number)
        _record_whatsapp_delivery(user, brief, result, to_number)
        return True
    logger.warning("Daily brief WA failed for %s: %s", user.email, result.get("error"))
    return False


def _record_whatsapp_delivery(user, brief, result: dict, to_number: str) -> None:
    """Persist delivery metadata + reply-to-act hint on the brief."""
    from django.utils import timezone

    ps = dict(brief.performance_summary or {})
    ps["last_whatsapp_delivery"] = {
        "sent_at": timezone.now().isoformat(),
        "to": to_number,
        "wamid": result.get("wamid", ""),
        "reply_commands": "Tap Approve · Score · Open brief",
        "template_buttons": ["url:Open brief", "qr:Approve", "qr:Score"],
    }
    brief.performance_summary = ps
    brief.save(update_fields=["performance_summary"])
