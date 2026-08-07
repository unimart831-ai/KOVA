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
    from apps.create.content.campaign_approval import campaign_rollout_minutes

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


def infer_share_context(items: list[ShareMediaItem]) -> str:
    """Build a human context line from upload filenames when the user adds none."""
    import re
    from django.utils import timezone

    if not items:
        return f"Shared {timezone.now().strftime('%A %b %d')}"

    raw = (items[0].filename or "").rsplit(".", 1)[0]
    cleaned = re.sub(r"[_\-]+", " ", raw).strip()
    cleaned = re.sub(r"\s*\(\d+\)\s*$", "", cleaned).strip()
    if cleaned and not is_meaningless_share_label(cleaned):
        title = cleaned.title() if cleaned.islower() else cleaned
        return title[:120]
    return f"Shared {timezone.now().strftime('%A %b %d')}"


def is_meaningless_share_label(text: str) -> bool:
    """True when a title/caption hook is auto-generated noise (e.g. IMG_738389)."""
    import re

    t = (text or "").strip()
    if not t or len(t) < 3:
        return True
    if re.fullmatch(r"\d+", t):
        return True
    lower = t.lower().replace(" ", "").replace("_", "").replace("-", "")
    noise_prefixes = ("img", "dsc", "photo", "image", "screenshot", "vid", "mvimg", "snap")
    if any(lower.startswith(p) and sum(c.isdigit() for c in lower) >= 3 for p in noise_prefixes):
        return True
    if len(t) >= 4 and sum(c.isdigit() for c in t) / len(t) > 0.75:
        return True
    return False


def human_share_title(seed, posts, *, user=None) -> str:
    """User-facing bundle title — never raw numeric filenames."""
    blueprint = seed.blueprint or {}
    kind = blueprint.get("share_kind", "photo")
    media_count = blueprint.get("media_count", len(posts))

    idea = (seed.idea or "").split("\n")[0].strip()
    if idea and not is_meaningless_share_label(idea) and "·" in idea:
        return idea[:120]
    if idea and not is_meaningless_share_label(idea):
        generic_prefixes = ("fresh from", "moments worth", "shared ", "highlights from", "new post")
        if not any(idea.lower().startswith(p) for p in generic_prefixes):
            return idea[:120]

    campaign = getattr(seed, "marketing_campaign", None)
    if campaign and (campaign.title or "").strip():
        camp_title = campaign.title.strip()
        if not is_meaningless_share_label(camp_title):
            return camp_title[:120]

    profile = getattr(user or getattr(seed, "user", None), "profile", None)
    business = _profile_business_name(user or seed.user, profile)

    when = seed.created_at.strftime("%b %d") if seed.created_at else "today"
    if kind == "reel":
        label = f"{media_count} reels" if media_count > 1 else "New reel"
    elif media_count > 1:
        label = f"{media_count}-photo carousel"
    else:
        label = "Photo share"

    if business:
        return f"{label} · {business} · {when}"
    return f"{label} · {when}"


def display_share_caption(seed, posts, *, user=None) -> str:
    """Caption for the bundle editor — strips meaningless leading lines."""
    if not posts:
        return ""

    raw = (posts[0].content_text or "").strip()
    lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
    while lines and is_meaningless_share_label(lines[0]):
        lines.pop(0)
    cleaned = "\n\n".join(lines).strip()

    if cleaned and len(cleaned) >= 24:
        return cleaned

    blueprint = seed.blueprint or {}
    return generate_share_caption(
        user or seed.user,
        context=seed.notes or "",
        media_count=blueprint.get("media_count", len(posts)),
        kind=blueprint.get("share_kind", "photo"),
    )


def share_bundle_summary_line(seed, posts, *, user=None) -> str:
    """One-line explanation of what Kova did with this upload."""
    blueprint = seed.blueprint or {}
    kind = blueprint.get("share_kind", "photo")
    media_count = blueprint.get("media_count", len(posts))
    platforms = sorted({p.platform for p in posts if p.platform})
    plat_label = ", ".join(p.title() for p in platforms) if platforms else "your platforms"

    if kind == "reel":
        media_phrase = f"{media_count} clips" if media_count > 1 else "your reel"
        action = f"queued reel posts for {plat_label}"
    elif media_count > 1 and any(p.post_format == "carousel" for p in posts):
        action = f"built a {media_count}-photo carousel for {plat_label}"
    elif media_count > 1:
        action = f"split {media_count} photos across {plat_label}"
    else:
        action = f"prepared a post for {plat_label}"

    mode = blueprint.get("schedule_mode", "manual")
    if mode in ("autopilot", "stagger"):
        schedule_phrase = "and staggered publish times"
    else:
        schedule_phrase = "ready for you to approve"

    return f"You uploaded {media_phrase} — Kova {action} {schedule_phrase}."


