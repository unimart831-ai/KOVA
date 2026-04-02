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
