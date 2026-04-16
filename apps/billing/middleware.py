"""
Plan enforcement middleware — checks plan limits on key actions.

Injects `plan_limits` into every authenticated request so templates and views
can access limits without repeated lookups. Also blocks actions that exceed
the user's current plan.
"""

import logging

from django.contrib import messages
from django.shortcuts import redirect

from apps.billing.models import get_plan_limits

logger = logging.getLogger(__name__)

# URL name prefixes that should be checked for plan limits
PLATFORM_CONNECT_URLS = ["platforms:connect", "platforms:callback"]
CONTENT_CREATE_URLS = ["content:create", "content:generate"]
COMPETITOR_URLS = [
    "analytics:competitors", "analytics:competitor_add",
    "analytics:competitor_detail", "analytics:competitor_analyze",
    "analytics:competitor_landscape",
]
ENGAGE_URLS = ["engage:inbox", "engage:send_reply", "engage:trigger"]
WHATSAPP_URLS = [
    "whatsapp:inbox", "whatsapp:conversation", "whatsapp:send_message",
    "whatsapp:toggle_ai", "whatsapp:template_list", "whatsapp:template_create",
]
MEMES_URLS = [
    "memes:discover", "memes:queue", "memes:settings", "memes:detail",
    "memes:adapt", "memes:card", "memes:approve", "memes:reject", "memes:to_post",
]
SEED_CREATE_URLS = ["content:generate"]


class PlanEnforcementMiddleware:
    """
    Middleware that:
    1. Attaches plan_limits to request for easy template access
    2. Blocks platform connects if at limit
    3. Blocks post creation if at monthly limit
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only process authenticated users
        if request.user.is_authenticated:
            profile = getattr(request.user, "profile", None)
            if profile:
                request.plan_limits = get_plan_limits(profile.plan)
            else:
                request.plan_limits = get_plan_limits("starter")
        else:
            request.plan_limits = get_plan_limits("starter")

        response = self.get_response(request)
        return response

    def _check_platform_limit(self, request):
        """Check if user can connect another social account."""
        from apps.platforms.models import SocialAccount

        profile = request.user.profile
        limits = get_plan_limits(profile.plan)
        current_count = SocialAccount.objects.filter(
            user=request.user, is_active=True
        ).count()

        if current_count >= limits["max_social_accounts"]:
            messages.warning(
                request,
                f"Your {limits['label']} plan allows up to "
                f"{limits['max_social_accounts']} social account(s). "
                f"Upgrade to connect more.",
            )
            return redirect("billing:pricing")
        return None

    def _check_post_limit(self, request):
        """Check if user can create another post this month."""
        from django.utils import timezone

        from apps.content.models import Post

        profile = request.user.profile
        limits = get_plan_limits(profile.plan)

        # Unlimited check
        if limits["max_posts_per_month"] >= 999999:
            return None

        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_count = Post.objects.filter(
            user=request.user,
            created_at__gte=month_start,
        ).count()

        if month_count >= limits["max_posts_per_month"]:
            messages.warning(
                request,
                f"You've used all {limits['max_posts_per_month']} posts for this month "
                f"on your {limits['label']} plan. Upgrade for more.",
            )
            return redirect("billing:pricing")
        return None

    def _check_seed_limit(self, request):
        """Check if user can create another seed this month."""
        from django.utils import timezone

        from apps.content.models import ContentSeed

        profile = request.user.profile
        limits = get_plan_limits(profile.plan)

        # Unlimited check
        if limits["max_seeds_per_month"] >= 999999:
            return None

        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_count = ContentSeed.objects.filter(
            user=request.user,
            created_at__gte=month_start,
        ).count()

        if month_count >= limits["max_seeds_per_month"]:
            messages.warning(
                request,
                f"You've used all {limits['max_seeds_per_month']} content seeds for this month "
                f"on your {limits['label']} plan. Upgrade for more.",
            )
            return redirect("billing:pricing")
        return None

    def _check_competitor_access(self, request):
        """Check if user's plan includes competitor tracking."""
        profile = request.user.profile
        limits = get_plan_limits(profile.plan)

        if not limits.get("competitor_tracking", False):
            messages.warning(
                request,
                f"Competitor tracking is not included in your {limits['label']} plan. "
                f"Upgrade to Kazi or higher to unlock.",
            )
            return redirect("billing:pricing")
        return None

    def _check_engage_access(self, request):
        """Check if user's plan includes the engagement inbox."""
        profile = request.user.profile
        limits = get_plan_limits(profile.plan)

        if not limits.get("engagement_agent", False):
            messages.warning(
                request,
                f"The engagement inbox is not included in your {limits['label']} plan. "
                f"Upgrade to Kazi or higher to unlock.",
            )
            return redirect("billing:pricing")
        return None

    def _check_whatsapp_access(self, request):
        """Check if user's plan includes WhatsApp features."""
        profile = request.user.profile
        limits = get_plan_limits(profile.plan)

        if not limits.get("whatsapp_enabled", False):
            messages.warning(
                request,
                f"WhatsApp is not included in your {limits['label']} plan. "
                f"Upgrade to Biashara / Pro or higher to unlock.",
            )
            return redirect("billing:pricing")
        return None

    def _check_memes_access(self, request):
        """Check if user's plan includes Meme Intelligence."""
        profile = request.user.profile
        limits = get_plan_limits(profile.plan)

        if not limits.get("memes_enabled", False):
            messages.warning(
                request,
                f"Meme Intelligence is not included in your {limits['label']} plan. "
                f"Upgrade to Biashara / Pro or higher to unlock.",
            )
            return redirect("billing:pricing")
        return None

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Check plan limits before specific views execute."""
        if not request.user.is_authenticated:
            return None

        # Resolve URL name
        url_name = request.resolver_match.url_name if request.resolver_match else ""
        namespace = request.resolver_match.namespace if request.resolver_match else ""
        full_name = f"{namespace}:{url_name}" if namespace else url_name

        # ── Feature gates (block on ANY request method, not just POST) ──
        if full_name in COMPETITOR_URLS:
            return self._check_competitor_access(request)

        if full_name in ENGAGE_URLS:
            return self._check_engage_access(request)

        if full_name in WHATSAPP_URLS:
            return self._check_whatsapp_access(request)

        if full_name in MEMES_URLS:
            return self._check_memes_access(request)

        # ── Limit checks (POST only) ──
        if request.method != "POST":
            return None

        if full_name in PLATFORM_CONNECT_URLS:
            return self._check_platform_limit(request)

        if full_name in CONTENT_CREATE_URLS:
            return self._check_post_limit(request)

        if full_name in SEED_CREATE_URLS:
            return self._check_seed_limit(request)

        return None