def resolve_automated_share_options(
    user,
    items: list[ShareMediaItem],
    *,
    context: str = "",
    caption: str = "",
) -> dict:
    """
    Hands-free Quick Share defaults — platforms, caption, layout, and schedule
    without asking the user to configure anything.
    """
    from apps.core.accounts.autopilot_helpers import should_auto_publish_approved
    from apps.commerce.products.commerce_autopilot import should_auto_publish_commerce

    profile = getattr(user, "profile", None)
    media_count = len(items)
    kind = items[0].kind if items else "photo"

    hands_free = bool(
        should_auto_publish_commerce(user)
        or should_auto_publish_approved(user)
        or (profile and profile.auto_approve_posts)
    )
    schedule_mode = "autopilot" if hands_free else "stagger"

    if media_count >= 6:
        gap_hours = 2
    elif media_count >= 3:
        gap_hours = 3
    else:
        gap_hours = 4

    inferred = infer_share_context(items)
    ctx = (context or "").strip() or inferred

    return {
        "share_kind": "auto",
        "schedule_mode": schedule_mode,
        "photo_mode": "auto",
        "gap_hours": gap_hours,
        "generate_caption": not (caption or "").strip(),
        "context": ctx,
        "caption": (caption or "").strip(),
    }


def _profile_business_name(user, profile=None) -> str:
    profile = profile or getattr(user, "profile", None)
    if profile and (profile.company_name or "").strip():
        return profile.company_name.strip()
    full = (user.get_full_name() or "").strip() if user else ""
    if full:
        return full
    return (getattr(user, "username", "") or "").strip()


def filter_accounts_for_share_items(accounts, items: list[ShareMediaItem]):
    """Keep only platforms that can publish this media type."""
    if not items:
        return accounts
    kind = items[0].kind
    if kind == "reel":
        return [a for a in accounts if a.platform in REEL_PLATFORMS]
    return [a for a in accounts if a.platform in IMAGE_PLATFORMS]


def generate_share_caption(
    user,
    *,
    context: str,
    media_count: int,
    kind: str,
) -> str:
    """Lightweight caption when user leaves the field blank."""
    from apps.create.content.post_copy import polish_post_caption

    business = _profile_business_name(user)
    ctx = (context or "").strip()
    if ctx and not is_meaningless_share_label(ctx):
        hook = ctx
    elif business:
        hook = f"Fresh from {business}"
    else:
        hook = "Moments worth sharing"

    if kind == "reel" and media_count > 1:
        body = (
            f"{media_count} clips from today — watch each reel as it goes live, "
            "or catch the full set on your feed."
        )
    elif kind == "reel":
        body = "New reel — tap through and tell us what you think."
    elif media_count >= 6:
        body = (
            f"{media_count} looks from today's session. "
            "Swipe the carousel and save your favourites."
        )
    elif media_count > 1:
        body = (
            f"{media_count} photos from today — swipe through and "
            "let us know which one hits."
        )
    else:
        body = "One shot we had to share with you."

    text = f"{hook}\n\n{body}"
    return polish_post_caption(text, "instagram", post_format="image" if kind == "photo" else "reel")


def _initial_post_status(user) -> str:
    from apps.create.content.models import Post
    from apps.commerce.products.commerce_autopilot import should_auto_publish_commerce

    if should_auto_publish_commerce(user):
        return Post.Status.APPROVED
    profile = getattr(user, "profile", None)
    if profile and profile.auto_approve_posts:
        return Post.Status.APPROVED
    return Post.Status.PENDING_APPROVAL


def _public_url_for_attachment(attachment) -> str:
    from apps.create.content.tasks import _public_url_for_file

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
    from apps.create.content.models import MediaAttachment, Post
    from apps.create.content.views.editing import _attach_user_reel_video

    ext = ".mp4"
    lower = item.filename.lower()
    if lower.endswith(".webm"):
        ext = ".webm"
    elif lower.endswith(".mov"):
        ext = ".mov"
    file_obj = ContentFile(item.file_bytes, name=f"share_reel_{item.order}{ext}")
    _attach_user_reel_video(post, file_obj, alt_text=label)


def _attach_image_to_post(post, item: ShareMediaItem, *, order: int = 0) -> str:
    from apps.create.content.models import MediaAttachment

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
    from apps.create.content.campaigns import ensure_campaign_for_seed, sync_campaign_status_from_seed
    from apps.create.content.models import ContentSeed, MarketingCampaign, Post
    from apps.create.content.post_copy import polish_post_caption

    if not accounts:
        raise ValueError("Select at least one platform to publish to.")

    kind = items[0].kind
    media_count = len(items)

    if not (caption or "").strip() and generate_caption:
        caption = generate_share_caption(
            user, context=context, media_count=media_count, kind=kind,
        )
    caption = (caption or "New post ✨").strip()

    ctx = (context or "").strip()
    if ctx and not is_meaningless_share_label(ctx):
        title = ctx[:200]
    else:
        business = _profile_business_name(user)
        when = timezone.now().strftime("%b %d")
        if kind == "reel":
            label = f"{media_count} reels" if media_count > 1 else "New reel"
        elif media_count > 1:
            label = f"{media_count}-photo carousel"
        else:
            label = "Photo share"
        title = f"{label} · {business} · {when}" if business else f"{label} · {when}"

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

    from apps.core.accounts.autopilot_helpers import mark_user_scheduled_publish
    from apps.create.content.models import Post
    from apps.create.content.scheduling import get_next_best_slot

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


