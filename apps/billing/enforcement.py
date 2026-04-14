"""
Plan enforcement utilities — reusable limit checks for API, Celery tasks, and views.

Use these instead of middleware when you need plan checks outside the HTTP request cycle.
"""

import logging
from django.utils import timezone

from apps.billing.models import get_plan_limits

logger = logging.getLogger(__name__)


def check_post_limit(user):
    """
    Check if user can create/publish another post this month.

    Returns:
        (allowed: bool, message: str)
    """
    from apps.content.models import Post

    profile = getattr(user, "profile", None)
    if not profile:
        return False, "No user profile found."

    limits = get_plan_limits(profile.plan)
    max_posts = limits["max_posts_per_month"]

    if max_posts >= 999999:
        return True, ""

    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_count = Post.objects.filter(
        user=user, created_at__gte=month_start,
    ).count()

    if month_count >= max_posts:
        return False, f"Monthly post limit reached ({max_posts} on {limits['label']} plan)."
    return True, ""


def check_seed_limit(user):
    """
    Check if user can create another content seed this month.

    Returns:
        (allowed: bool, message: str)
    """
    from apps.content.models import ContentSeed

    profile = getattr(user, "profile", None)
    if not profile:
        return False, "No user profile found."

    limits = get_plan_limits(profile.plan)
    max_seeds = limits["max_seeds_per_month"]

    if max_seeds >= 999999:
        return True, ""

    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_count = ContentSeed.objects.filter(
        user=user, created_at__gte=month_start,
    ).count()

    if month_count >= max_seeds:
        return False, f"Monthly seed limit reached ({max_seeds} on {limits['label']} plan)."
    return True, ""


def check_platform_limit(user):
    """
    Check if user can connect another social account.

    Returns:
        (allowed: bool, message: str)
    """
    from apps.platforms.models import SocialAccount

    profile = getattr(user, "profile", None)
    if not profile:
        return False, "No user profile found."

    limits = get_plan_limits(profile.plan)
    current_count = SocialAccount.objects.filter(user=user, is_active=True).count()

    if current_count >= limits["max_social_accounts"]:
        return False, f"Social account limit reached ({limits['max_social_accounts']} on {limits['label']} plan)."
    return True, ""


def check_api_access(user):
    """
    Check if user's plan includes API access (Pro + Agency only).

    Returns:
        (allowed: bool, message: str)
    """
    profile = getattr(user, "profile", None)
    if not profile:
        return False, "No user profile found."

    if profile.plan in ("pro", "agency"):
        return True, ""

    return False, f"API access requires Pro or Agency plan. You're on {profile.get_plan_display()}."
