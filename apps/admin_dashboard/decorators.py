from functools import wraps

from django.shortcuts import redirect


def staff_required(view_func):
    """Require is_staff=True. Redirects non-staff users to landing page."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return redirect("landing")
        return view_func(request, *args, **kwargs)
    return _wrapped


def superuser_required(view_func):
    """Require is_superuser=True. For critical operations:
    toggling staff status, bulk grants, system health, CSV exports.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            from django.contrib import messages
            if request.user.is_authenticated and request.user.is_staff:
                messages.error(request, "This action requires superuser access.")
            return redirect("landing")
        return view_func(request, *args, **kwargs)
    return _wrapped


def senior_staff_required(view_func):
    """Require superuser for billing/subscription changes, plan modifications,
    partner approval, and email broadcasts. Prevents junior staff from
    making financial or account-level changes.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            from django.contrib import messages
            if request.user.is_authenticated and request.user.is_staff:
                messages.error(request, "This action requires senior staff (superuser) access.")
            return redirect("landing")
        return view_func(request, *args, **kwargs)
    return _wrapped
