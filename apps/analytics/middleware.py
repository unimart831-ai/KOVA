"""
Feature-usage tracking middleware.

Logs one PageView row per authenticated GET request so the admin
dashboard can show which sections users actually use.

Lightweight by design:
- Skips anonymous users, AJAX/HTMX partials, static files, admin, API, dashboard
- Uses bulk_create with a small buffer (flushed every N requests) to
  reduce DB writes — but falls back to single insert for simplicity
  in low-traffic environments.
"""

import re

# URL prefix → section key  (order matters — first match wins)
_SECTION_MAP = [
    # Sub-sections that must match BEFORE their parent prefix
    (re.compile(r"^/analytics/attribution"), "attribution"),
    (re.compile(r"^/analytics/intelligence"), "intelligence"),
    (re.compile(r"^/leads/nurture"), "nurture"),
    (re.compile(r"^/accounts/settings"), "settings"),
    # Main sections
    (re.compile(r"^/brief/"), "brief"),
    (re.compile(r"^/content/"), "content"),
    (re.compile(r"^/engage/"), "engage"),
    (re.compile(r"^/whatsapp/"), "whatsapp"),
    (re.compile(r"^/agents/"), "agents"),
    (re.compile(r"^/analytics/"), "analytics"),
    (re.compile(r"^/leads/"), "leads"),
    (re.compile(r"^/links/"), "links"),
    (re.compile(r"^/products/"), "products"),
    (re.compile(r"^/billing/"), "billing"),
    (re.compile(r"^/teams/"), "teams"),
    (re.compile(r"^/emails/"), "emails"),
    (re.compile(r"^/notifications/"), "notifications"),
    (re.compile(r"^/help/"), "help"),
]

# Paths we never track
_SKIP_PREFIXES = ("/admin/", "/api/", "/dashboard/", "/static/", "/media/", "/health/", "/sw.js")


def _resolve_section(path: str) -> str | None:
    """Return section key for a URL path, or None to skip."""
    if path.startswith(_SKIP_PREFIXES):
        return None
    for pattern, section in _SECTION_MAP:
        if pattern.search(path):
            return section
    return None


class FeatureUsageMiddleware:
    """Record one PageView per authenticated page load."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only track successful GETs from logged-in users
        if (
            request.method != "GET"
            or not hasattr(request, "user")
            or not request.user.is_authenticated
            or response.status_code >= 400
        ):
            return response

        # Skip HTMX partial loads & AJAX (we want full page loads only)
        if request.headers.get("HX-Request") or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return response

        section = _resolve_section(request.path)
        if section is None:
            return response

        # Buffer analytics — flushed to DB via Celery (non-blocking)
        try:
            from apps.analytics.pageview_buffer import buffer_pageview
            buffer_pageview(request.user.pk, section, request.path)
        except Exception:
            try:
                from apps.analytics.models import PageView
                PageView.objects.create(
                    user=request.user,
                    section=section,
                    path=request.path[:500],
                )
            except Exception:
                pass

        return response
