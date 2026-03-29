from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def engage_inbox(request):
    """Engagement inbox — view and respond to interactions."""
    interactions = request.user.interactions.all()[:50]
    return render(request, "engage/inbox.html", {
        "interactions": interactions,
        "page_title": "Engagement Inbox",
    })
