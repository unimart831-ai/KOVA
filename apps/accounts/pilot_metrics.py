"""Pilot metrics for TEST_BUSINESSES admin dashboard and nightly snapshots."""

from __future__ import annotations

from datetime import timedelta

from django.core.cache import cache
from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.accounts.test_businesses import (
    TEST_BUSINESS_EMAILS,
    TEST_BUSINESS_REGISTRY,
    WA_REPLY_SLA_SECONDS,
)

PILOT_METRICS_CACHE_KEY = "admin:pilot_metrics:latest"
PILOT_METRICS_CACHE_TTL = 3600


def _pilot_wedge_status(user, stats: dict) -> dict:
    """Wedge checklist for admin — always returns status (no TTL hide)."""
    from apps.accounts.wedge_checklist import build_wedge_checklist

    checklist = build_wedge_checklist(user, stats)
    if checklist is not None:
        return checklist

    items = [
        {"key": "wedge_whatsapp", "label": "Connect WhatsApp", "done": True},
        {"key": "wedge_instagram", "label": "Connect Instagram", "done": True},
        {"key": "wedge_snap", "label": "First Snap listing", "done": True},
        {"key": "wedge_publish_link", "label": "First publish with link", "done": True},
        {"key": "wedge_automation", "label": "First automation or lead captured", "done": True},
    ]
    return {
        "items": items,
        "completed": 5,
        "total": 5,
        "percent": 100,
        "next_step": None,
    }


def _collect_stats(user, week_ago, month_ago):
    from apps.briefs.dashboard import _collect_home_stats

    today = timezone.now().date()
    return _collect_home_stats(user, today, week_ago)


def _business_metrics(user, meta: dict, *, week_ago, month_ago) -> dict:
    from apps.billing.visual_credits import get_visual_credit_usage
    from apps.content.models import Post
    from apps.leads.models import Lead

    stats = _collect_stats(user, week_ago, month_ago)
    wedge = _pilot_wedge_status(user, stats)
    polish = get_visual_credit_usage(user)

    post_counts = Post.objects.filter(user=user, updated_at__gte=month_ago).aggregate(
        published=Count("id", filter=Q(status="published")),
        failed=Count("id", filter=Q(status="failed")),
    )
    published = post_counts["published"] or 0
    failed = post_counts["failed"] or 0
    publish_attempts = published + failed
    publish_success_rate = round((published / publish_attempts) * 100, 1) if publish_attempts else None

    leads_week = Lead.objects.filter(user=user, first_seen_at__gte=week_ago).count()

    wa_sla_pct = None
    wa_avg_minutes = None
    try:
        from apps.whatsapp.models import WhatsAppAnalytics

        wa_agg = WhatsAppAnalytics.objects.filter(
            social_account__user=user,
            date__gte=week_ago.date(),
            avg_response_time_seconds__isnull=False,
        ).aggregate(avg_seconds=Avg("avg_response_time_seconds"))
        if wa_agg["avg_seconds"] is not None:
            wa_avg_minutes = round(wa_agg["avg_seconds"] / 60, 1)
            wa_sla_pct = 100.0 if wa_agg["avg_seconds"] <= WA_REPLY_SLA_SECONDS else 0.0
    except Exception:
        pass

    profile = user.profile
    return {
        "slug": meta["slug"],
        "email": meta["email"],
        "company_name": meta["company_name"],
        "plan": meta.get("plan") or profile.plan,
        "wave": meta.get("wave"),
        "user_id": str(user.pk),
        "is_active": user.is_active,
        "onboarding_completed": user.onboarding_completed,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "wedge": wedge,
        "leads_week": leads_week,
        "polish_credits_used": polish.get("used", 0),
        "polish_credits_limit": polish.get("max", 0),
        "publish_success_rate": publish_success_rate,
        "published_month": published,
        "failed_month": failed,
        "wa_avg_reply_minutes": wa_avg_minutes,
        "wa_sla_met": wa_sla_pct == 100.0 if wa_sla_pct is not None else None,
    }


def _readiness_label(*, seeded: bool, onboarding_completed: bool, wedge_completed: int, wedge_total: int) -> str:
    if not seeded:
        return "not_seeded"
    if not onboarding_completed:
        return "onboarding_pending"
    if wedge_completed >= wedge_total:
        return "pilot_ready"
    if wedge_completed > 0:
        return f"wedge_{wedge_completed}_of_{wedge_total}"
    return "seeded"


