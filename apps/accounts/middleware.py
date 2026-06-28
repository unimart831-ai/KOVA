"""Middleware for accounts app."""

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.shortcuts import redirect

from apps.accounts.phone_utils import user_needs_phone


class HealthCheckMiddleware:
    """Answer /health/ before sessions, Redis, or auth — keeps Railway probes fast."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.rstrip("/") == "/health":
            return HttpResponse("ok", content_type="text/plain")
        return self.get_response(request)


class RequirePhoneMiddleware:
    """Redirect authenticated users without phone to the capture screen."""

    # Paths reachable before phone capture (keep in sync with OnboardingMiddleware where noted).
    EXEMPT_PREFIXES = (
        "/accounts/onboarding/",
        "/accounts/settings/",
        "/accounts/logout/",
        "/accounts/login/",
        "/accounts/signup/",
        "/accounts/confirm-email/",
        "/accounts/password/",
        "/accounts/google/",
        "/accounts/facebook/",
        "/billing/pricing/",
        "/help/",
        "/teams/invite/",
        "/admin/",
        "/health/",
        "/static/",
        "/media/",
        "/learn/",
        "/blog/",
        "/favicon.ico",
        "/__reload__/",  # django-browser-reload SSE (dev only)
        "/sw.js",  # PWA service worker — must not redirect
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if (
            getattr(user, "is_authenticated", False)
            and user.is_authenticated
            and not user.is_staff
            and user_needs_phone(user)
            and not any(request.path.startswith(p) for p in self.EXEMPT_PREFIXES)
        ):
            return redirect("accounts:collect_phone")
        return self.get_response(request)


class OnboardingMiddleware:
    """Redirect authenticated users who haven't completed onboarding."""

    ALLOWED_PREFIXES = (
        "/accounts/onboarding/",
        "/accounts/api/",
        "/accounts/logout/",
        "/accounts/login/",
        "/accounts/signup/",
        "/accounts/confirm-email/",
        "/accounts/password/reset/",
        "/accounts/google/",
        "/accounts/facebook/",
        "/billing/pricing/",
        "/help/",
        "/teams/invite/",
        "/admin/",
        "/health/",
        "/static/",
        "/media/",
        "/favicon.ico",
        "/__reload__/",
        "/sw.js",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and not request.user.onboarding_completed
            and not request.user.is_staff
            and not any(request.path.startswith(p) for p in self.ALLOWED_PREFIXES)
        ):
            return redirect("accounts:onboarding_choose_path")
        return self.get_response(request)


class ProfilePrefetchMiddleware:
    """Load user + profile in one query; create profile if missing."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and user.pk:
            from apps.accounts.profile_utils import ensure_user_profile

            ensure_user_profile(user)
            if "profile" not in user.__dict__:
                User = get_user_model()
                try:
                    request.user = User.objects.select_related("profile").get(pk=user.pk)
                except User.DoesNotExist:
                    pass
        return self.get_response(request)
