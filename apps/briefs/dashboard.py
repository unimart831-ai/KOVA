"""Consolidated home dashboard — batched queries + Redis cache."""

from __future__ import annotations

from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count, Max, Q
from django.utils import timezone

HOME_EXTRAS_TTL = 90
REVENUE_STAT_TTL = 300
OPS_REPORT_TTL = 120

PRODUCT_ACTION_TYPES = (
    "snap.vision", "snap.vision_batch", "snap.carousel", "snap.reel",
    "receipt_to_restock",
)


def invalidate_home_cache(user_id) -> None:
    today = timezone.now().date().isoformat()
    cache.delete(f"brief:home_extras:{user_id}:{today}")
    cache.delete(f"brief:ops_report:{user_id}:{today}:24")
    cache.delete(f"brief:revenue:{user_id}")


def _collect_home_stats(user, today, week_ago):
    """Batch count queries shared across home dashboard widgets."""
    from apps.briefs.models import DailyBrief
    from apps.bookings.models import Booking
    from apps.content.models import Post
    from apps.engage.models import Interaction
    from apps.leads.models import Lead
    from apps.platforms.models import SocialAccount

    from apps.teams.permissions import get_scoped_post_queryset

    post_stats = get_scoped_post_queryset(user).aggregate(
        published_today=Count("id", filter=Q(
            status="published", published_at__date=today,
        )),
        failed=Count("id", filter=Q(status="failed")),
        scheduled=Count("id", filter=Q(status__in=["approved", "scheduled"])),
        published_week=Count("id", filter=Q(
            status="published", published_at__gte=week_ago,
        )),
        created_week=Count("id", filter=Q(created_at__gte=week_ago)),
    )

    engage_stats = Interaction.objects.filter(user=user).aggregate(
        inbox_waiting=Count("id", filter=Q(status__in=["new", "flagged"])),
        replies_week=Count("id", filter=Q(responded_at__gte=week_ago)),
    )

    lead_stats = Lead.objects.filter(user=user).aggregate(
        new_leads=Count("id", filter=Q(status="new")),
        leads_week=Count("id", filter=Q(first_seen_at__gte=week_ago)),
    )

    booking_today = Booking.objects.filter(
        booking_link__user=user,
        scheduled_at__date=today,
        status__in=["pending", "confirmed"],
    ).count()

    has_platform = SocialAccount.objects.filter(user=user, is_active=True).exists()
    has_published = Post.objects.filter(user=user, status="published").exists()
    has_scheduled = post_stats["scheduled"] > 0
    has_brief_read = DailyBrief.objects.filter(user=user, is_read=True).exists()

    wa_escalated = 0
    has_whatsapp = False
    has_instagram = False
    if SocialAccount.objects.filter(user=user, platform="whatsapp", is_active=True).exists():
        has_whatsapp = True
        try:
            from apps.whatsapp.models import WhatsAppConversation
            wa_escalated = WhatsAppConversation.objects.filter(
                social_account__user=user,
                status="escalated",
            ).count()
        except Exception:
            pass
    has_instagram = SocialAccount.objects.filter(
        user=user, platform="instagram", is_active=True,
    ).exists()

    has_snap_product = False
    has_publish_with_link = False
    has_automation_or_lead = False
    try:
        from apps.products.models import Product
        has_snap_product = Product.objects.filter(user=user).exists()
    except Exception:
        pass
    try:
        from apps.content.models import Post
        has_publish_with_link = Post.objects.filter(
            user=user, status="published",
        ).filter(
            Q(cta_url__gt="") | ~Q(cta_type="none"),
        ).exists()
    except Exception:
        pass
    try:
        from apps.leads.models import Lead, LeadEnrollment
        has_automation_or_lead = (
            Lead.objects.filter(user=user).exists()
            or LeadEnrollment.objects.filter(lead__user=user).exists()
        )
    except Exception:
        pass

    product_tasks = 0
    try:
        from apps.agents.models import AgentAction
        product_tasks = AgentAction.objects.filter(
            user=user,
            created_at__gte=week_ago,
            status=AgentAction.ActionStatus.COMPLETED,
            action_type__in=PRODUCT_ACTION_TYPES,
        ).count()
    except Exception:
        pass

    return {
        **post_stats,
        **engage_stats,
        **lead_stats,
        "booking_today": booking_today,
        "has_platform": has_platform,
        "has_published": has_published,
        "has_scheduled": has_scheduled,
        "has_brief_read": has_brief_read,
        "wa_escalated": wa_escalated,
        "product_tasks_week": product_tasks,
        "has_whatsapp": has_whatsapp,
        "has_instagram": has_instagram,
        "has_snap_product": has_snap_product,
        "has_publish_with_link": has_publish_with_link,
        "has_automation_or_lead": has_automation_or_lead,
    }


