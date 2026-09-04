"""Campaign proposals — pick a marketing opportunity from a BusinessAsset."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.billing.enforcement import check_seed_limit, seed_limit_block_response
from apps.core.billing.exceptions import PlanLimitExceeded


@login_required
def asset_campaign_proposals(request, asset_id):
    """Show 3–5 marketing angles Kova found for this asset."""
    from apps.create.content.seed_proposals import (
        cache_proposals_for_asset,
        propose_seeds_from_asset,
    )
    from apps.commerce.products.models import BusinessAsset

    asset = get_object_or_404(
        BusinessAsset.objects.select_related("product"),
        pk=asset_id, user=request.user,
    )
    proposals = propose_seeds_from_asset(asset, request.user)
    cache_proposals_for_asset(request, asset, proposals)
    usage = __import__("apps.core.billing.enforcement", fromlist=["get_seed_usage"]).get_seed_usage(request.user)

    return render(request, "dashboard/content/campaign_proposals.html", {
        "page_title": "Marketing opportunities",
        "asset": asset,
        "proposals": proposals,
        "seed_usage": usage,
    })


@login_required
@require_POST
def activate_campaign_proposal(request, asset_id):
    """User picked one proposal — create campaign and start generation."""
    from apps.create.content.seed_proposals import (
        activate_proposal,
        cache_proposals_for_asset,
        get_cached_proposals,
        propose_seeds_from_asset,
    )
    from apps.commerce.products.models import BusinessAsset

    asset = get_object_or_404(
        BusinessAsset.objects.select_related("product"),
        pk=asset_id, user=request.user,
    )
    proposal_id = (request.POST.get("proposal_id") or "").strip()
    from apps.create.content.seed_proposals import parse_content_types_from_post

    content_types = parse_content_types_from_post(request.POST)

    cached = get_cached_proposals(request, asset)
    if cached and proposal_id in cached:
        proposal = cached[proposal_id]
    else:
        proposals = {p.id: p for p in propose_seeds_from_asset(asset, request.user)}
        proposal = proposals.get(proposal_id)
    if not proposal:
        messages.error(request, "That opportunity is no longer available. Pick another.")
        return redirect("content:asset_proposals", asset_id=asset_id)

    try:
        seed = activate_proposal(
            request.user, asset, proposal, content_types=content_types,
        )
    except PlanLimitExceeded as exc:
        if request.headers.get("HX-Request"):
            return seed_limit_block_response(request, exc.message)
        messages.error(request, exc.message)
        return redirect("billing:pricing")

    messages.success(request, f"Building your campaign: {proposal.title}")
    redirect_url = f"{reverse('content:studio')}?generating={seed.pk}"
    if request.headers.get("HX-Request"):
        response = HttpResponse(status=200)
        response["HX-Redirect"] = redirect_url
        return response
    return redirect(redirect_url)
