from django.shortcuts import render

from apps.core.admin_dashboard.decorators import staff_required
from apps.core.admin_dashboard.overview_metrics import get_cached_overview_context


@staff_required
def overview(request):
    """Admin dashboard home — key metrics, charts data, activity feed."""
    force_refresh = request.GET.get("refresh") == "1"
    context = get_cached_overview_context(force_refresh=force_refresh)
    context["page_title"] = "Dashboard Overview"
    return render(request, "admin_dashboard/overview.html", context)
