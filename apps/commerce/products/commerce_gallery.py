"""Published media gallery for public shop pages."""

from __future__ import annotations

from typing import Any

from apps.create.content.models import Post

PUBLIC_STATUSES = (
    Post.Status.PUBLISHED,
    Post.Status.SCHEDULED,
    Post.Status.APPROVED,
)


def get_published_media_gallery(user, *, limit: int = 12) -> list[dict[str, Any]]:
    """Images from Kova-published posts (phase 1 — no social import)."""
    posts = (
        Post.objects.filter(
            user=user,
            status__in=PUBLIC_STATUSES,
        )
        .exclude(media_urls=[])
        .order_by("-published_at", "-created_at")[: limit * 3]
    )
    gallery: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for post in posts:
        for url in post.media_urls or []:
            if not url or url in seen_urls:
                continue
            if url.lower().endswith((".mp4", ".mov", ".webm")):
                continue
            seen_urls.add(url)
            gallery.append({
                "url": url,
                "platform": post.platform,
                "post_format": post.post_format,
                "caption": (post.content_text or "")[:80],
            })
            if len(gallery) >= limit:
                return gallery
    return gallery
