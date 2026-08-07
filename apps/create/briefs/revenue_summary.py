"""Unified revenue summary — web + WhatsApp parity (Wave 7 foundation)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone


def get_unified_revenue_summary(user, *, days: int = 7, ops: dict | None = None) -> dict:
    """
    Single revenue payload for MONEY command, standup, and Today board.
    Combines M-Pesa, bookings, digital conversions, walk-ins, and top asset.

    Pass ``ops`` from ``_collect_money_board_stats`` when the caller already
    computed ops counts (avoids duplicate queries and must not call
    ``get_money_board_stats`` — that would recurse).
    """
    from apps.insight.analytics.revenue import get_revenue_brief_data
    from apps.create.briefs.dashboard import _collect_money_board_stats
    from apps.commerce.products.models import CommercePayment

    week_ago = timezone.now() - timedelta(days=days)
    brief = get_revenue_brief_data(user, days=days)
    if ops is None:
        ops = _collect_money_board_stats(user, week_ago)
    profile = getattr(user, "profile", None)
    business_model = getattr(profile, "business_model", "") if profile else ""

    mpesa = (
        CommercePayment.objects.filter(
            user=user,
            status=CommercePayment.Status.COMPLETED,
            completed_at__gte=week_ago,
        ).aggregate(total=Sum("amount"), count=Count("id"))
    )
    mpesa_kes = float(mpesa["total"] or 0)
    mpesa_count = mpesa["count"] or 0

    booking_kes = float(brief.get("booking_revenue", 0) or 0)
    digital_kes = float(brief.get("digital_revenue", 0) or 0)
    walkin_kes = float(brief.get("walkin_revenue", 0) or 0)
    total_kes = mpesa_kes + booking_kes + digital_kes + walkin_kes

    top_asset = _top_asset_this_week(user, week_ago, business_model=business_model)

    campaign_lines = brief.get("campaign_revenue_lines") or []
    best_campaign = brief.get("best_campaign")

    return {
        "days": days,
        "business_model": business_model,
        "total_kes": total_kes,
        "mpesa_kes": mpesa_kes,
        "mpesa_count": mpesa_count,
        "booking_kes": booking_kes,
        "digital_kes": digital_kes,
        "walkin_kes": walkin_kes,
        "leads_week": ops["leads_week"],
        "hot_leads": ops["hot_leads"],
        "needs_reply": ops["needs_reply"],
        "ready_to_approve": ops["ready_to_approve"],
        "top_asset_title": top_asset.get("title", ""),
        "top_asset_revenue": top_asset.get("revenue", 0),
        "top_asset_type": top_asset.get("asset_type", ""),
        "top_asset_type_label": top_asset.get("type_label", ""),
        "top_asset_source": top_asset.get("source", ""),
        "campaign_revenue_lines": campaign_lines,
        "best_campaign": best_campaign,
        "next_action": recommend_next_revenue_action(user, ops, total_kes),
    }


def recommend_next_revenue_action(user, ops: dict, total_kes: float) -> dict:
    """Revenue-tied next-best action for owner."""
    profile = getattr(user, "profile", None)
    business_model = getattr(profile, "business_model", "") if profile else ""

    if ops.get("needs_reply", 0) > 0:
        return {
            "key": "reply",
            "label": f"Reply to {ops['needs_reply']} waiting message(s)",
            "whatsapp_command": "leads",
            "priority": "high",
        }
    if ops.get("ready_to_approve", 0) > 0:
        return {
            "key": "approve",
            "label": f"Approve {ops['ready_to_approve']} post(s) to publish",
            "whatsapp_command": "approve all",
            "priority": "high",
        }
    if ops.get("hot_leads", 0) > 0:
        return {
            "key": "hot_leads",
            "label": f"Follow up on {ops['hot_leads']} hot lead(s)",
            "whatsapp_command": "leads",
            "priority": "medium",
        }
    if business_model == "service":
        return {
            "key": "book",
            "label": "Share your booking link on WhatsApp Status",
            "whatsapp_command": "book",
            "priority": "medium",
        }
    if business_model == "professional":
        return {
            "key": "book",
            "label": "Share a portfolio post with your consultation link",
            "whatsapp_command": "book",
            "priority": "medium",
        }
    if total_kes <= 0:
        return {
            "key": "snap",
            "label": "Snap a product and post today",
            "whatsapp_command": "help",
            "priority": "medium",
        }
    return {
        "key": "money",
        "label": "Review what's selling and double down",
        "whatsapp_command": "money",
        "priority": "low",
    }


def format_money_whatsapp_message(summary: dict) -> str:
    """WhatsApp MONEY command body from unified summary."""
    bm = summary.get("business_model", "")
    header = {
        "product": "Money this week:",
        "service": "Revenue & bookings this week:",
        "professional": "Pipeline & revenue this week:",
    }.get(bm, "Money this week:")
    hot_label = {
        "professional": "Hot consultation leads",
        "service": "Hot booking leads",
    }.get(bm, "Hot leads")
    approve_label = {
        "professional": "Authority posts to approve",
    }.get(bm, "Posts to approve")

    lines = [
        header,
        f"• Total: KES {summary['total_kes']:,.0f}",
    ]
    if summary["mpesa_kes"]:
        lines.append(f"• M-Pesa: KES {summary['mpesa_kes']:,.0f} ({summary['mpesa_count']} sale(s))")
    if summary["booking_kes"]:
        label = "Consultations" if bm == "professional" else "Bookings"
        lines.append(f"• {label}: KES {summary['booking_kes']:,.0f}")
    if summary["digital_kes"]:
        lines.append(f"• Digital: KES {summary['digital_kes']:,.0f}")
    if summary["walkin_kes"]:
        lines.append(f"• Walk-in: KES {summary['walkin_kes']:,.0f}")
    lines.extend([
        f"• Leads: {summary['leads_week']}",
        f"• {hot_label}: {summary['hot_leads']}",
        f"• Need reply: {summary['needs_reply']}",
        f"• {approve_label}: {summary['ready_to_approve']}",
    ])
    if summary.get("top_asset_title"):
        type_label = summary.get("top_asset_type_label") or "Top asset"
        rev = summary.get("top_asset_revenue") or 0
        if rev > 0:
            lines.append(f"• Top {type_label.lower()}: {summary['top_asset_title']} (KES {rev:,.0f})")
        else:
            lines.append(f"• Top {type_label.lower()}: {summary['top_asset_title']}")
    for camp_line in (summary.get("campaign_revenue_lines") or [])[:2]:
        lines.append(f"• {camp_line}")
    nba = summary.get("next_action") or {}
    if nba.get("label"):
        lines.append(f"\nNext: {nba['label']}")
        if nba.get("whatsapp_command"):
            lines.append(f"Reply {nba['whatsapp_command'].upper()}")
    return "\n".join(lines)


def format_standup_money_line(summary: dict) -> str:
    bm = summary.get("business_model", "")
    parts = []
    if summary["total_kes"] > 0:
        parts.append(f"KES {summary['total_kes']:,.0f} this week")
        if summary["mpesa_kes"]:
            parts.append(f"M-Pesa {summary['mpesa_kes']:,.0f}")
        if summary["booking_kes"]:
            label = "consultations" if bm == "professional" else "bookings"
            parts.append(f"{label} {summary['booking_kes']:,.0f}")
    top_title = summary.get("top_asset_title", "")
    top_type = summary.get("top_asset_type_label", "")
    if top_title and bm == "professional":
        rev = summary.get("top_asset_revenue") or 0
        if rev > 0:
            parts.append(f"top {top_type.lower()}: {top_title} (KES {rev:,.0f})")
        else:
            parts.append(f"top {top_type.lower()}: {top_title}")
    return " · ".join(parts)


def format_money_board_digest(user, stats: dict) -> tuple[str, str]:
    """Email + in-app subject/body for money board digest, tuned by business_model."""
    bm = stats.get("business_model") or getattr(getattr(user, "profile", None), "business_model", "")
    needs = stats.get("needs_reply", 0)
    hot = stats.get("hot_leads", 0)
    approve = stats.get("ready_to_approve", 0)

    parts = []
    if needs:
        parts.append(f"{needs} need reply")
    if hot:
        if bm == "professional":
            parts.append(f"{hot} hot consultation lead{'s' if hot != 1 else ''}")
        elif bm == "service":
            parts.append(f"{hot} hot booking lead{'s' if hot != 1 else ''}")
        else:
            parts.append(f"{hot} hot lead{'s' if hot != 1 else ''}")
    if approve:
        if bm == "professional":
            parts.append(f"{approve} authority post{'s' if approve != 1 else ''} to approve")
        else:
            parts.append(f"{approve} to approve")

    subject_map = {
        "professional": "Kova — consultation pipeline needs you",
        "service": "Kova — bookings & leads need you",
        "product": "Kova — money needs your attention",
    }
    prefix_map = {
        "professional": "Pipeline check:",
        "service": "Service board:",
        "product": "Money board:",
    }
    subject = subject_map.get(bm, subject_map["product"])
    message = f"{prefix_map.get(bm, 'Money board:')} " + ", ".join(parts) + "."
    if stats.get("top_asset_title"):
        type_lbl = stats.get("top_asset_type_label", "asset")
        message += f" Top {type_lbl.lower()}: {stats['top_asset_title']}."
    return subject, message


def _top_asset_this_week(user, since, *, business_model: str = ""):
    from apps.create.briefs.asset_attribution import top_asset_this_week

    return top_asset_this_week(user, since, business_model=business_model)
