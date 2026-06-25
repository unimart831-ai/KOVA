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
  standup       — full morning standup digest
  morning       — alias for standup
  reject        — reject first pending post
  reject all    — reject all pending posts
  leads         — hot leads + need reply summary
  book          — booking page link + services
  money         — revenue + leads summary this week
  snap          — send a product photo to list + create content
"""

from __future__ import annotations

import logging
import re

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "Kova commands:\n"
    "• Send a product photo to Snap to Sell\n"
    "• STANDUP — morning standup digest\n"
    "• MONEY — revenue + leads this week\n"
    "• SCORE — your Kova score\n"
    "• BRIEF — today's summary\n"
    "• CAMPAIGNS — campaigns ready to approve\n"
    "• APPROVE CAMPAIGN — approve full campaign package\n"
    "• SHARE — campaign + shop links for Status\n"
    "• POSTS — pending approvals (by post)\n"
    "• APPROVE — approve next post\n"
    "• APPROVE ALL — approve all pending posts\n"
    "• REJECT — reject next post\n"
    "• LEADS — hot leads + need reply\n"
    "• BOOK — your booking page + services\n"
    "• REPLIES — AI reply drafts waiting for approval\n"
    "• APPROVE REPLY — send the latest AI draft\n"
    "• REJECT REPLY — discard the latest AI draft\n"
    "• HELP — this list"
)


def handle_owner_whatsapp_message(msg_data: dict, contacts: dict | None = None) -> bool:
    """Process owner messages on Kova's master WhatsApp number."""
    wa_id = msg_data.get("from", "")
    if not wa_id:
        return False

    user = find_user_by_whatsapp_id(wa_id)
    if not user:
        return False

    msg_type = msg_data.get("type", "text")

    if msg_type == "image":
        from apps.products.owner_snap_whatsapp import handle_owner_snap_image

        response, command_key, success, metadata = handle_owner_snap_image(user, msg_data)
        _send_owner_reply(wa_id, response, user=user, brief=_get_today_brief(user))
        _log_command(user, wa_id, "[image]", command_key, response, success=success, metadata=metadata)
        return True

    if msg_type not in ("text", "interactive"):
        return True

    text = _extract_command_text(msg_data, msg_type)
    if not text:
        return True

    from apps.whatsapp.owner_onboarding import try_whatsapp_onboarding

    onboarding_reply = try_whatsapp_onboarding(user, text)
    if onboarding_reply:
        _send_owner_reply(wa_id, onboarding_reply, user=user, brief=_get_today_brief(user))
        _log_command(user, wa_id, text, "wa_onboarding", onboarding_reply, success=True)
        return True

    from apps.products.owner_snap_whatsapp import try_complete_pending_snap

    pending_result = try_complete_pending_snap(user, text)
    if pending_result:
        response, command_key, success, metadata = pending_result
        _send_owner_reply(wa_id, response, user=user, brief=_get_today_brief(user))
        _log_command(user, wa_id, text, command_key, response, success=success, metadata=metadata)
        return True

    return handle_owner_brief_command(msg_data, contacts, _prechecked_user=user)


