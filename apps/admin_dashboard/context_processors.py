"""Context for admin dashboard templates (staff-only badges)."""

from django.core.cache import cache


def admin_nav(request):
    """Sidebar badges for staff on admin dashboard routes."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    if not request.user.is_staff:
        return {}

    path = getattr(request, "path", "") or ""
    if not path.startswith("/dashboard"):
        return {}

    cache_key = "admin_nav:agency_sales_new"
    count = cache.get(cache_key)
    if count is None:
        try:
            from apps.billing.models import AgencySalesInquiry

            count = AgencySalesInquiry.objects.filter(
                status=AgencySalesInquiry.Status.NEW,
            ).count()
        except Exception:
            count = 0
        cache.set(cache_key, count, 60)

    return {"admin_sales_inquiry_new_count": count}
