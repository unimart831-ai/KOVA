"""Compact plan-limit notices — stay on context pages instead of pricing flash banners."""

from __future__ import annotations

from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import escape

PLAN_LIMIT_SESSION_KEY = "plan_limit_notice"
PLAN_LIMIT_QUERY_PARAM = "plan_limit"
DEFAULT_NOTICE = "You've reached a limit on your current plan."


def set_plan_limit_notice(request, message: str) -> None:
    request.session[PLAN_LIMIT_SESSION_KEY] = message


def pop_plan_limit_notice(request) -> str | None:
    if request.GET.get(PLAN_LIMIT_QUERY_PARAM) != "1":
        return None
    return request.session.pop(PLAN_LIMIT_SESSION_KEY, None) or DEFAULT_NOTICE


def plan_limit_banner_html(message: str, upgrade_url: str | None = None) -> str:
    upgrade_url = upgrade_url or reverse("billing:pricing")
    safe_message = escape(message)
    return (
        '<div class="flex flex-wrap items-center gap-x-3 gap-y-1 mb-4 px-3 py-2 text-xs rounded-lg '
        'border border-amber-200/80 bg-amber-50/80 dark:bg-amber-950/25 dark:border-amber-800/60 '
        'text-amber-900 dark:text-amber-200" role="status">'
        '<svg class="w-3.5 h-3.5 shrink-0 text-amber-600 dark:text-amber-400" fill="none" '
        'stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">'
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" '
        'd="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>'
        '</svg>'
        f'<span class="flex-1 min-w-0">{safe_message}</span>'
        f'<a href="{upgrade_url}" class="font-semibold text-kova-600 dark:text-kova-400 '
        'hover:underline shrink-0">Upgrade plan →</a>'
        '</div>'
    )


def _append_plan_limit_query(url: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{PLAN_LIMIT_QUERY_PARAM}=1"


def plan_limit_redirect(request, message: str, redirect_to: str, *args, **kwargs):
    """Store a notice in session and redirect back to a sensible page."""
    set_plan_limit_notice(request, message)
    if redirect_to.startswith("/"):
        url = redirect_to
    else:
        url = reverse(redirect_to, args=args, kwargs=kwargs)
    return redirect(_append_plan_limit_query(url))


def plan_limit_block_response(
    request,
    message: str,
    redirect_to: str | None = None,
    *args,
    **kwargs,
):
    """HTMX: inline banner. Full page: redirect with session notice (no flash message)."""
    if request.headers.get("HX-Request") == "true":
        return HttpResponse(plan_limit_banner_html(message), status=403)

    if redirect_to:
        return plan_limit_redirect(request, message, redirect_to, *args, **kwargs)

    referer = request.META.get("HTTP_REFERER", "")
    if referer:
        from urllib.parse import urlparse

        parsed = urlparse(referer)
        if parsed.path.startswith("/"):
            return plan_limit_redirect(request, message, parsed.path)

    return plan_limit_redirect(request, message, "brief:home")
