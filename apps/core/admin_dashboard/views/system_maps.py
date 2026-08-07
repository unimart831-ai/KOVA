"""Staff-only system flow maps for the admin dashboard."""

from django.http import Http404
from django.shortcuts import render

from apps.core.admin_dashboard.decorators import staff_required
from apps.insight.help.models import HelpPageView
from apps.insight.help.system_maps import (
    SYSTEM_MAPS,
    daily_print_maps,
    get_map,
    ordered_tab_groups,
    resolve_admin_links,
)


def _enrich_tab_groups():
    """Attach resolved admin links to each map for template rendering."""
    enriched = []
    for group_name, maps in ordered_tab_groups():
        enriched.append((
            group_name,
            [{"map": m, "admin_links": resolve_admin_links(m)} for m in maps],
        ))
    return enriched


@staff_required
def system_maps_index(request):
    HelpPageView.objects.create(user=request.user, page_type="system_maps")
    return render(request, "admin_dashboard/system_maps/index.html", {
        "page_title": "System Map",
        "tab_groups": _enrich_tab_groups(),
        "daily_maps": daily_print_maps(),
        "total_maps": len(SYSTEM_MAPS),
    })


@staff_required
def system_map_detail(request, slug):
    map_obj = get_map(slug)
    if not map_obj:
        raise Http404

    HelpPageView.objects.create(
        user=request.user,
        page_type="system_map",
        article_slug=slug,
        article_title=map_obj.title,
    )
    ordered = sorted(SYSTEM_MAPS, key=lambda m: m.print_order)
    idx = next(i for i, m in enumerate(ordered) if m.slug == slug)
    prev_map = ordered[idx - 1] if idx > 0 else None
    next_map = ordered[idx + 1] if idx < len(ordered) - 1 else None

    return render(request, "admin_dashboard/system_maps/detail.html", {
        "page_title": map_obj.title,
        "map": map_obj,
        "admin_links": resolve_admin_links(map_obj),
        "prev_map": prev_map,
        "next_map": next_map,
    })


@staff_required
def system_maps_print(request):
    HelpPageView.objects.create(user=request.user, page_type="system_maps_print")
    return render(request, "help/system_maps_print.html", {
        "maps": sorted(SYSTEM_MAPS, key=lambda m: m.print_order),
        "daily_maps": daily_print_maps(),
    })
