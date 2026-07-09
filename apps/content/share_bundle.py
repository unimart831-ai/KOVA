"""
Quick Share — multi-reel / multi-photo event workflows.

Groups user uploads under a ContentSeed + MarketingCampaign, assigns publish
order, and optionally auto-schedules for Autopilot.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

MAX_REEL_ITEMS = 10
MAX_PHOTO_ITEMS = 20
MAX_REEL_BYTES = 100 * 1024 * 1024
MAX_PHOTO_BYTES = 15 * 1024 * 1024

REEL_PLATFORMS = frozenset({"instagram", "facebook", "tiktok", "linkedin"})
CAROUSEL_PLATFORMS = frozenset({"instagram", "facebook", "linkedin"})
IMAGE_PLATFORMS = frozenset({"instagram", "facebook", "linkedin", "twitter", "tiktok", "whatsapp", "threads", "bluesky"})

PLATFORM_STAGGER_MINUTES = {
    "instagram": 0,
    "facebook": 10,
    "tiktok": 5,
    "linkedin": 15,
    "twitter": 8,
    "whatsapp": 12,
    "threads": 6,
    "bluesky": 7,
}


@dataclass
class ShareMediaItem:
    file_bytes: bytes
    filename: str
    content_type: str
    order: int
    kind: str  # "reel" | "photo"


@dataclass
class ShareBundleResult:
    seed_id: str
    campaign_id: str | None
    posts_created: int
    post_ids: list[str] = field(default_factory=list)
    autopilot_scheduled: bool = False


def campaign_rollout_minutes_for_post(post) -> int:
    """Sort key: sequence index dominates, then platform stagger."""
    dna = getattr(post, "content_dna", None) or {}
    seq = dna.get("publish_sequence_index")
    if seq is not None:
        plat = (post.platform or "").lower()
        return int(seq) * 1000 + PLATFORM_STAGGER_MINUTES.get(plat, 20)
    from apps.content.campaign_approval import campaign_rollout_minutes

    return campaign_rollout_minutes(post)


def _is_video(filename: str, content_type: str) -> bool:
    ct = (content_type or "").lower()
    name = (filename or "").lower()
    return ct.startswith("video/") or name.endswith((".mp4", ".mov", ".webm", ".m4v"))


def _is_image(filename: str, content_type: str) -> bool:
    ct = (content_type or "").lower()
    name = (filename or "").lower()
    return ct.startswith("image/") or name.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic"))


def parse_uploaded_files(file_list, *, kind_hint: str = "auto") -> list[ShareMediaItem]:
    """Parse and validate uploaded files; preserve client order."""
    items: list[ShareMediaItem] = []
    for idx, uploaded in enumerate(file_list):
        name = getattr(uploaded, "name", "") or f"upload_{idx}"
        ct = getattr(uploaded, "content_type", "") or ""
        data = uploaded.read()
        if _is_video(name, ct):
            if len(data) > MAX_REEL_BYTES:
                raise ValueError(f"{name} is too large (max 100MB per reel).")
            items.append(ShareMediaItem(data, name, ct, idx, "reel"))
        elif _is_image(name, ct):
            if len(data) > MAX_PHOTO_BYTES:
                raise ValueError(f"{name} is too large (max 15MB per photo).")
            items.append(ShareMediaItem(data, name, ct, idx, "photo"))
        else:
            raise ValueError(f"Unsupported file type: {name}")
    if not items:
        raise ValueError("Add at least one photo or video.")
    reels = sum(1 for i in items if i.kind == "reel")
    photos = sum(1 for i in items if i.kind == "photo")
    if reels and photos:
        raise ValueError("Mix reels and photos in separate shares — pick one type per batch.")
    if reels > MAX_REEL_ITEMS:
        raise ValueError(f"Maximum {MAX_REEL_ITEMS} reels per batch.")
    if photos > MAX_PHOTO_ITEMS:
        raise ValueError(f"Maximum {MAX_PHOTO_ITEMS} photos per batch.")
    if kind_hint == "reel" and photos:
        raise ValueError("This share is set to reels only.")
    if kind_hint == "photo" and reels:
        raise ValueError("This share is set to photos only.")
    return items


def apply_custom_order(items: list[ShareMediaItem], order_values: list[str]) -> list[ShareMediaItem]:
    """Reorder items using 1-based order numbers from the form."""
    if not order_values or len(order_values) != len(items):
        return items
    indexed = list(enumerate(items))
    try:
        indexed.sort(key=lambda pair: int(order_values[pair[0]] or pair[0] + 1))
    except (TypeError, ValueError):
        indexed.sort(key=lambda pair: pair[0])
    reordered = [item for _, item in indexed]
    for i, item in enumerate(reordered):
        item.order = i
    return reordered


def generate_share_caption(
    user,
    *,
    context: str,
    media_count: int,
    kind: str,
) -> str:
    """Lightweight caption when user leaves the field blank."""
    from apps.content.post_copy import polish_post_caption

    profile = getattr(user, "profile", None)
    business = ""
    if profile:
        business = (profile.company_name or profile.display_name or "").strip()
    ctx = (context or "").strip()
    if ctx:
        hook = ctx
    elif business:
        hook = f"Highlights from {business} ✨"
    else:
        hook = "Moments worth sharing ✨"

    if kind == "reel" and media_count > 1:
        body = f"{media_count} clips from the field — swipe through if you're on feed, or catch each reel as they go live."
    elif kind == "reel":
        body = "Fresh from today — tap through and let us know what you think."
    elif media_count > 1:
        body = f"{media_count} photos from today. Save the ones that resonate — more coming if you want the full set."
    else:
        body = "One shot we had to share."

    text = f"{hook}\n\n{body}"
    return polish_post_caption(text, "instagram", post_format="image" if kind == "photo" else "reel")


def _initial_post_status(user) -> str:
    from apps.content.models import Post
    from apps.products.commerce_autopilot import should_auto_publish_commerce

    if should_auto_publish_commerce(user):
        return Post.Status.APPROVED
    profile = getattr(user, "profile", None)
    if profile and profile.auto_approve_posts:
        return Post.Status.APPROVED
    return Post.Status.PENDING_APPROVAL


def _public_url_for_attachment(attachment) -> str:
    from apps.content.tasks import _public_url_for_file

    if attachment.file and attachment.file.name:
        url = _public_url_for_file(attachment.file.name, for_platform_api=True) or ""
        if url:
            return url
        try:
            return attachment.file.url or ""
        except Exception:
            pass
    return ""


def _attach_reel_to_post(post, item: ShareMediaItem, *, label: str) -> None:
    from apps.content.models import MediaAttachment, Post
    from apps.content.views.editing import _attach_user_reel_video

    ext = ".mp4"
    lower = item.filename.lower()
    if lower.endswith(".webm"):
        ext = ".webm"
    elif lower.endswith(".mov"):
        ext = ".mov"
    file_obj = ContentFile(item.file_bytes, name=f"share_reel_{item.order}{ext}")
    _attach_user_reel_video(post, file_obj, alt_text=label)


def _attach_image_to_post(post, item: ShareMediaItem, *, order: int = 0) -> str:
    from apps.content.models import MediaAttachment

    ext = ".jpg"
    lower = item.filename.lower()
    for candidate in (".png", ".webp", ".gif", ".jpeg", ".jpg"):
        if lower.endswith(candidate):
            ext = candidate if candidate != ".jpeg" else ".jpg"
            break
    file_obj = ContentFile(item.file_bytes, name=f"share_photo_{order}{ext}")
    attachment = MediaAttachment.objects.create(
        post=post,
        file=file_obj,
        file_type="image",
        alt_text=item.filename,
        order=order,
    )
    return _public_url_for_attachment(attachment)


def _carousel_format_for_platform(platform: str) -> bool:
    return (platform or "").lower() in CAROUSEL_PLATFORMS


@transaction.atomic
def create_share_bundle(
    user,
    accounts,
    items: list[ShareMediaItem],
    *,
    caption: str = "",
    context: str = "",
    schedule_mode: str = "autopilot",
    gap_hours: int = 4,
    photo_mode: str = "auto",
    generate_caption: bool = True,
) -> ShareBundleResult:
    """
    Create a grouped share campaign from user uploads.

    schedule_mode: autopilot | stagger | manual
    photo_mode: auto | carousel | sequence
    """
    from apps.content.campaigns import ensure_campaign_for_seed, sync_campaign_status_from_seed
    from apps.content.models import ContentSeed, MarketingCampaign, Post
    from apps.content.post_copy import polish_post_caption

    if not accounts:
        raise ValueError("Select at least one platform to publish to.")

    kind = items[0].kind
    media_count = len(items)

    if not (caption or "").strip() and generate_caption:
        caption = generate_share_caption(
            user, context=context, media_count=media_count, kind=kind,
        )
    caption = (caption or "New post ✨").strip()

    title = (context or caption).split("\n")[0][:200] or (
        f"{media_count} {'reels' if kind == 'reel' else 'photos'} share"
    )

    seed = ContentSeed.objects.create(
        user=user,
        idea=title,
        notes=context or f"Quick share — {media_count} {kind}(s)",
        status=ContentSeed.SeedStatus.COMPLETED,
        generate_images=False,
        target_platforms=[a.platform for a in accounts],
        blueprint={
            "share_bundle": True,
            "share_kind": kind,
            "media_count": media_count,
            "schedule_mode": schedule_mode,
            "gap_hours": gap_hours,
        },
    )
    campaign = ensure_campaign_for_seed(seed, title=title, objective="awareness")
    campaign.status = MarketingCampaign.Status.REVIEW
    campaign.save(update_fields=["status", "updated_at"])

    initial_status = (
        Post.Status.APPROVED
        if schedule_mode in ("autopilot", "stagger")
        else _initial_post_status(user)
    )
    posts: list[Post] = []

    if kind == "reel":
        for item in sorted(items, key=lambda x: x.order):
            for account in accounts:
                plat = account.platform
                post = Post.objects.create(
                    user=user,
                    social_account=account,
                    platform=plat,
                    seed=seed,
                    content_text=polish_post_caption(caption, plat, post_format="reel"),
                    content_type="original",
                    post_format=Post.PostFormat.REEL,
                    aspect_ratio=Post.AspectRatio.STORY,
                    status=initial_status,
                    generated_by_agent="user_share",
                    media_status=Post.MediaStatus.UPLOADED,
                    content_dna={
                        "share_bundle": True,
                        "publish_sequence_index": item.order,
                        "media_order": item.order + 1,
                        "bundle_role": f"share_reel_{item.order + 1}",
                    },
                    visual_metadata={
                        "reel_source": "user_upload",
                        "user_uploaded_reel": True,
                        "video_compose_status": "done",
                        "share_bundle_id": str(seed.id),
                    },
                )
                _attach_reel_to_post(
                    post, item, label=f"Reel {item.order + 1} of {media_count}",
                )
                posts.append(post)
    else:
        sorted_items = sorted(items, key=lambda x: x.order)
        want_carousel = photo_mode == "carousel" or (photo_mode == "auto" and media_count > 1)

        for account in accounts:
            plat = account.platform
            if want_carousel and media_count > 1 and _carousel_format_for_platform(plat):
                post = Post.objects.create(
                    user=user,
                    social_account=account,
                    platform=plat,
                    seed=seed,
                    content_text=polish_post_caption(caption, plat, post_format="carousel"),
                    content_type="original",
                    post_format=Post.PostFormat.CAROUSEL,
                    aspect_ratio=Post.AspectRatio.SQUARE,
                    status=initial_status,
                    generated_by_agent="user_share",
                    media_status=Post.MediaStatus.UPLOADED,
                    content_dna={
                        "share_bundle": True,
                        "publish_sequence_index": 0,
                        "bundle_role": "share_carousel",
                    },
                    visual_metadata={"share_bundle_id": str(seed.id)},
                    visual_strategy="carousel",
                )
                urls: list[str] = []
                slides: list[dict] = []
                for idx, item in enumerate(sorted_items):
                    url = _attach_image_to_post(post, item, order=idx)
                    if url:
                        urls.append(url)
                        slides.append({"image_url": url, "heading": "", "body": ""})
                post.media_urls = urls
                post.carousel_slides = slides
                post.save(update_fields=["media_urls", "carousel_slides", "updated_at"])
                posts.append(post)
            else:
                for item in sorted_items:
                    if plat not in IMAGE_PLATFORMS:
                        continue
                    post = Post.objects.create(
                        user=user,
                        social_account=account,
                        platform=plat,
                        seed=seed,
                        content_text=polish_post_caption(caption, plat, post_format="image"),
                        content_type="original",
                        post_format=Post.PostFormat.IMAGE,
                        aspect_ratio=Post.AspectRatio.SQUARE,
                        status=initial_status,
                        generated_by_agent="user_share",
                        media_status=Post.MediaStatus.UPLOADED,
                        content_dna={
                            "share_bundle": True,
                            "publish_sequence_index": item.order,
                            "media_order": item.order + 1,
                            "bundle_role": f"share_photo_{item.order + 1}",
                        },
                        visual_metadata={"share_bundle_id": str(seed.id)},
                    )
                    url = _attach_image_to_post(post, item)
                    if url:
                        post.media_urls = [url]
                        post.save(update_fields=["media_urls", "updated_at"])
                    posts.append(post)

    if schedule_mode in ("autopilot", "stagger"):
        _schedule_share_posts(
            user,
            posts,
            gap_hours=gap_hours,
            publish_first=(schedule_mode == "autopilot"),
        )
        autopilot = True
    else:
        autopilot = False

    sync_campaign_status_from_seed(seed)
    logger.info(
        "Share bundle %s: %d posts for user %s (%s, mode=%s)",
        seed.id, len(posts), user.pk, kind, schedule_mode,
    )
    return ShareBundleResult(
        seed_id=str(seed.id),
        campaign_id=str(campaign.pk) if campaign else None,
        posts_created=len(posts),
        post_ids=[str(p.id) for p in posts],
        autopilot_scheduled=autopilot,
    )


def _schedule_share_posts(user, posts, *, gap_hours: int = 4, publish_first: bool = False) -> None:
    """Assign staggered scheduled_at times ordered by publish_sequence_index."""
    from datetime import timedelta

    from apps.accounts.autopilot_helpers import mark_user_scheduled_publish
    from apps.content.models import Post
    from apps.content.scheduling import get_next_best_slot

    if not posts:
        return

    gap_hours = max(1, min(int(gap_hours or 4), 168))
    gap_minutes = gap_hours * 60
    sorted_posts = sorted(posts, key=campaign_rollout_minutes_for_post)

    lead = sorted_posts[0]
    lead_platform = lead.social_account.platform if lead.social_account else None
    anchor = get_next_best_slot(user, lead_platform)
    if publish_first:
        anchor = timezone.now() + timedelta(minutes=2)

    for post in sorted_posts:
        dna = post.content_dna or {}
        seq = int(dna.get("publish_sequence_index", 0))
        plat = (post.platform or "").lower()
        rollout = seq * gap_minutes + PLATFORM_STAGGER_MINUTES.get(plat, 15)
        post.scheduled_at = anchor + timedelta(minutes=rollout)
        post.status = Post.Status.SCHEDULED
        mark_user_scheduled_publish(post)
        post.save(update_fields=["scheduled_at", "status", "visual_metadata", "updated_at"])
