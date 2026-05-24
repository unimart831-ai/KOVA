"""
WhatsApp reply-to-act for Daily Brief owners.

Owners reply to Kova's morning brief ping (master WhatsApp number) with
short commands — no LLM required.

Commands:
  help          — list commands
  score         — Kova score + delta
  brief         — today's headline + your move
  approve       — approve first pending post
  approve all   — approve all pending posts
  approve 2     — approve post #2 in queue
  idea 1        — queue content idea #1 as a seed
  posts         — pending approval count
"""

from __future__ import annotations

import logging
import re

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "Kova Daily Brief commands:\n"
    "• SCORE — your Kova score\n"
    "• BRIEF — today's summary\n"
    "• POSTS — pending approvals\n"
    "• APPROVE — approve next post\n"
    "• APPROVE ALL — approve all pending\n"
    "• APPROVE 2 — approve post #2\n"
    "• IDEA 1 — queue idea #1 for creation\n"
    "• HELP — this list"
)


def handle_owner_brief_command(msg_data: dict, contacts: dict | None = None) -> bool:
    """Process an inbound message on Kova's master WhatsApp number.

    Returns True when the sender matches a Kova user (handled or not).
    """
    wa_id = msg_data.get("from", "")
    if not wa_id:
        return False

    msg_type = msg_data.get("type", "text")
    if msg_type not in ("text", "interactive"):
        return False

    text = _extract_command_text(msg_data, msg_type)
    if not text:
        return False

    user = find_user_by_whatsapp_id(wa_id)
    if not user:
        return False

    from apps.billing.models import get_user_plan_limits

    limits = get_user_plan_limits(user)
    if not limits.get("whatsapp_brief") or not getattr(user, "brief_whatsapp_enabled", True):
        _send_owner_reply(
            wa_id,
            "WhatsApp brief commands need Biashara (Pro). Upgrade at "
            f"{getattr(settings, 'SITE_URL', '').rstrip('/')}/billing/",
            send_buttons=False,
        )
        _log_command(user, wa_id, text, "plan_blocked", success=False)
        return True

    response, command_key, success, metadata = _dispatch_command(user, text)
    _send_owner_reply(wa_id, response, user=user, brief=_get_today_brief(user))
    _log_command(user, wa_id, text, command_key, response, success=success, metadata=metadata)
    return True


def find_user_by_whatsapp_id(wa_id: str):
    from django.contrib.auth import get_user_model

    from apps.accounts.phone_utils import phone_to_whatsapp_digits

    User = get_user_model()
    for user in User.objects.filter(is_active=True).exclude(phone_number=""):
        if phone_to_whatsapp_digits(user.phone_number) == wa_id:
            return user
    return None


def _extract_command_text(msg_data: dict, msg_type: str) -> str:
    from apps.briefs.whatsapp_buttons import map_button_inbound

    if msg_type == "text":
        return (msg_data.get("text", {}).get("body", "") or "").strip()
    if msg_type == "interactive":
        interactive = msg_data.get("interactive", {})
        inter_type = interactive.get("type", "")
        if inter_type == "button_reply":
            reply = interactive.get("button_reply", {})
            mapped = map_button_inbound(
                reply.get("id", ""),
                reply.get("title", ""),
            )
            return mapped
        if inter_type == "list_reply":
            row_id = interactive.get("list_reply", {}).get("id", "")
            title = interactive.get("list_reply", {}).get("title", "")
            mapped = map_button_inbound(row_id, title)
            return mapped or title
    return ""


