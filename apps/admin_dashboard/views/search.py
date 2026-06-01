"""Admin dashboard — global staff search."""

from django.shortcuts import render

from apps.admin_dashboard.decorators import staff_required
from apps.admin_dashboard.search_service import MIN_QUERY_LEN, admin_global_search, maybe_interpret_query


@staff_required
def global_search(request):
    q = request.GET.get("q", "").strip()
    groups = admin_global_search(q) if q else []
    ai_hint = ""
    if q and request.GET.get("interpret") == "1":
        ai_hint = maybe_interpret_query(q, groups)

    context = {
        "page_title": "Search" if not request.headers.get("HX-Request") else "",
        "q": q,
        "groups": groups,
        "ai_hint": ai_hint,
        "min_len": MIN_QUERY_LEN,
    }

    if request.headers.get("HX-Request"):
        return render(request, "admin_dashboard/search/_results.html", context)
    return render(request, "admin_dashboard/search/page.html", context)


@staff_required
def search_suggest(request):
    q = request.GET.get("q", "").strip()
    groups = admin_global_search(q) if len(q) >= MIN_QUERY_LEN else []
    return render(
        request,
        "admin_dashboard/search/_suggest.html",
        {
            "q": q,
            "groups": groups,
            "min_len": MIN_QUERY_LEN,
        },
    )
