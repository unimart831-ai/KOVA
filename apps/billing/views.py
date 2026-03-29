from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def billing_overview(request):
    """Billing overview page."""
    return render(request, "billing/overview.html", {
        "page_title": "Billing & Plan",
    })
