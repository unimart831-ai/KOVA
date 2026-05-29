"""Middleware for accounts app."""

from django.contrib.auth import get_user_model
from django.shortcuts import redirect

from apps.accounts.phone_utils import user_needs_phone


class RequirePhoneMiddleware:
    """Redirect authenticated users without phone to the capture screen."""

    EXEMPT_PREFIXES = (
        "/accounts/onboarding/phone/",
        "/accounts/logout/",
        "/accounts/login/",
        "/accounts/signup/",
        "/accounts/confirm-email/",
        "/accounts/password/",
        "/accounts/google/",
        "/accounts/facebook/",
        "/admin/",
        "/health/",
        "/static/",
        "/media/",
        "/learn/",
        "/blog/",
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
        "/accounts/settings/",
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
            return redirect("accounts:onboarding")
        return self.get_response(request)


class ProfilePrefetchMiddleware:
    """Load user + profile in one query after authentication."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(request, "user", None) and request.user.is_authenticated:
            User = get_user_model()
            try:
                request.user = User.objects.select_related("profile").get(pk=request.user.pk)
            except User.DoesNotExist:
                pass
        return self.get_response(request)