def handle_owner_brief_command(
    msg_data: dict,
    contacts: dict | None = None,
    *,
    _prechecked_user=None,
) -> bool:
    """Process text/interactive brief commands on Kova's master WhatsApp number."""
    wa_id = msg_data.get("from", "")
    if not wa_id:
        return False

    msg_type = msg_data.get("type", "text")
    if msg_type not in ("text", "interactive"):
        return False

    text = _extract_command_text(msg_data, msg_type)
    if not text:
        return False

    user = _prechecked_user or find_user_by_whatsapp_id(wa_id)
    if not user:
        return False

    from apps.billing.models import get_user_plan_limits

    limits = get_user_plan_limits(user)
    if not limits.get("whatsapp_brief") or not getattr(user, "brief_whatsapp_enabled", True):
        _send_owner_reply(
            wa_id,
            "WhatsApp brief commands require an active Kova subscription. "
            f"Subscribe at {getattr(settings, 'SITE_URL', '').rstrip('/')}/billing/pricing/",
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

    if text in {"standup", "morning", "morning standup"}:
        brief = _get_today_brief(user)
        from apps.briefs.standup import format_standup_whatsapp_message, mark_standup_engaged

        msg = format_standup_whatsapp_message(user, brief)
        if brief:
            mark_standup_engaged(brief)
        return msg, "standup", True, metadata

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

    if text in {"campaigns", "campaign", "my campaigns"}:
        return _handle_campaigns(user)

    if text.startswith("share"):
        return _handle_share(user, text)

    if text.startswith("approve reply"):
        return _handle_approve_reply(user, text)

    if text.startswith("reject reply"):
        return _handle_reject_reply(user, text)

    if text in {"replies", "reply drafts", "drafts"}:
        return _handle_replies(user)

    if text.startswith("approve campaign"):
        return _handle_approve_campaign(user, text)

    if text.startswith("approve"):
        return _handle_approve(user, text)

    if text.startswith("reject"):
        parts = text.split()
        if len(parts) == 1:
            return _handle_reject(user, "reject 1")
        return _handle_reject(user, text)

    if text in {"leads", "inbox", "hot leads"}:
        return _handle_leads(user)

    if text in {"book", "booking", "bookings", "calendar"}:
        return _handle_book(user)

    if text.startswith("idea"):
        return _handle_idea(user, text)

    if text in {"money", "revenue", "sales"}:
        return _handle_money(user)

    return (
        f"Didn't recognize \"{raw_text[:40]}\".\n\n{HELP_TEXT}",
        "unknown",
        False,
        metadata,
    )


def _handle_replies(user) -> tuple[str, str, bool, dict]:
    from apps.whatsapp.draft_actions import format_drafts_whatsapp_summary, pending_draft_count

    count = pending_draft_count(user)
    return (
        format_drafts_whatsapp_summary(user),
        "replies",
        True,
        {"pending_drafts": count},
    )


def _handle_approve_reply(user, text: str) -> tuple[str, str, bool, dict]:
    from apps.whatsapp.draft_actions import approve_draft

    parts = text.split()
    index = 1
    if len(parts) >= 3 and parts[2].isdigit():
        index = int(parts[2])
    ok, message, draft = approve_draft(user, index=index)
    meta = {"draft_id": str(draft.pk)} if draft else {}
    return message, f"approve_reply_{index}", ok, meta


def _handle_reject_reply(user, text: str) -> tuple[str, str, bool, dict]:
    from apps.whatsapp.draft_actions import reject_draft

    parts = text.split()
    index = 1
    if len(parts) >= 3 and parts[2].isdigit():
        index = int(parts[2])
    ok, message = reject_draft(user, index=index)
    return message, f"reject_reply_{index}", ok, {}


def _handle_campaigns(user) -> tuple[str, str, bool, dict]:
    from apps.content.campaign_whatsapp import format_campaigns_list_message

    return format_campaigns_list_message(user), "campaigns", True, {}


def _handle_share(user, text: str) -> tuple[str, str, bool, dict]:
    from apps.content.campaign_whatsapp import format_commerce_share_message

    parts = text.split()
    index = 1
    if len(parts) >= 2 and parts[1].isdigit():
        index = int(parts[1])
    msg, ok, meta = format_commerce_share_message(user, index=index)
    return msg, f"share_{index}", ok, meta


def _handle_approve_campaign(user, text: str) -> tuple[str, str, bool, dict]:
    from apps.content.campaign_whatsapp import approve_campaign_via_whatsapp

    parts = text.split()
    index = 1
    if len(parts) >= 3 and parts[2].isdigit():
        index = int(parts[2])
    elif len(parts) >= 2 and parts[1].isdigit():
        index = int(parts[1])
    msg, ok, meta = approve_campaign_via_whatsapp(user, index=index)
    return msg, f"approve_campaign_{index}", ok, meta


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


def _handle_reject(user, text: str) -> tuple[str, str, bool, dict]:
    from apps.content.approval import get_pending_posts, reject_pending_posts

    pending = get_pending_posts(user)
    if not pending:
        return "Nothing to reject — no pending posts.", "reject", True, {}

    parts = text.split()
    if len(parts) >= 2 and parts[1] == "all":
        result = reject_pending_posts(user, indices=None)
        command_key = "reject_all"
    elif len(parts) >= 2 and parts[1].isdigit():
        result = reject_pending_posts(user, indices=[int(parts[1])])
        command_key = f"reject_{parts[1]}"
    else:
        result = reject_pending_posts(user, indices=[1])
        command_key = "reject"

    rejected = result["rejected"]
    if rejected == 0:
        msg = "Couldn't reject — no matching pending posts."
        if result["errors"]:
            msg += " " + result["errors"][0]
        return msg, command_key, False, result

    if rejected == 1 and result["posts"]:
        p = result["posts"][0]
        return (
            f"Rejected 1 post: \"{p.get('preview', 'Removed')}\".",
            command_key,
            True,
            result,
        )

    return (
        f"Rejected {rejected} post(s).",
        command_key,
        True,
        result,
    )


def _handle_leads(user) -> tuple[str, str, bool, dict]:
    from datetime import timedelta

    from django.utils import timezone

    from apps.briefs.dashboard import get_money_board_stats
    from apps.leads.models import Lead

    stats = get_money_board_stats(user)
    week_ago = timezone.now() - timedelta(days=7)

    recent = list(
        Lead.objects.filter(user=user, first_seen_at__gte=week_ago)
        .order_by("-first_seen_at")[:5]
    )
    hot = list(
        Lead.objects.filter(user=user, temperature=Lead.Temperature.HOT)
        .order_by("-first_seen_at")[:3]
    )

    lines = []
    if hot:
        lines.append("Hot leads:")
        for lead in hot:
            label = lead.name or lead.email or lead.phone or "Unknown"
            lines.append(f"• {label[:40]}")
    elif recent:
        lines.append("Recent leads:")
        for lead in recent:
            label = lead.name or lead.email or lead.phone or "Unknown"
            lines.append(f"• {label[:40]}")
    else:
        lines.append("No new leads this week yet.")

    site = getattr(settings, "SITE_URL", "").rstrip("/")
    return (
        f"Leads:\n"
        f"• This week: {stats['leads_week']}\n"
        f"• Hot: {stats['hot_leads']}\n"
        f"• Need reply: {stats['needs_reply']}\n\n"
        + "\n".join(lines)
        + f"\n\nOpen inbox: {site}/engage/",
        "leads",
        True,
        {
            "leads_week": stats["leads_week"],
            "hot_leads": stats["hot_leads"],
            "needs_reply": stats["needs_reply"],
        },
    )


def _handle_book(user) -> tuple[str, str, bool, dict]:
    from apps.bookings.models import Booking, BookingLink
    from apps.bookings.service_setup import booking_public_url, ensure_primary_booking_link

    link = BookingLink.objects.filter(user=user, is_active=True).order_by("created_at").first()
    profile = getattr(user, "profile", None)
    if not link and profile and getattr(profile, "business_model", "") == "service":
        link = ensure_primary_booking_link(user)

    if not link:
        site = getattr(settings, "SITE_URL", "").rstrip("/")
        return (
            f"No booking page yet.\n\nSet one up: {site}/bookings/links/new/",
            "book",
            True,
            {"has_booking_link": False},
        )

    url = booking_public_url(link)
    services = link.services or []
    service_lines = []
    for svc in services[:5]:
        name = svc.get("name", "Service")
        price = svc.get("price_kes", 0)
        duration = svc.get("duration_minutes", 60)
        service_lines.append(f"• {name} — KES {price:,.0f} ({duration} min)")

    upcoming = Booking.objects.filter(
        booking_link=link,
        status__in=[Booking.Status.CONFIRMED, Booking.Status.PENDING],
        scheduled_at__gte=timezone.now(),
    ).count()

    body = (
        f"Booking page: {link.label}\n"
        f"Link: {url}\n"
        f"Upcoming: {upcoming} appointment(s)"
    )
    if service_lines:
        body += "\n\nServices:\n" + "\n".join(service_lines)
    else:
        body += "\n\nAdd services in the app to show them here."

    site = getattr(settings, "SITE_URL", "").rstrip("/")
    body += f"\n\nManage: {site}/bookings/"
    return (
        body,
        "book",
        True,
        {"has_booking_link": True, "booking_url": url, "upcoming": upcoming},
    )


def _handle_money(user) -> tuple[str, str, bool, dict]:
    from apps.briefs.revenue_summary import format_money_whatsapp_message, get_unified_revenue_summary

    summary = get_unified_revenue_summary(user)
    return (
        format_money_whatsapp_message(summary),
        "money",
        True,
        {
            "total_kes": summary["total_kes"],
            "mpesa_kes": summary["mpesa_kes"],
            "revenue_week": summary["total_kes"],
            "leads_week": summary["leads_week"],
        },
    )


def _handle_idea(user, text: str) -> tuple[str, str, bool, dict]:
    from apps.briefs.actions import ensure_brief_idea_asset, proposals_url_for_asset

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

    from apps.billing.enforcement import check_seed_limit

    allowed, limit_msg = check_seed_limit(user)
    if not allowed:
        return limit_msg, "idea", False, {}

    asset = ensure_brief_idea_asset(
        user,
        idea,
        context=context,
        platform_hint=platform_hint,
        source="whatsapp",
    )
    url = proposals_url_for_asset(asset)
    return (
        f"Idea #{idx + 1} — pick your campaign angle:\n\"{idea[:120]}\"\n\n"
        f"{url}\n\nReply CAMPAIGNS to see campaigns ready to approve.",
        f"idea_{idx + 1}",
        True,
        {"asset_id": str(asset.pk)},
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
    buttons = action_buttons_for_user(user, posts_pending=pending, brief=brief)
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
