"""Public campaign pages and studio campaign helpers."""

from __future__ import annotations

from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.create.content.campaign_pages import (
    build_campaign_page_context,
    resolve_public_campaign,
    track_campaign_view,
)


@require_GET
def public_campaign_page(request, campaign_slug):
    campaign = resolve_public_campaign(campaign_slug)
    if not campaign:
        raise Http404

    track_campaign_view(request, campaign)
    ctx = build_campaign_page_context(campaign, request)
    return render(request, "content/public/campaign_page.html", ctx)