def is_share_bundle_seed(seed) -> bool:
    if not seed:
        return False
    blueprint = getattr(seed, "blueprint", None) or {}
    return bool(blueprint.get("share_bundle"))


def share_bundle_seed_ids_for_users(user_ids) -> list:
    """Seed IDs for Quick Share bundles — used to exclude from Studio/Queue."""
    from apps.create.content.models import ContentSeed

    return list(
        ContentSeed.objects.filter(
            user_id__in=user_ids,
            blueprint__share_bundle=True,
        ).values_list("id", flat=True)
    )


def exclude_share_bundle_posts(qs, user_ids):
    """Remove Quick Share posts from a queryset (they live on the Shares pages)."""
    seed_ids = share_bundle_seed_ids_for_users(user_ids)
    if not seed_ids:
        return qs
    return qs.exclude(seed_id__in=seed_ids)


def _share_status_counts(posts) -> dict:
    counts = {
        "pending": 0,
        "scheduled": 0,
        "published": 0,
        "failed": 0,
        "publishing": 0,
        "other": 0,
    }
    for post in posts:
        status = post.status
        if status in ("draft", "pending_approval"):
            counts["pending"] += 1
        elif status == "published":
            counts["published"] += 1
        elif status in ("failed", "blocked", "rate_limited"):
            counts["failed"] += 1
        elif status == "publishing":
            counts["publishing"] += 1
        elif status in ("approved", "scheduled") or post.scheduled_at:
            counts["scheduled"] += 1
        else:
            counts["other"] += 1
    return counts


def summarize_share_bundle(seed, posts) -> dict:
    """Lightweight summary for list cards."""
    blueprint = seed.blueprint or {}
    posts = list(posts)
    platforms = sorted({p.platform for p in posts if p.platform})
    counts = _share_status_counts(posts)
    attention = counts["pending"] + counts["failed"] + counts["publishing"]
    display_title = human_share_title(seed, posts, user=getattr(seed, "user", None))
    return {
        "seed": seed,
        "title": display_title,
        "display_title": display_title,
        "share_kind": blueprint.get("share_kind", "photo"),
        "media_count": blueprint.get("media_count", len(posts)),
        "schedule_mode": blueprint.get("schedule_mode", "manual"),
        "gap_hours": blueprint.get("gap_hours", 4),
        "platforms": platforms,
        "platform_count": len(platforms),
        "post_count": len(posts),
        "counts": counts,
        "needs_attention": attention > 0,
        "attention_count": attention,
        "created_at": seed.created_at,
        "all_published": counts["published"] == len(posts) and len(posts) > 0,
    }


def build_share_bundle_detail(seed, posts) -> dict:
    """Full detail context for a single Quick Share bundle."""
    from apps.create.content.campaign_approval import campaign_approval_summary

    blueprint = seed.blueprint or {}
    posts = sorted(
        list(posts),
        key=lambda p: (
            campaign_rollout_minutes_for_post(p),
            p.platform or "",
        ),
    )
    summary = summarize_share_bundle(seed, posts)
    campaign = getattr(seed, "marketing_campaign", None)
    approval = campaign_approval_summary(posts, bundle=None)

    timeline = []
    for post in posts:
        dna = post.content_dna or {}
        media_order = dna.get("media_order") or (dna.get("publish_sequence_index", 0) + 1)
        timeline.append({
            "post": post,
            "sequence_index": dna.get("publish_sequence_index", 0),
            "media_order": media_order,
            "bundle_role": dna.get("bundle_role", ""),
        })

    return {
        **summary,
        "campaign": campaign,
        "posts": posts,
        "timeline": timeline,
        "title": summary["display_title"],
        "caption": display_share_caption(seed, posts, user=seed.user),
        "context": seed.notes or "",
        "summary_line": share_bundle_summary_line(seed, posts, user=seed.user),
        "approval": approval,
        "can_approve_all": approval.get("can_approve_campaign", False),
        "can_reschedule": any(
            p.status in ("approved", "scheduled", "draft", "pending_approval")
            for p in posts
        ),
    }


def reschedule_share_bundle(user, seed, *, gap_hours: int = 4, publish_first: bool = False) -> int:
    """Re-stagger all reschedule-eligible posts in a share bundle."""
    from apps.create.content.models import Post

    posts = list(
        Post.objects.filter(
            seed=seed,
            user=user,
            generated_by_agent="user_share",
        ).select_related("social_account")
    )
    eligible = [
        p for p in posts
        if p.status in (
            Post.Status.APPROVED,
            Post.Status.SCHEDULED,
            Post.Status.DRAFT,
            Post.Status.PENDING_APPROVAL,
        )
    ]
    if not eligible:
        return 0
    _schedule_share_posts(user, eligible, gap_hours=gap_hours, publish_first=publish_first)
    return len(eligible)

