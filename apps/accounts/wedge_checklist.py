"""Five-step wedge onboarding checklist — WA → lead → automation loop."""

from __future__ import annotations

from django.utils import timezone

WEDGE_CHECKLIST_TTL_DAYS = 30


def _platform_connected(user, platform: str) -> bool:
    from apps.platforms.models import SocialAccount

    return SocialAccount.objects.filter(
        user=user, platform=platform, is_active=True,
    ).exists()


def _has_snap_listing(user) -> bool:
    from apps.products.models import Product

    return Product.objects.filter(user=user).exists()


def _has_publish_with_link(user) -> bool:
    from django.db.models import Q

    from apps.content.models import Post

    return Post.objects.filter(
        user=user,
        status="published",
    ).filter(
        Q(cta_url__gt="") | ~Q(cta_type="none"),
    ).exists()


def _has_automation_or_lead(user) -> bool:
    from apps.leads.models import Lead, LeadEnrollment

    if Lead.objects.filter(user=user).exists():
        return True
    return LeadEnrollment.objects.filter(lead__user=user).exists()


def build_wedge_checklist(user, stats: dict | None = None) -> dict | None:
    """
    Money-chase onboarding widget for Today home.
    Returns None when all steps complete or outside the first-30-days window.
    """
    if stats is None:
        from apps.briefs.dashboard import _collect_home_stats

        today = timezone.now().date()
        week_ago = timezone.now() - timezone.timedelta(days=7)
        stats = _collect_home_stats(user, today, week_ago)

    days_since_signup = (timezone.now() - user.date_joined).days
    if days_since_signup > WEDGE_CHECKLIST_TTL_DAYS:
        return None

    profile = user.profile
    steps_ts = profile.onboarding_step_timestamps or {}

    items = [
        {
            "key": "wedge_whatsapp",
            "label": "Connect WhatsApp",
            "done": stats.get("has_whatsapp") or bool(steps_ts.get("wedge_whatsapp")),
            "url_name": "platforms:list",
        },
        {
            "key": "wedge_instagram",
            "label": "Connect Instagram",
            "done": stats.get("has_instagram") or bool(steps_ts.get("wedge_instagram")),
            "url_name": "platforms:list",
        },
        {
            "key": "wedge_snap",
            "label": "First Snap listing",
            "done": stats.get("has_snap_product") or bool(steps_ts.get("wedge_snap")),
            "url_name": "products:snap",
        },
        {
            "key": "wedge_publish_link",
            "label": "First publish with link",
            "done": stats.get("has_publish_with_link") or bool(steps_ts.get("wedge_publish_link")),
            "url_name": "content:studio",
        },
        {
            "key": "wedge_automation",
            "label": "First automation or lead captured",
            "done": stats.get("has_automation_or_lead") or bool(steps_ts.get("wedge_automation")),
            "url_name": "leads:nurture_list",
        },
    ]

    completed = sum(1 for item in items if item["done"])
    total = len(items)
    if completed >= total:
        return None

    next_step = next((item for item in items if not item["done"]), None)
    return {
        "items": items,
        "completed": completed,
        "total": total,
        "percent": int((completed / total) * 100) if total else 100,
        "next_step": next_step,
    }
