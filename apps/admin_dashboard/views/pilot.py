"""Admin pilot dashboard — TEST_BUSINESSES cohort health."""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.accounts.pilot_metrics import get_latest_snapshot, get_pilot_metrics
from apps.accounts.test_businesses import WAVE1_SLUGS
from apps.admin_dashboard.decorators import staff_required


@staff_required
def pilot_overview(request):
    """Pilot dashboard — active test businesses, wedge %, leads, WA SLA, polish, publish rate."""
    refresh = request.method == "POST" or request.GET.get("refresh") == "1"
    if request.method == "POST":
        get_pilot_metrics(refresh=True)
        messages.success(request, "Pilot metrics refreshed.")
        return redirect(reverse("admin_dashboard:pilot_overview"))

    metrics = get_pilot_metrics(refresh=refresh)
    latest_snapshot = get_latest_snapshot()
    businesses = sorted(
        metrics["businesses"],
        key=lambda b: (0 if b.get("wave") else 1, b["company_name"]),
    )

    return render(request, "admin_dashboard/pilot/overview.html", {
        "page_title": "Pilot Dashboard",
        "metrics": metrics,
        "aggregate": metrics["aggregate"],
        "businesses": businesses,
        "latest_snapshot": latest_snapshot,
        "wave1_slugs": WAVE1_SLUGS,
        "captured_at": metrics["captured_at"],
    })
