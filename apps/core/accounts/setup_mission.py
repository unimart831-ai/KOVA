"""Unified setup mission — onboarding + first-week progress in one place."""

from __future__ import annotations

from django.utils import timezone

COMMERCE_INDUSTRIES = frozenset({
    "ecommerce",
    "wholesale_retail",
    "fashion_beauty",
    "food_restaurant",
    "agriculture",
})

SETUP_MISSION_TTL_DAYS = 14


def is_commerce_industry(industry: str) -> bool:
    return bool(industry) and industry in COMMERCE_INDUSTRIES


def get_onboarding_intent(profile) -> str:
    """Return sell | grow | both | empty from business_model or recorded timestamps."""
    if profile.business_model in ("product", "service"):
        return "sell"
    if profile.business_model == "professional":
        return "grow"
    steps = profile.onboarding_step_timestamps or {}
    if steps.get("intent_sell"):
        return "sell"
    if steps.get("intent_both"):
        return "both"
    if steps.get("intent_grow"):
        return "grow"
    return ""


def build_setup_mission(user, stats: dict | None = None) -> dict | None:
    """
    Mission checklist for onboarding completion page and Brief home.
    Returns None when all items done or outside the first-14-days window.
    """
    if stats is None:
        from apps.create.briefs.dashboard import _collect_home_stats

        today = timezone.now().date()
        week_ago = timezone.now() - timezone.timedelta(days=7)
        stats = _collect_home_stats(user, today, week_ago)

    days_since_signup = (timezone.now() - user.date_joined).days
    if days_since_signup > SETUP_MISSION_TTL_DAYS:
        return None

    profile = user.profile
    commerce = is_commerce_industry(profile.industry) or profile.business_model in ("product", "service")
    is_service = profile.business_model == "service"
    has_brand = bool(user.onboarding_completed or (profile.brand_voice or "").strip())

    from apps.commerce.products.models import Product

    has_product = Product.objects.filter(user=user).exists()
    shop_ready = bool(profile.page_slug and has_product)

    items = [
        {
            "key": "brand",
            "label": "Brand profile ready",
            "done": has_brand,
            "url_name": "accounts:settings",
        },
        {
            "key": "content",
            "label": "First posts generated",
            "done": stats.get("created_week", 0) > 0 or stats.get("has_scheduled") or stats.get("has_published"),
            "url_name": "content:studio",
        },
    ]

    if commerce:
        items.append({
            "key": "snap",
            "label": "Add your first product" if not is_service else "Add your first service",
            "done": has_product or stats.get("product_tasks_week", 0) > 0,
            "url_name": "products:snap",
        })
        if is_service:
            from apps.commerce.bookings.models import BookingLink

            has_booking = BookingLink.objects.filter(user=user, is_active=True).exists()
            items.append({
                "key": "booking",
                "label": "Set up your booking page",
                "done": has_booking,
                "url_name": "bookings:list",
            })
        else:
            items.append({
                "key": "shop",
                "label": "Share your shop link",
                "done": shop_ready,
                "url_name": "products:list",
            })

    items.extend([
        {
            "key": "platform",
            "label": "Connect a social account",
            "done": stats.get("has_platform"),
            "url_name": "platforms:list",
        },
        {
            "key": "publish",
            "label": "Publish or schedule a post",
            "done": stats.get("has_published") or stats.get("has_scheduled"),
            "url_name": "content:studio",
        },
    ])

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
        "commerce": commerce,
        "intent": get_onboarding_intent(profile),
    }