def _normalize_command(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _get_today_brief(user):
    from apps.briefs.models import DailyBrief

    return DailyBrief.objects.filter(user=user, date=timezone.localdate()).first()


def _dispatch_command(user, raw_text: str) -> tuple[str, str, bool, dict]:
    text = _normalize_command(raw_text)
    metadata: dict = {}

    if text in {"help", "commands", "?", "menu"}:
        return HELP_TEXT, "help", True, metadata

    if text in {"score", "kova", "kova score"}:
        brief = _get_today_brief(user)
        if not brief:
            return "No brief yet today — check back after your brief time.", "score", True, metadata
        delta = brief.kova_score_delta or 0
        delta_txt = f" ({'+' if delta > 0 else ''}{delta})" if delta else ""
        return (
            f"Kova Score: {brief.kova_score or 0}/100{delta_txt}. "
            f"{brief.posts_pending or 0} post(s) waiting for approval.",
            "score",
            True,
            {"kova_score": brief.kova_score},
        )

    if text in {"brief", "status", "today"}:
        brief = _get_today_brief(user)
        if not brief:
            return "Your brief isn't ready yet today.", "brief", True, metadata
        from apps.briefs.delivery import build_mobile_digest

        digest = build_mobile_digest(brief)
        move = digest.get("your_move") or "Open the app for your full brief."
        site = getattr(settings, "SITE_URL", "").rstrip("/")
        return (
            f"{digest.get('headline', 'Your brief is ready')}\n\n"
            f"Your move: {move}\n\n"
            f"Full brief: {site}/brief/",
            "brief",
            True,
            metadata,
        )

    if text in {"posts", "pending", "queue"}:
        from apps.content.approval import get_pending_posts

        pending = get_pending_posts(user, limit=10)
        if not pending:
            return "No posts waiting for approval. You're clear!", "posts", True, metadata
        lines = [f"{i + 1}. {(p.content_text or '')[:50].strip()}…" for i, p in enumerate(pending[:5])]
        extra = f"\n+{len(pending) - 5} more" if len(pending) > 5 else ""
        return (
            f"{len(pending)} post(s) waiting:\n" + "\n".join(lines) + extra
            + "\n\nReply APPROVE or APPROVE 1 to schedule.",
            "posts",
            True,
            {"pending_count": len(pending)},
        )

    if text.startswith("approve"):
        return _handle_approve(user, text)

    if text.startswith("idea"):
        return _handle_idea(user, text)

    return (
        f"Didn't recognize \"{raw_text[:40]}\".\n\n{HELP_TEXT}",
        "unknown",
        False,
        metadata,
    )


def _handle_approve(user, text: str) -> tuple[str, str, bool, dict]:
    from apps.content.approval import approve_pending_posts, get_pending_posts

    pending = get_pending_posts(user)
    if not pending:
        return "Nothing to approve — no pending posts.", "approve", True, {}

    parts = text.split()
    if len(parts) == 1 or parts[1] == "all":
        result = approve_pending_posts(user, indices=None)
        command_key = "approve_all"
    elif len(parts) >= 2 and parts[1].isdigit():
        result = approve_pending_posts(user, indices=[int(parts[1])])
        command_key = f"approve_{parts[1]}"
    else:
        result = approve_pending_posts(user, indices=[1])
        command_key = "approve"

    approved = result["approved"]
    skipped = result["skipped"]
    if approved == 0:
        msg = "Couldn't approve — posts may need images first."
        if result["errors"]:
            msg += " " + result["errors"][0]
        return msg, command_key, False, result

    if approved == 1 and result["posts"]:
        p = result["posts"][0]
        plat = p.get("platform") or "social"
        return (
            f"Approved 1 post for {plat}. "
            f"\"{p.get('preview', 'Scheduled')}\" — queued for publishing.",
            command_key,
            True,
            result,
        )

    return (
        f"Approved {approved} post(s)."
        + (f" Skipped {skipped} (need media or invalid)." if skipped else ""),
        command_key,
        True,
        result,
    )


def _handle_idea(user, text: str) -> tuple[str, str, bool, dict]:
    from apps.briefs.actions import create_seed_from_brief_idea

    brief = _get_today_brief(user)
    if not brief:
        return "No brief today — can't queue an idea yet.", "idea", False, {}

    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return "Try IDEA 1 or IDEA 2 (number matches the list in your brief).", "idea", False, {}

    idx = int(parts[1]) - 1
    ideas = brief.suggested_posts or []
    if idx < 0 or idx >= len(ideas):
        return f"Only {len(ideas)} idea(s) in today's brief. Check the app.", "idea", False, {}

    item = ideas[idx]
    if isinstance(item, str):
        idea = item
        platform_hint = ""
        context = ""
    else:
        idea = item.get("idea") or item.get("title") or ""
        platform_hint = item.get("platform") or ""
        context = item.get("reasoning") or item.get("description") or ""

    if not idea:
        return "That idea slot is empty in today's brief.", "idea", False, {}

    seed = create_seed_from_brief_idea(
        user,
        idea,
        context=context,
        platform_hint=platform_hint,
        action_type="whatsapp",
    )
    site = getattr(settings, "SITE_URL", "").rstrip("/")
    return (
        f"Queued idea #{idx + 1} for creation:\n\"{idea[:120]}\"\n\n"
        f"Open Studio: {site}/content/studio/",
        f"idea_{idx + 1}",
        True,
        {"seed_id": str(seed.id)},
    )


def _send_owner_reply(wa_id: str, body: str, *, user=None, brief=None, send_buttons: bool = True) -> bool:
    token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "") or ""
    phone_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "") or ""
    if not (token and phone_id):
        logger.debug("Owner WA reply skipped — master creds missing")
        return False

    from apps.platforms.providers.whatsapp import WhatsAppProvider

    provider = WhatsAppProvider()
    sent = False

    if body:
        result = provider.send_text_message(
            access_token=token,
            to=wa_id,
            body=body[:4096],
            phone_number_id=phone_id,
        )
        if not result.get("success"):
            logger.warning("Owner WA reply failed for %s: %s", wa_id, result.get("error"))
        sent = bool(result.get("success"))

    if send_buttons and user is not None:
        sent = _send_owner_action_buttons(wa_id, user, brief=brief) or sent

    return sent


def _send_owner_action_buttons(wa_id: str, user, *, brief=None) -> bool:
    """Send up to 3 quick-action buttons (works inside 24h customer service window)."""
    from apps.briefs.whatsapp_buttons import action_buttons_for_user
    from apps.platforms.providers.whatsapp import WhatsAppProvider

    token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "") or ""
    phone_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "") or ""
    if not (token and phone_id):
        return False

    pending = brief.posts_pending if brief else 0
    buttons = action_buttons_for_user(user, posts_pending=pending)
    provider = WhatsAppProvider()
    result = provider.send_interactive_buttons(
        access_token=token,
        to=wa_id,
        body="Quick actions:",
        buttons=buttons,
        footer="Or type HELP for all commands",
        phone_number_id=phone_id,
    )
    if not result.get("success"):
        logger.debug("Action buttons not sent for %s: %s", wa_id, result.get("error"))
        return False
    return True


def _log_command(user, wa_id, inbound, command_key, response="", *, success=True, metadata=None):
    try:
        from apps.briefs.models import BriefWhatsAppLog, DailyBrief

        brief = DailyBrief.objects.filter(user=user, date=timezone.localdate()).first()
        BriefWhatsAppLog.objects.create(
            user=user,
            brief=brief,
            wa_id=wa_id,
            inbound_text=(inbound or "")[:500],
            command=command_key[:64],
            response_text=(response or "")[:1000],
            success=success,
            metadata=metadata or {},
        )
    except Exception:
        logger.exception("Failed to log brief WhatsApp command for %s", user.email)
