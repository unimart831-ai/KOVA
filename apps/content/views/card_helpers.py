"""Shared HTMX post-card responses."""

from __future__ import annotations

from django.http import HttpRequest
from django.shortcuts import render


def is_compact_card_request(request: HttpRequest) -> bool:
    url = (
        request.headers.get("HX-Current-URL")
        or request.META.get("HTTP_REFERER")
        or ""
    )
    return "/content/queue" in url or "/content/calendar" in url


def render_post_card(request, post, **extra):
    ctx = {"post": post, "compact_card": is_compact_card_request(request)}
    ctx.update(extra)
    return render(request, "components/post_card.html", ctx)