def _customer_pulse_from_stats(stats):
    pulse = []
    if stats["inbox_waiting"]:
        n = stats["inbox_waiting"]
        pulse.append({
            "label": "Social inbox",
            "detail": f"{n} waiting for reply",
            "url_name": "engage:inbox",
            "tone": "amber" if n >= 3 else "blue",
        })
    if stats["new_leads"]:
        n = stats["new_leads"]
        pulse.append({
            "label": "Leads",
            "detail": f"{n} new lead{'s' if n != 1 else ''}",
            "url_name": "leads:list",
            "tone": "purple",
        })
    if stats["booking_today"]:
        n = stats["booking_today"]
        pulse.append({
            "label": "Bookings",
            "detail": f"{n} today",
            "url_name": "bookings:list",
            "tone": "green",
        })
    if stats["wa_escalated"]:
        n = stats["wa_escalated"]
        pulse.append({
            "label": "WhatsApp",
            "detail": f"{n} need{'s' if n == 1 else ''} you",
            "url_name": "whatsapp:inbox",
            "tone": "red",
        })
    if stats["leads_week"] and not stats["new_leads"]:
        n = stats["leads_week"]
        pulse.append({
            "label": "Leads",
            "detail": f"{n} this week",
            "url_name": "leads:list",
            "tone": "purple",
        })
    return pulse


def _wedge_checklist_from_stats(user, stats):
    from apps.accounts.wedge_checklist import build_wedge_checklist

    return build_wedge_checklist(user, stats)


def _setup_checklist_from_stats(user, stats):
    from apps.accounts.setup_mission import build_setup_mission

    mission = build_setup_mission(user, stats)
    if not mission:
        return None
    items = [
        {**item, "icon": _SETUP_MISSION_ICONS.get(item["key"], "✓")}
        for item in mission["items"]
    ]
    next_step = mission.get("next_step")
    if next_step:
        next_step = {**next_step, "icon": _SETUP_MISSION_ICONS.get(next_step["key"], "✓")}
    return {
        "items": items,
        "completed": mission["completed"],
        "total": mission["total"],
        "percent": mission["percent"],
        "next_step": next_step,
    }


_SETUP_MISSION_ICONS = {
    "brand": "🎯",
    "content": "✍️",
    "snap": "📸",
    "shop": "🛍️",
    "platform": "🔗",
    "publish": "🚀",
}


def _collect_money_board_stats(user, week_ago):
    """Single aggregate pass for Today money-chase board."""
    from apps.content.models import Post
    from apps.engage.models import Interaction
    from apps.leads.models import Lead
    from apps.whatsapp.models import WhatsAppConversation

    row = Interaction.objects.filter(user=user).aggregate(
        engage_needs_reply=Count("id", filter=Q(status__in=["new", "flagged"])),
    )
    wa_needs_reply = WhatsAppConversation.objects.filter(
        social_account__user=user,
        status=WhatsAppConversation.Status.ESCALATED,
    ).count()
    needs_reply = row["engage_needs_reply"] + wa_needs_reply

    hot_leads = Lead.objects.filter(user=user).filter(
        Q(status=Lead.Status.NEW)
        | Q(status=Lead.Status.CONTACTED, last_activity_at__gte=week_ago),
    ).count()

    ready_to_approve = Post.objects.filter(
        user=user, status__in=["pending_approval", "draft"],
    ).count()

    leads_week = Lead.objects.filter(
        user=user, first_seen_at__gte=week_ago,
    ).count()

    return {
        "needs_reply": needs_reply,
        "needs_reply_wa": wa_needs_reply,
        "needs_reply_engage": row["engage_needs_reply"],
        "hot_leads": hot_leads,
        "ready_to_approve": ready_to_approve,
        "leads_week": leads_week,
    }


