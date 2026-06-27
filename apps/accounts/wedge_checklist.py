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

    profile = user.profile
    bm = getattr(profile, "business_model", "") or "product"

    if bm == "professional":
        step_defs = [
            ("wedge_linkedin", "Connect LinkedIn", stats.get("has_linkedin"), "platforms:list"),
            ("wedge_instagram", "Connect Instagram", stats.get("has_instagram"), "platforms:list"),
            ("wedge_snap", "Add portfolio item", stats.get("has_snap_product"), "products:snap"),
            ("wedge_publish_link", "First publish with CTA", stats.get("has_publish_with_link"), "content:studio"),
            ("wedge_automation", "First lead or nurture", stats.get("has_automation_or_lead"), "leads:nurture_list"),
        ]
    elif bm == "service":
        step_defs = [
            ("wedge_whatsapp", "Connect WhatsApp", stats.get("has_whatsapp"), "platforms:list"),
            ("wedge_instagram", "Connect Instagram", stats.get("has_instagram"), "platforms:list"),
            ("wedge_snap", "Add a service offer", stats.get("has_snap_product"), "products:snap"),
            ("wedge_publish_link", "First publish with booking link", stats.get("has_publish_with_link"), "content:studio"),
            ("wedge_automation", "First lead or booking", stats.get("has_automation_or_lead"), "leads:nurture_list"),
        ]
    else:
        step_defs = [
            ("wedge_whatsapp", "Connect WhatsApp", stats.get("has_whatsapp"), "platforms:list"),
            ("wedge_instagram", "Connect Instagram", stats.get("has_instagram"), "platforms:list"),
            ("wedge_snap", "First Snap listing", stats.get("has_snap_product"), "products:snap"),
            ("wedge_publish_link", "First publish with shop link", stats.get("has_publish_with_link"), "content:studio"),
            ("wedge_automation", "First automation or lead", stats.get("has_automation_or_lead"), "leads:nurture_list"),
        ]

    items = [
        {
            "key": key,
            "label": label,
            "done": done or bool(steps_ts.get(key)),
            "url_name": url_name,
        }
        for key, label, done, url_name in step_defs
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
