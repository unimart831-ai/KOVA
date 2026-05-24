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

    post_stats = Post.objects.filter(user=user).aggregate(
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
    if SocialAccount.objects.filter(user=user, platform="whatsapp", is_active=True).exists():
        try:
            from apps.whatsapp.models import WhatsAppConversation
            wa_escalated = WhatsAppConversation.objects.filter(
                social_account__user=user,
                status="escalated",
            ).count()
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


def _setup_checklist_from_stats(user, stats):
    days_since_signup = (timezone.now() - user.date_joined).days
    if days_since_signup > 14:
        return None

    profile = user.profile
    has_brand_voice = bool(profile.brand_voice and profile.brand_voice.strip())

    items = [
        {
            "key": "connect_platform",
            "label": "Connect a social account",
            "done": stats["has_platform"],
            "url_name": "platforms:list",
            "icon": "🔗",
        },
        {
            "key": "brand_voice",
            "label": "Set your brand voice",
            "done": has_brand_voice,
            "url_name": "accounts:settings",
            "icon": "🎯",
        },
        {
            "key": "first_post",
            "label": "Publish or schedule your first post",
            "done": stats["has_published"] or stats["has_scheduled"],
            "url_name": "content:studio",
            "icon": "✍️",
        },
        {
            "key": "read_brief",
            "label": "Review your Daily Brief",
            "done": stats["has_brief_read"],
            "url_name": "brief:home",
            "icon": "📊",
        },
    ]
    completed = sum(1 for i in items if i["done"])
    total = len(items)
    if completed == total:
        return None
    return {
        "items": items,
        "completed": completed,
        "total": total,
        "percent": int((completed / total) * 100),
        "next_step": next((i for i in items if not i["done"]), None),
    }


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
    try:
        from apps.profile_audit.models import ProfileAudit, ProfileUpdateSuggestion
        latest_ids = list(
            ProfileAudit.objects.filter(user=user)
            .values("social_account_id")
            .annotate(latest_id=Max("id"))
            .values_list("latest_id", flat=True)
        )
        audits = (
            ProfileAudit.objects
            .filter(id__in=latest_ids, completeness_score__lt=70, error="")
            .select_related("social_account")
            .annotate(pending=Count(
                "suggestions",
                filter=Q(suggestions__status=ProfileUpdateSuggestion.Status.PENDING),
            ))[:3]
        )
        return [
            {
                "platform": a.social_account.platform,
                "score": a.completeness_score,
                "pending": a.pending,
                "account_id": a.social_account_id,
            }
            for a in audits
        ]
    except Exception:
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
        "value_summary": _value_summary_from_stats(stats),
        "profile_health_alerts": _profile_health_alerts(user),
        "revenue_stat": get_cached_revenue_stat(user),
        "momentum": _build_momentum_data(user),
        "brief_streak": _build_brief_streak(user),
        "quick_actions": _build_quick_actions(user, brief),
    }
    cache.set(cache_key, extras, HOME_EXTRAS_TTL)
    return extras