def get_money_board_stats(user):
    """Public helper for tests and Today view."""
    week_ago = timezone.now() - timedelta(days=7)
    stats = _collect_money_board_stats(user, week_ago)
    profile = getattr(user, "profile", None)
    stats["business_model"] = getattr(profile, "business_model", "") if profile else ""
    try:
        from apps.briefs.revenue_summary import get_unified_revenue_summary

        rev = get_unified_revenue_summary(user)
        stats["revenue_total_kes"] = rev["total_kes"]
        parts = []
        if rev["mpesa_kes"]:
            parts.append("M-Pesa")
        if rev["booking_kes"]:
            parts.append("bookings")
        if rev["digital_kes"]:
            parts.append("digital")
        stats["revenue_detail"] = " + ".join(parts) if parts else "No sales yet"
        stats["next_action"] = rev.get("next_action")
        stats["top_asset_title"] = rev.get("top_asset_title", "")
        stats["top_asset_revenue"] = rev.get("top_asset_revenue", 0)
        stats["top_asset_type_label"] = rev.get("top_asset_type_label", "")
        stats["top_asset_source"] = rev.get("top_asset_source", "")
    except Exception:
        pass
    return stats


def _money_board_from_stats(stats):
    is_pro = stats.get("business_model") == "professional"
    board = {
        "summary_line": (
            f"This week: {stats['leads_week']} lead{'s' if stats['leads_week'] != 1 else ''}"
            f" · {stats['needs_reply']} need reply"
            f" · {stats['ready_to_approve']} to approve"
        ),
        "needs_reply": {
            "count": stats["needs_reply"],
            "label": "Needs reply",
            "detail": (
                "Consultation DMs and comments waiting on you"
                if is_pro
                else "WhatsApp + social inbox waiting on you"
            ),
            "url_name": (
                "engage:unified_inbox"
                if stats["needs_reply_wa"] and stats["needs_reply_engage"]
                else (
                    "whatsapp:inbox"
                    if stats["needs_reply_wa"]
                    else "engage:inbox"
                )
            ),
            "url_query": (
                ""
                if stats["needs_reply_wa"] and stats["needs_reply_engage"]
                else (
                    "status=escalated"
                    if stats["needs_reply_wa"]
                    else "needs_reply=1"
                )
            ),
            "needs_reply_wa": stats["needs_reply_wa"],
            "needs_reply_engage": stats["needs_reply_engage"],
            "tone": "red" if stats["needs_reply"] >= 3 else "amber",
        },
        "hot_leads": {
            "count": stats["hot_leads"],
            "label": "Hot consultation leads" if is_pro else "Hot leads",
            "detail": (
                "Booking requests + new inquiries this week"
                if is_pro
                else "New + contacted in the last 7 days"
            ),
            "url_name": "leads:list",
            "tone": "purple",
        },
        "ready_to_approve": {
            "count": stats["ready_to_approve"],
            "label": "Authority posts to approve" if is_pro else "Ready to approve",
            "detail": (
                "Portfolio and thought-leadership posts waiting"
                if is_pro
                else "Posts waiting for your OK"
            ),
            "url_name": "content:studio",
            "tone": "kova",
        },
    }
    if stats.get("revenue_total_kes"):
        board["revenue_week"] = {
            "count": stats["revenue_total_kes"],
            "label": "Revenue this week",
            "detail": stats.get("revenue_detail", "M-Pesa + bookings + digital"),
            "url_name": "analytics:revenue",
            "tone": "green",
        }
        board["summary_line"] = (
            f"KES {stats['revenue_total_kes']:,.0f} this week"
            f" · {stats['leads_week']} lead{'s' if stats['leads_week'] != 1 else ''}"
            f" · {stats['needs_reply']} need reply"
        )
    if stats.get("top_asset_title"):
        type_lbl = stats.get("top_asset_type_label") or ("Showcase" if is_pro else "Top asset")
        rev = stats.get("top_asset_revenue") or 0
        detail = (
            f"{stats['top_asset_title']} — KES {rev:,.0f}"
            if rev > 0
            else f"{stats['top_asset_title']} — most active this week"
        )
        board["top_asset"] = {
            "title": stats["top_asset_title"],
            "type_label": type_lbl,
            "revenue": rev,
            "detail": detail,
            "url_name": "analytics:revenue",
            "tone": "emerald" if rev > 0 else "purple",
        }
    nba = stats.get("next_action")
    if nba:
        board["next_action"] = {
            "label": nba.get("label", ""),
            "key": nba.get("key", ""),
            "priority": nba.get("priority", "medium"),
            "whatsapp_command": nba.get("whatsapp_command", ""),
            "url_name": _nba_url_name(nba.get("key", "")),
        }
    return board


