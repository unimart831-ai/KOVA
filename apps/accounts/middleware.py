"""Middleware to enforce onboarding completion for authenticated users."""

from django.shortcuts import redirect


class OnboardingMiddleware:
    """Redirect authenticated users who haven't completed onboarding."""

    ALLOWED_PREFIXES = (
        "/accounts/onboarding/",
        "/accounts/logout/",
        "/accounts/login/",
        "/accounts/signup/",
        "/accounts/confirm-email/",
        "/accounts/password/reset/",
        "/accounts/google/",
        "/platforms/connect/",
        "/platforms/callback/",
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
