"""Holiday & cultural moment preferences — owned by briefs domain."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def preferences(request):
    """Holiday & moment preferences — full engine ships in a later sprint."""
    profile = getattr(request.user, "profile", None)
    country = (getattr(profile, "country", None) or "").strip()
    return render(request, "dashboard/calendar_intel/preferences.html", {
        "country": country,
        "moment_categories": [
            {"id": "national", "label": "National holidays", "enabled": True},
            {"id": "religious", "label": "Religious observances", "enabled": True},
            {"id": "commercial", "label": "Commercial moments", "enabled": False},
        ],
    })