def _nba_url_name(key: str) -> str:
    mapping = {
        "reply": "engage:unified_inbox",
        "approve": "content:studio",
        "hot_leads": "leads:list",
        "book": "bookings:list",
        "snap": "products:snap",
        "money": "analytics:revenue",
    }
    return mapping.get(key, "brief:home")


def _value_summary_from_stats(stats):
    total = (
        stats["published_week"] + stats["created_week"]
        + stats["replies_week"] + stats["leads_week"]
        + stats["product_tasks_week"]
    )
    if total == 0:
        return None
    return {
        "posts_published": stats["published_week"],
        "posts_created": stats["created_week"],
        "replies_drafted": stats["replies_week"],
        "leads_captured": stats["leads_week"],
        "product_tasks": stats["product_tasks_week"],
    }


def _profile_health_alerts(user):
    return []


def get_cached_revenue_stat(user):
    cache_key = f"brief:revenue:{user.pk}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached if cached != "__none__" else None
    try:
        from apps.analytics.revenue import get_revenue_stat_card
        result = get_revenue_stat_card(user)
    except Exception:
        result = None
    cache.set(cache_key, result if result is not None else "__none__", REVENUE_STAT_TTL)
    return result


def get_cached_operations_report(user, hours=24):
    today = timezone.now().date().isoformat()
    cache_key = f"brief:ops_report:{user.pk}:{today}:{hours}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        from apps.briefs.operations_report import build_operations_report
        report = build_operations_report(user, hours=hours)
    except Exception:
        report = {"has_activity": False, "categories": [], "recent_tasks": []}
    cache.set(cache_key, report, OPS_REPORT_TTL)
    return report


def get_cached_home_extras(user, brief):
    """Return cached dashboard widgets (pulse, actions, stats, etc.)."""
    today = timezone.now().date()
    cache_key = f"brief:home_extras:{user.pk}:{today.isoformat()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    week_ago = timezone.now() - timedelta(days=7)
    stats = _collect_home_stats(user, today, week_ago)
    money_stats = get_money_board_stats(user)

    from apps.briefs.views import (
        _build_brief_streak,
        _build_momentum_data,
        _build_quick_actions,
    )

    extras = {
        "published_today": stats["published_today"],
        "failed_count": stats["failed"],
        "scheduled_count": stats["scheduled"],
        "has_connected_platform": stats["has_platform"],
        "customer_pulse": _customer_pulse_from_stats(stats),
        "setup_checklist": _setup_checklist_from_stats(user, stats),
        "wedge_checklist": _wedge_checklist_from_stats(user, stats),
        "money_board": _money_board_from_stats(money_stats),
        "value_summary": _value_summary_from_stats(stats),
        "profile_health_alerts": _profile_health_alerts(user),
        "revenue_stat": get_cached_revenue_stat(user),
        "momentum": _build_momentum_data(user),
        "brief_streak": _build_brief_streak(user),
        "quick_actions": _build_quick_actions(user, brief),
    }
    cache.set(cache_key, extras, HOME_EXTRAS_TTL)
    return extras