def compute_pilot_readiness(meta: dict, user=None) -> dict:
    """Readiness row for pilot_status command and cards."""
    if user is None:
        return {
            "slug": meta["slug"],
            "company_name": meta["company_name"],
            "plan": meta["plan"],
            "wave": meta.get("wave"),
            "seeded": False,
            "readiness": "not_seeded",
            "wedge_percent": 0,
        }

    week_ago = timezone.now() - timedelta(days=7)
    month_ago = timezone.now() - timedelta(days=30)
    card = _business_metrics(user, meta, week_ago=week_ago, month_ago=month_ago)
    wedge = card["wedge"]
    readiness = _readiness_label(
        seeded=True,
        onboarding_completed=card["onboarding_completed"],
        wedge_completed=wedge["completed"],
        wedge_total=wedge["total"],
    )
    return {
        "slug": meta["slug"],
        "company_name": meta["company_name"],
        "plan": meta["plan"],
        "wave": meta.get("wave"),
        "seeded": True,
        "readiness": readiness,
        "wedge_percent": wedge["percent"],
        "onboarding_completed": card["onboarding_completed"],
        "last_login": card["last_login"],
    }


def compute_pilot_metrics(*, persist_snapshot: bool = False) -> dict:
    """Aggregate + per-business pilot metrics. Optionally persist nightly snapshot."""
    from apps.accounts.models import PilotMetricsSnapshot, User

    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    users = {
        u.email: u
        for u in User.objects.filter(email__in=TEST_BUSINESS_EMAILS).select_related("profile")
    }

    businesses = []
    for meta in TEST_BUSINESS_REGISTRY:
        user = users.get(meta["email"])
        if user:
            businesses.append(_business_metrics(user, meta, week_ago=week_ago, month_ago=month_ago))
        else:
            businesses.append({
                "slug": meta["slug"],
                "email": meta["email"],
                "company_name": meta["company_name"],
                "plan": meta["plan"],
                "wave": meta.get("wave"),
                "user_id": None,
                "is_active": False,
                "onboarding_completed": False,
                "last_login": None,
                "wedge": {"completed": 0, "total": 5, "percent": 0, "items": [], "next_step": None},
                "leads_week": 0,
                "polish_credits_used": 0,
                "polish_credits_limit": 0,
                "publish_success_rate": None,
                "published_month": 0,
                "failed_month": 0,
                "wa_avg_reply_minutes": None,
                "wa_sla_met": None,
            })

    seeded = [b for b in businesses if b["user_id"]]
    active = [b for b in seeded if b["is_active"]]
    wedge_percents = [b["wedge"]["percent"] for b in seeded]
    avg_wedge_pct = round(sum(wedge_percents) / len(wedge_percents), 1) if wedge_percents else 0.0

    leads_week = sum(b["leads_week"] for b in seeded)
    polish_used = sum(b["polish_credits_used"] for b in seeded)

    publish_rates = [b["publish_success_rate"] for b in seeded if b["publish_success_rate"] is not None]
    avg_publish_success = round(sum(publish_rates) / len(publish_rates), 1) if publish_rates else None

    wa_times = [b["wa_avg_reply_minutes"] for b in seeded if b["wa_avg_reply_minutes"] is not None]
    avg_wa_reply_minutes = round(sum(wa_times) / len(wa_times), 1) if wa_times else None
    wa_sla_count = sum(1 for b in seeded if b["wa_sla_met"] is True)
    wa_sla_total = sum(1 for b in seeded if b["wa_sla_met"] is not None)

    aggregate = {
        "active_test_businesses": len(active),
        "seeded_test_businesses": len(seeded),
        "total_test_businesses": len(TEST_BUSINESS_REGISTRY),
        "avg_wedge_percent": avg_wedge_pct,
        "leads_week": leads_week,
        "polish_credits_used": polish_used,
        "publish_success_rate": avg_publish_success,
        "wa_avg_reply_minutes": avg_wa_reply_minutes,
        "wa_sla_met_count": wa_sla_count,
        "wa_sla_tracked_count": wa_sla_total,
        "wa_sla_target_minutes": WA_REPLY_SLA_SECONDS // 60,
    }

    payload = {
        "captured_at": now.isoformat(),
        "aggregate": aggregate,
        "businesses": businesses,
    }

    cache.set(PILOT_METRICS_CACHE_KEY, payload, PILOT_METRICS_CACHE_TTL)

    if persist_snapshot:
        PilotMetricsSnapshot.objects.update_or_create(
            snapshot_date=now.date(),
            defaults={
                "captured_at": now,
                "aggregate": aggregate,
                "businesses": businesses,
            },
        )

    return payload


def get_pilot_metrics(*, refresh: bool = False) -> dict:
    """Return cached pilot metrics or recompute."""
    if refresh:
        return compute_pilot_metrics()
    cached = cache.get(PILOT_METRICS_CACHE_KEY)
    if cached:
        return cached
    return compute_pilot_metrics()


def get_latest_snapshot() -> dict | None:
    from apps.accounts.models import PilotMetricsSnapshot

    snap = PilotMetricsSnapshot.objects.order_by("-snapshot_date").first()
    if not snap:
        return None
    return {
        "snapshot_date": snap.snapshot_date.isoformat(),
        "captured_at": snap.captured_at.isoformat(),
        "aggregate": snap.aggregate,
        "businesses": snap.businesses,
    }
