"""Programmatic post approval — shared by web UI and WhatsApp reply-to-act."""

from __future__ import annotations

from datetime import datetime as dt

from django.utils import timezone

from apps.content.models import Post
from apps.content.scheduling import (
    get_next_best_slot,
    get_quick_schedule_time,
    get_smart_queue_slot,
)


def _resolve_scheduled_at(user, post, schedule_intent: str, exact_datetime: str | None = None):
    platform = post.social_account.platform if post.social_account else None

    if schedule_intent == "post_now":
        return timezone.now(), True
    if schedule_intent == "next_best":
        return get_next_best_slot(user, platform), False
    if schedule_intent == "smart_queue":
        return get_smart_queue_slot(user), False
    if schedule_intent.startswith("quick:"):
        option = schedule_intent.split(":", 1)[1]
        return get_quick_schedule_time(option), False
    if schedule_intent == "exact" and exact_datetime:
        try:
            naive = dt.fromisoformat(exact_datetime)
            return timezone.make_aware(naive, timezone.get_current_timezone()), False
        except (ValueError, TypeError):
            pass
    return get_next_best_slot(user, platform), False


def approve_post_for_user(
    user,
    post,
    *,
    schedule_intent: str = "next_best",
    exact_datetime: str | None = None,
) -> dict:
    """Approve a single post. Returns {success, error, post_id, published_now}."""
    if post.user_id != user.pk:
        return {"success": False, "error": "not_owner", "post_id": str(post.id)}

    if post.status not in (Post.Status.DRAFT, Post.Status.PENDING_APPROVAL):
        return {"success": False, "error": "invalid_status", "post_id": str(post.id)}

    if post.needs_media:
        platform_name = (
            post.social_account.get_platform_display()
            if post.social_account else "This platform"
        )
        return {
            "success": False,
            "error": "needs_media",
            "post_id": str(post.id),
            "message": f"{platform_name} requires media before approval.",
        }

    scheduled_at, publish_now = _resolve_scheduled_at(
        user, post, schedule_intent, exact_datetime,
    )
    post.scheduled_at = scheduled_at
    post.status = Post.Status.APPROVED
    post.save(update_fields=["status", "scheduled_at", "updated_at"])

    if publish_now:
        from apps.content.tasks import publish_post
        from apps.utils import fire_task

        fire_task(publish_post, str(post.id))

    preview = (post.content_text or "")[:60].strip()
    return {
        "success": True,
        "post_id": str(post.id),
        "published_now": publish_now,
        "preview": preview,
        "platform": post.social_account.platform if post.social_account else "",
    }


def get_pending_posts(user, *, limit: int = 20):
    return list(
        Post.objects.filter(
            user=user,
            status__in=(Post.Status.DRAFT, Post.Status.PENDING_APPROVAL),
        )
        .select_related("social_account")
        .order_by("-created_at")[:limit]
    )


def approve_pending_posts(
    user,
    *,
    indices: list[int] | None = None,
    schedule_intent: str = "next_best",
) -> dict:
    """Approve pending posts by 1-based index, or all when indices is None."""
    posts = get_pending_posts(user)
    if not posts:
        return {"approved": 0, "skipped": 0, "errors": [], "posts": []}

    if indices is None:
        targets = posts
    else:
        targets = []
        for idx in indices:
            if 1 <= idx <= len(posts):
                targets.append(posts[idx - 1])

    approved = 0
    skipped = 0
    errors = []
    approved_posts = []

    for post in targets:
        result = approve_post_for_user(user, post, schedule_intent=schedule_intent)
        if result.get("success"):
            approved += 1
            approved_posts.append(result)
        elif result.get("error") == "needs_media":
            skipped += 1
            errors.append(result.get("message") or "Media required")
        else:
            skipped += 1

    return {
        "approved": approved,
        "skipped": skipped,
        "errors": errors,
        "posts": approved_posts,
        "total_pending": len(posts),
    }
