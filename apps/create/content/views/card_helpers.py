"""Shared HTMX post-card responses."""

from __future__ import annotations

from django.http import HttpRequest
from django.shortcuts import render


def _card_context_from_request(request):
    url = (
        request.headers.get("HX-Current-URL")
        or request.META.get("HTTP_REFERER")
        or ""
    )
    share = "/content/studio/shares/" in url
    compact = (
        "/content/queue" in url
        or "/content/calendar" in url
        or share
    )
    return {"compact_card": compact, "share_context": share}


def is_compact_card_request(request: HttpRequest) -> bool:
    return _card_context_from_request(request)["compact_card"]


def is_share_card_request(request: HttpRequest) -> bool:
    return _card_context_from_request(request)["share_context"]


def render_post_card(request, post, **extra):
    ctx = {"post": post, **_card_context_from_request(request)}
    ctx.update(extra)
    return render(request, "components/post_card.html", ctx)
