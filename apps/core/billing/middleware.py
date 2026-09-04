"""
Plan enforcement middleware — checks plan limits on key actions.

Injects `plan_limits` into every authenticated request so templates and views
can access limits without repeated lookups. Also blocks actions that exceed
the user's current plan.
"""

import logging

from django.shortcuts import redirect

from apps.core.billing.access import is_subscription_exempt_url, subscription_allows_app_access
from apps.core.billing.models import get_user_plan_limits
from apps.core.billing.plan_limit_ui import plan_limit_redirect

logger = logging.getLogger(__name__)

# URL names checked for plan limits (must match apps/*/urls.py name= values)
PLATFORM_CONNECT_URLS = ["platforms:connect", "platforms:oauth_callback"]
ENGAGE_URLS = [
    "engage:inbox",
    "engage:unified_inbox",
    "engage:dm_inbox",
    "engage:auto_sent_list",
    "engage:send_reply",
    "engage:trigger",
]
WHATSAPP_INBOX_URLS = [
    "whatsapp:inbox", "whatsapp:conversation", "whatsapp:send_message",
    "whatsapp:toggle_ai",
]
WHATSAPP_PRO_URLS = [
    "whatsapp:template_list", "whatsapp:template_create",
    # Sprint 5C — Status Studio
    "whatsapp:status_studio", "whatsapp:status_create", "whatsapp:status_share",
    "whatsapp:status_skip", "whatsapp:status_repurpose", "whatsapp:status_calendar",
    # Sprint 5D — Broadcasts + Analytics
    "whatsapp:broadcast_list", "whatsapp:broadcast_create", "whatsapp:broadcast_detail",
    "whatsapp:broadcast_launch", "whatsapp:broadcast_pause",
    "whatsapp:sequence_create", "whatsapp:sequence_detail",
    "whatsapp:sequence_add_step", "whatsapp:sequence_toggle",
    "whatsapp:wa_analytics", "whatsapp:wa_digest_detail",
    # Sprint 5E — Channels
    "whatsapp:channel_dashboard", "whatsapp:channel_create", "whatsapp:channel_detail",
    "whatsapp:channel_post_create", "whatsapp:channel_post_publish",
    "whatsapp:channel_toggle_curate",
]
WHATSAPP_URLS = WHATSAPP_INBOX_URLS + WHATSAPP_PRO_URLS
SEED_CREATE_URLS = ["content:submit_seed", "content:voice_to_seed"]


class PlanEnforcementMiddleware:
    """
    Middleware that:
    1. Attaches plan_limits to request for easy template access
    2. Blocks platform connects if at limit
    3. Blocks campaign creation if at monthly quota (seed limit)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only process authenticated users
        if request.user.is_authenticated:
            request.plan_limits = get_user_plan_limits(request.user)
        else:
            from apps.core.billing.models import get_plan_limits
            request.plan_limits = get_plan_limits("starter")

        response = self.get_response(request)
        return response

    def _check_platform_limit(self, request):
        """Check if user can connect another social account."""
        from apps.core.platforms.models import SocialAccount

        limits = get_user_plan_limits(request.user)
        current_count = SocialAccount.objects.filter(
            user=request.user, is_active=True
        ).count()

        if current_count >= limits["max_social_accounts"]:
            return plan_limit_redirect(
                request,
                f"Your {limits['label']} plan allows up to "
                f"{limits['max_social_accounts']} social account(s). Upgrade to connect more.",
                "platforms:list",
            )
        return None

    def _check_seed_limit(self, request):
        """Check if user can create another seed this month."""
        from apps.core.billing.enforcement import check_seed_limit, seed_limit_block_response

        allowed, message = check_seed_limit(request.user)
        if not allowed:
            return seed_limit_block_response(request, message)
        return None

    def _check_engage_access(self, request):
        """Check if user's plan includes the engagement inbox."""
        from apps.core.billing.engage_trial import engage_inbox_allowed

        limits = get_user_plan_limits(request.user)

        if not engage_inbox_allowed(request.user):
            return plan_limit_redirect(
                request,
                "Engagement inbox is included on Kova. Subscribe to unlock.",
                "billing:pricing",
            )
        return None

    def _check_whatsapp_inbox_access(self, request):
        """Growth wedge: inbox + utility replies."""
        from apps.core.billing.whatsapp_access import whatsapp_inbox_allowed

        limits = get_user_plan_limits(request.user)
        if not whatsapp_inbox_allowed(limits):
            return plan_limit_redirect(
                request,
                "WhatsApp inbox is included on Kova. Subscribe to unlock.",
                "billing:pricing",
            )
        return None

    def _check_whatsapp_pro_access(self, request):
        """Pro+ broadcasts, templates, Status Studio, channels."""
        from apps.core.billing.whatsapp_access import whatsapp_full_allowed

        limits = get_user_plan_limits(request.user)
        if whatsapp_full_allowed(limits):
            return None
        if limits.get("whatsapp_inbox_enabled"):
            return plan_limit_redirect(
                request,
                "WhatsApp broadcasts, Status Studio, and channels require Agency (Wakala). "
                "Kova includes WhatsApp inbox + lead capture.",
                "whatsapp:inbox",
            )
        return plan_limit_redirect(
            request,
            "WhatsApp inbox is included on Kova. Subscribe to unlock.",
            "billing:pricing",
        )

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Check plan limits before specific views execute."""
        if not request.user.is_authenticated:
            return None

        # Dev tooling / static — never paywall (browser-reload SSE would 302-loop).
        path = request.path or ""
        if path.startswith(("/__reload__/", "/static/", "/media/", "/health/", "/favicon.ico")):
            return None

        # Resolve URL name
        url_name = request.resolver_match.url_name if request.resolver_match else ""
        namespace = request.resolver_match.namespace if request.resolver_match else ""
        full_name = f"{namespace}:{url_name}" if namespace else url_name

        # ── Subscription paywall (expired trial / lapsed period) ──
        if not is_subscription_exempt_url(full_name):
            allowed, msg = subscription_allows_app_access(request.user)
            if not allowed:
                return plan_limit_redirect(request, msg, "billing:pricing")

        # ── Feature gates (block on ANY request method, not just POST) ──
        if full_name in ENGAGE_URLS:
            return self._check_engage_access(request)

        if full_name in WHATSAPP_PRO_URLS:
            return self._check_whatsapp_pro_access(request)

        if full_name in WHATSAPP_INBOX_URLS:
            return self._check_whatsapp_inbox_access(request)

        # ── Limit checks (POST only) ──
        if request.method != "POST":
            return None

        if full_name in PLATFORM_CONNECT_URLS:
            return self._check_platform_limit(request)

        if full_name in SEED_CREATE_URLS:
            # voice_to_seed only creates a seed in submit mode
            if full_name == "content:voice_to_seed" and request.POST.get("mode", "transcribe") != "submit":
                return None
            return self._check_seed_limit(request)

        return None

