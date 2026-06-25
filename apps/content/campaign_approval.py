"""
Campaign-level approval — approve an entire marketing package in one action.

Wraps post scheduling with bundle-aware rollout order (reel → stories → feed → carousel)
and keeps MarketingCampaign status in sync.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from django.utils import timezone

logger = logging.getLogger(__name__)

PENDING_STATUSES = ("draft", "pending_approval")

# Minutes after campaign anchor time — reel leads, stories follow, carousel spreads.
ROLL_OUT_MINUTES: dict[str, int] = {
    "primary_reel": 0,
    "tiktok_copy": 5,
    "ig_feed": 90,
    "fb_feed": 120,
    "ig_story_1": 20,
    "ig_story_2": 1440,
    "ig_story_3": 2880,
    "ig_carousel": 360,
    "linkedin_copy": 180,
}

FORMAT_ROLL_OUT = {
    "reel": 0,
    "story": 25,
    "image": 90,
    "carousel": 360,
    "text": 120,
}


@dataclass
class CampaignApproveResult:
    approved_count: int = 0
    skipped_media: int = 0
    post_now_ids: list[str] = field(default_factory=list)
    approved_post_ids: list[str] = field(default_factory=list)


def campaign_rollout_minutes(post) -> int:
    """Sort key — lower publishes earlier in the campaign rollout."""
    dna = getattr(post, "content_dna", None) or {}
    role = (dna.get("bundle_role") or "").strip()
    if role in ROLL_OUT_MINUTES:
        return ROLL_OUT_MINUTES[role]
    fmt = getattr(post, "post_format", "") or ""
    return FORMAT_ROLL_OUT.get(fmt, 200)


def _pending_posts(posts):
    return [p for p in posts if p.status in PENDING_STATUSES]


def _approvable_posts(posts):
    return [p for p in _pending_posts(posts) if not p.needs_media]


def campaign_approval_summary(posts: list, *, bundle: dict | None = None) -> dict[str, Any]:
    """Metadata for Studio campaign approve button and modal."""
    pending = _pending_posts(posts)
    approvable = _approvable_posts(posts)
    blocked = [p for p in pending if p.needs_media]
    total = len(posts)

    bundle = bundle or {}
    bundle_ready = bundle.get("ready_count", 0)
    bundle_total = bundle.get("total_count", 0)

    subtitle_parts = []
    if approvable:
        subtitle_parts.append(f"{len(approvable)} post{'s' if len(approvable) != 1 else ''} ready")
    if bundle_total:
        subtitle_parts.append(f"{bundle_ready}/{bundle_total} package items")
    if blocked:
        subtitle_parts.append(f"{len(blocked)} waiting on images")

    return {
        "can_approve_campaign": len(approvable) > 0,
        "approvable_count": len(approvable),
        "pending_count": len(pending),
        "media_blocked_count": len(blocked),
        "total_posts": total,
        "approve_label": "Approve campaign",
        "modal_title": "Approve entire campaign",
        "modal_subtitle": " · ".join(subtitle_parts) if subtitle_parts else "Schedule all deliverables at once",
        "all_pending": len(pending) == total and total > 0,
        "partial_ready": 0 < len(approvable) < len(pending),
    }


def _resolve_post_schedule(
    user,
    post,
    intent: str,
    *,
    exact_datetime: str | None = None,
    anchor: datetime | None = None,
    rollout_minutes: int | None = None,
) -> datetime:
    """Resolve scheduled_at for one post."""
    from apps.content.scheduling import (
        get_next_best_slot,
        get_quick_schedule_time,
        get_smart_queue_slot,
    )

    platform = post.social_account.platform if post.social_account else None
    now = timezone.now()

    if anchor is not None and rollout_minutes is not None:
        return anchor + timedelta(minutes=rollout_minutes)

    if intent == "post_now":
        return now
    if intent == "next_best":
        return get_next_best_slot(user, platform)
    if intent == "smart_queue":
        return get_smart_queue_slot(user)
    if intent.startswith("quick:"):
        return get_quick_schedule_time(intent.split(":", 1)[1])
    if intent == "exact":
        if exact_datetime:
            try:
                from datetime import datetime as dt

                naive = dt.fromisoformat(exact_datetime)
                return timezone.make_aware(naive, timezone.get_current_timezone())
            except (ValueError, TypeError):
                pass
        return get_next_best_slot(user, platform)
    return get_next_best_slot(user, platform)


def _use_campaign_stagger(intent: str, approvable: list) -> bool:
    return intent in ("post_now", "next_best", "smart_queue") and len(approvable) > 1


def client_approval_status(campaign) -> dict:
    """Return client approval metadata from MarketingCampaign.proposal_meta."""
    if not campaign:
        return {}
    meta = getattr(campaign, "proposal_meta", None) or {}
    return dict(meta.get("client_approval") or {})


def client_approval_blocks_publish(campaign, user) -> tuple[bool, str]:
    """
    Block agency publish when client sign-off is pending.
    Client-role users may approve even while pending.
    """
    status = client_approval_status(campaign).get("status")
    if status != "pending":
        return False, ""
    from apps.teams.permissions import get_client_membership

    if get_client_membership(user):
        return False, ""
    return True, "Client approval is pending — send to client or wait for sign-off."


def approve_campaign_posts(
    user,
    posts,
    intent: str,
    *,
    exact_datetime: str | None = None,
) -> CampaignApproveResult:
    """
    Approve all ready posts in a campaign with bundle-aware scheduling.

    Posts blocked on media are skipped. Returns counts and IDs for publish queue.
    """
    from apps.content.models import Post

    result = CampaignApproveResult()
    approvable = _approvable_posts(posts)
    pending = _pending_posts(posts)
    result.skipped_media = len(pending) - len(approvable)

    if not approvable:
        return result

    stagger = _use_campaign_stagger(intent, approvable)
    sorted_posts = sorted(approvable, key=campaign_rollout_minutes)

    anchor = None
    if stagger and intent in ("next_best", "smart_queue"):
        lead = sorted_posts[0]
        lead_platform = lead.social_account.platform if lead.social_account else None
        if intent == "next_best":
            anchor = _resolve_post_schedule(user, lead, "next_best")
        else:
            anchor = _resolve_post_schedule(user, lead, "smart_queue")
        logger.info(
            "Campaign approve: staggered rollout from %s for %d posts (platform=%s)",
            anchor.isoformat(), len(sorted_posts), lead_platform,
        )
    elif stagger and intent == "post_now":
        anchor = timezone.now()

    for post in sorted_posts:
        rollout = campaign_rollout_minutes(post) if stagger else None
        scheduled_at = _resolve_post_schedule(
            user,
            post,
            intent,
            exact_datetime=exact_datetime,
            anchor=anchor,
            rollout_minutes=rollout,
        )

        post.scheduled_at = scheduled_at
        post.status = Post.Status.APPROVED
        post.save(update_fields=["status", "scheduled_at", "updated_at"])
        result.approved_count += 1
        result.approved_post_ids.append(str(post.pk))

        if intent == "post_now":
            result.post_now_ids.append(str(post.pk))

    return result


def sync_campaign_after_approval(campaign, seed) -> None:
    """Update MarketingCampaign status after posts are approved or published."""
    if not campaign:
        return

    from apps.content.models import MarketingCampaign, Post

    statuses = set(
        Post.objects.filter(seed=seed).values_list("status", flat=True)
    )
    if not statuses:
        return

    pending = statuses.intersection({Post.Status.DRAFT, Post.Status.PENDING_APPROVAL})
    has_published = Post.Status.PUBLISHED in statuses
    has_approved = statuses.intersection({
        Post.Status.APPROVED,
        Post.Status.SCHEDULED,
        Post.Status.PUBLISHED,
    })

    new_status = campaign.status
    if has_published and not pending:
        new_status = MarketingCampaign.Status.PUBLISHED
    elif not pending and has_approved:
        new_status = MarketingCampaign.Status.APPROVED
    elif has_approved:
        new_status = MarketingCampaign.Status.APPROVED

    if new_status != campaign.status:
        campaign.status = new_status
        campaign.save(update_fields=["status", "updated_at"])
        logger.info("Campaign %s status → %s after approval", campaign.pk, new_status)


def approval_flash_messages(result: CampaignApproveResult) -> list[tuple[str, str]]:
    """Return Django messages (level, text) tuples for the view."""
    if result.approved_count == 0 and result.skipped_media:
        return [(
            "warning",
            f"No posts approved — {result.skipped_media} need images before they can go live.",
        )]
    if result.skipped_media:
        return [(
            "warning",
            f"Campaign approved — {result.approved_count} posts scheduled. "
            f"{result.skipped_media} skipped until images are ready.",
        )]
    if result.approved_count:
        return [(
            "success",
            f"Campaign approved — {result.approved_count} posts scheduled and ready to publish!",
        )]
    return []
