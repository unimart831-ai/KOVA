"""
Celery tasks for the content app.

Handles async content generation via the Create Agent,
auto-publishing at scheduled times, and metrics fetching.
"""

import logging
import re
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

import unicodedata

import sentry_sdk
from celery import shared_task
from django.utils import timezone

from apps.utils.locks import single_run

logger = logging.getLogger(__name__)


# ── Content sanitizer ─────────────────────────────────────────────────────
# LLMs occasionally emit invisible Unicode characters (zero-width spaces,
# soft hyphens, BOM markers) that are invisible in our UI but cause platform
# APIs — especially LinkedIn — to silently truncate the post at that point.

_ZERO_WIDTH_CHARS = frozenset({
    '​',  # zero-width space
    '‌',  # zero-width non-joiner
    '‍',  # zero-width joiner
    '\u200E',  # left-to-right mark
    '\u200F',  # right-to-left mark
    '­',  # soft hyphen
    '﻿',  # BOM / zero-width no-break space
    ' ',  # line separator (breaks JSON parsers)
    ' ',  # paragraph separator (breaks JSON parsers)
})


def sanitize_content(content: str) -> str:
    """Strip invisible Unicode control characters that cause platform truncation.

    Keeps all printable characters, newlines, and tabs intact.
    Normalises Windows line endings to Unix so downstream code is consistent.
    """
    if not content:
        return content
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    chars = []
    for ch in content:
        if ch in _ZERO_WIDTH_CHARS:
            continue
        cat = unicodedata.category(ch)
        if ch in ('\n', '\t') or cat[0] != 'C':
            chars.append(ch)
    return ''.join(chars)


# Platforms that do not render markdown — asterisks/underscores appear literally.
_PLAIN_TEXT_PLATFORMS = frozenset({"linkedin", "facebook", "instagram", "tiktok", "whatsapp"})


def strip_markdown(content: str) -> str:
    """Remove LLM-generated markdown syntax that renders as literal characters
    on social platforms.

    Handles: **bold**, *italic*, __underline__, _italic_, `code`.
    Leaves hashtags, numbered lists, emojis, and newlines untouched.
    """
    if not content:
        return content
    # Bold (**text** or __text__)
    content = re.sub(r'\*\*(.+?)\*\*', r'\1', content, flags=re.DOTALL)
    content = re.sub(r'__(.+?)__', r'\1', content, flags=re.DOTALL)
    # Italic (*text* or _text_) — only match single delimiters not already consumed
    content = re.sub(r'\*([^*\n]+?)\*', r'\1', content)
    content = re.sub(r'(?<!\w)_([^_\n]+?)_(?!\w)', r'\1', content)
    # Inline code (`text`)
    content = re.sub(r'`([^`\n]+?)`', r'\1', content)
    return content


# ── Media URL helpers ────────────────────────────────────────────────────

def _public_url_for_file(file_name: str):
    """
    Generate a publicly accessible URL for a file in storage.

    Prefers the public URL from default_storage (uses AWS_S3_CUSTOM_DOMAIN
    when configured, giving a clean URL that any platform API can download).
    Falls back to constructing the URL from R2 env vars directly (handles
    cases where the Celery worker's default_storage differs from web).
    Returns None if no public URL can be constructed.
    """
    import os
    from django.core.files.storage import default_storage
    from django.conf import settings

    try:
        # Prefer the public URL (uses custom domain like pub-xxx.r2.dev)
        url = default_storage.url(file_name)
        if url.startswith(("http://", "https://")):
            return url

        # S3/R2 fallback: generate a pre-signed URL (1 hour expiry)
        try:
            from storages.backends.s3boto3 import S3Boto3Storage
            if isinstance(default_storage, S3Boto3Storage):
                key = default_storage._normalize_name(
                    default_storage._clean_name(file_name)
                )
                return default_storage.connection.meta.client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": default_storage.bucket_name, "Key": key},
                    ExpiresIn=3600,
                )
        except ImportError:
            pass

        # R2 fallback: construct URL from env vars directly (works even
        # when default_storage is FileSystemStorage but R2 is configured)
        custom_domain = (
            getattr(settings, "AWS_S3_CUSTOM_DOMAIN", "")
            or os.environ.get("AWS_S3_CUSTOM_DOMAIN", "")
        )
        if custom_domain:
            location = (
                getattr(settings, "AWS_LOCATION", "")
                or os.environ.get("AWS_LOCATION", "media")
            )
            prefix = f"{location}/" if location else ""
            return f"https://{custom_domain}/{prefix}{file_name}"

        # Last resort: SITE_URL + relative path
        site_url = getattr(settings, "SITE_URL", "").rstrip("/")
        if site_url and "localhost" not in site_url:
            return f"{site_url}{url}"
    except Exception as e:
        logger.warning("Could not generate public URL for %s: %s", file_name, e)
    return None


# ── Motion Reel helpers ──────────────────────────────────────────────────

def _is_video_url(url: str) -> bool:
    from apps.content.video_compose import is_video_url
    return is_video_url(url or "")


def _resolve_tiktok_privacy(account) -> str:
    """Privacy level for TikTok Direct Post — defaults to SELF_ONLY until app audit."""
    from django.conf import settings

    meta = account.metadata or {}
    level = meta.get("default_privacy_level") or getattr(
        settings, "TIKTOK_DEFAULT_PRIVACY_LEVEL", "",
    )
    return level or "SELF_ONLY"


def _reel_video_url(media_urls):
    if not media_urls:
        return None
    return next((u for u in media_urls if _is_video_url(u)), None)


def _post_has_reel_video(post) -> bool:
    for url in post.media_urls or []:
        if _is_video_url(url):
            return True
    return post.attachments.filter(file_type="video").exists()


def _resolve_absolute_media_urls(post, *, is_carousel_post: bool = False) -> list[str]:
    """
    Build ordered HTTPS URLs for platform APIs (Instagram Container, etc.).

    Relative ``attachment.file.url`` values are replaced with storage/CDN URLs.
    """
    urls: list[str] = []
    seen: set[str] = set()

    def _add(url: str | None) -> None:
        if not url:
            return
        if url.startswith(("http://", "https://")):
            if url not in seen:
                seen.add(url)
                urls.append(url)
            return
        public = _public_url_for_file(url.lstrip("/"))
        if public and public not in seen:
            seen.add(public)
            urls.append(public)

    if is_carousel_post:
        for attachment in post.attachments.filter(file_type="image").order_by("order"):
            if attachment.file:
                _add(_public_url_for_file(attachment.file.name))
        if urls:
            return urls

    for raw in post.media_urls or []:
        _add(raw)

    for attachment in post.attachments.order_by("order"):
        if attachment.file and attachment.file_type != "video":
            _add(_public_url_for_file(attachment.file.name))

    return urls


def _normalize_reel_image_source(source: str) -> str:
    """Return an absolute URL or local path FFmpeg can read."""
    if not source:
        return source
    if source.startswith(("http://", "https://")):
        return source
    from django.conf import settings

    if source.startswith("/"):
        site = getattr(settings, "SITE_URL", "").rstrip("/")
        if site and "localhost" not in site:
            return f"{site}{source}"
        media_url = getattr(settings, "MEDIA_URL", "/media/").rstrip("/")
        if source.startswith(media_url + "/") or source.startswith(media_url):
            rel = source[len(media_url):].lstrip("/")
            public = _public_url_for_file(rel)
            if public:
                return public
    public = _public_url_for_file(source.lstrip("/"))
    if public:
        return public
    return source


def _collect_reel_image_sources(post) -> list[str]:
    """Gather ordered image URLs/paths for reel composition."""
    meta = post.visual_metadata or {}

    source_images = meta.get("source_images") or []
    if source_images:
        return [_normalize_reel_image_source(u) for u in source_images if u and not _is_video_url(u)]

    # Prefer Photoroom 9:16 story variants if available (no blur-letterbox needed)
    if post.product:
        story_urls = [
            u for u in (post.product.additional_images or [])
            if u and "channel_story" in u
        ]
        if story_urls:
            normalized = [_normalize_reel_image_source(u) for u in story_urls if u]
            if len(normalized) >= 1:
                # Use story-optimized frames + original sources for variety
                combined = normalized[:3] + [
                    _normalize_reel_image_source(u) for u in source_images if u
                ]
                return [u for u in combined if u][:8]

    slide_urls = [
        _normalize_reel_image_source(s.get("image_url"))
        for s in (post.carousel_slides or [])
        if isinstance(s, dict) and s.get("image_url")
    ]
    if slide_urls:
        return slide_urls

    urls = [_normalize_reel_image_source(u) for u in (post.media_urls or []) if u and not _is_video_url(u)]
    if urls:
        return urls

    from django.core.files.storage import default_storage

    attachment_urls = []
    for attachment in post.attachments.filter(file_type="image").order_by("order"):
        if not attachment.file:
            continue
        url = _public_url_for_file(attachment.file.name)
        if url:
            attachment_urls.append(_normalize_reel_image_source(url))
        else:
            try:
                attachment_urls.append(default_storage.path(attachment.file.name))
            except Exception:
                pass
    return attachment_urls


def _queue_reel_compose(post_id: str) -> None:
    from apps.content.models import Post
    from apps.utils import fire_task

    try:
        post = Post.objects.get(pk=post_id)
        meta = dict(post.visual_metadata or {})
        meta["video_compose_status"] = "pending"
        post.visual_metadata = meta
        post.save(update_fields=["visual_metadata", "updated_at"])
    except Post.DoesNotExist:
        pass
    fire_task(compose_reel_video, post_id)


# ── UTM Tracking ─────────────────────────────────────────────────────────
# Appends UTM parameters to URLs in post content so we can attribute
# website traffic back to specific posts, platforms, and campaigns.

_URL_RE = re.compile(r'(https?://[^\s<>"\']+)')


def _add_utm_to_url(url: str, platform: str, post_id: str, post=None) -> str:
    """Add UTM parameters to a single URL, preserving existing query params.

    When ``post`` is provided, delegates to ``Post.tracked_url`` so the link
    carries the post's actual UTM context (including campaign assignment).
    Falls back to the legacy platform/post-id-prefix scheme when no post is
    available (e.g. for callers outside the publish pipeline).
    """
    if post is not None:
        return post.tracked_url(url)
    parsed = urlparse(url)
    existing = parse_qs(parsed.query)
    # Don't overwrite if UTM already present
    if any(k.startswith("utm_") for k in existing):
        return url
    utm = {
        "utm_source": platform,
        "utm_medium": "social",
        "utm_campaign": f"kova_{post_id[:8]}",
        "utm_content": post_id[:8],
    }
    separator = "&" if parsed.query else ""
    new_query = f"{parsed.query}{separator}{urlencode(utm)}"
    return urlunparse(parsed._replace(query=new_query))


def add_utm_tracking(content: str, platform: str, post_id: str, post=None) -> str:
    """Find all URLs in post content and append UTM parameters.

    Returns the content with UTM-tagged URLs. Pass a ``post`` object when
    you want campaign-aware tagging; the function will use the Post's own
    utm_source / utm_medium / utm_campaign / utm_content fields instead of
    the legacy hardcoded platform/post-id-prefix scheme. This is what wires
    Kova-published posts to the Pixel attribution chain in
    apps/analytics/pixel.py:_attribute_to_post.
    """
    if not content:
        return content

    def replace_url(match):
        return _add_utm_to_url(match.group(0), platform, str(post_id), post=post)
    return _URL_RE.sub(replace_url, content)


@shared_task(name="content.post_generate_analytics", soft_time_limit=120, time_limit=150)
def post_generate_analytics(post_ids: list[str]):
    """
    Run Content DNA extraction + engagement prediction AFTER posts are created.
    Runs as a background task so the user sees posts immediately.
    """
    from apps.content.models import Post
    from apps.agents.analyst_agent import batch_extract_content_dna, batch_predict_engagement

    posts = list(Post.objects.filter(pk__in=post_ids).select_related("social_account", "user"))
    if not posts:
        return

    try:
        batch_extract_content_dna(posts)
    except Exception as e:
        logger.warning("Async batch DNA extraction failed: %s", e)

    try:
        batch_predict_engagement(posts)
    except Exception as e:
        logger.warning("Async batch engagement prediction failed: %s", e)

    return {"analyzed": len(posts)}


@shared_task(name="content.async_generate_image", soft_time_limit=60, time_limit=90)
def async_generate_image(post_id: str, image_prompt: str, visual_strategy_data: dict | None = None):
    """
    Generate an AI image for a post in the background.
    Fires after post creation so the user sees text content immediately.
    """
    from apps.content.models import Post
    from apps.agents.media import generate_post_image

    try:
        post = Post.objects.get(pk=post_id)
    except Post.DoesNotExist:
        logger.warning("Post %s not found for async image gen", post_id)
        return

    if visual_strategy_data and visual_strategy_data.get("strategy"):
        from apps.agents.visual_strategy import apply_visual_strategy
        if not visual_strategy_data.get("image_prompt") and image_prompt:
            visual_strategy_data["image_prompt"] = image_prompt
        apply_visual_strategy(post, visual_strategy_data)
    else:
        from apps.agents.visual_strategy import infer_visual_strategy, apply_visual_strategy
        strategy = infer_visual_strategy(
            post.content_text,
            post.social_account.platform if post.social_account else "twitter",
        )
        if strategy == "ai_photo":
            generate_post_image(post, image_prompt)
        else:
            apply_visual_strategy(post, {
                "strategy": strategy,
                "image_prompt": image_prompt,
                "text": post.content_text[:300],
                "headline": post.content_text.split("\n")[0][:120],
            })

    return {"post_id": str(post_id), "status": post.media_status}


@shared_task(name="content.generate_from_seed", soft_time_limit=300, time_limit=360)
def generate_from_seed(seed_id: str):
    """
    Run the Create Agent on a ContentSeed.
    Called when user submits a new idea.
    """
    from apps.content.models import ContentSeed
    from apps.agents.create_agent import run_create_agent

    try:
        seed = ContentSeed.objects.select_related("user", "user__profile").get(pk=seed_id)
    except ContentSeed.DoesNotExist:
        logger.error("ContentSeed %s not found", seed_id)
        return {"error": "Seed not found"}

    from apps.products.utils import maybe_attach_sampled_product_to_autonomous_seed

    maybe_attach_sampled_product_to_autonomous_seed(seed)
    seed.refresh_from_db()

    from apps.billing.exceptions import PlanLimitExceeded
    from apps.notifications.models import Notification

    try:
        posts = run_create_agent(seed)
    except PlanLimitExceeded as exc:
        # Daily AI budget hit — this is a billing event, not a bug. Don't
        # noise Sentry, but do tell the user with an actionable message.
        logger.info(
            "generate_from_seed budget-blocked for seed %s user=%s: %s",
            seed_id, seed.user.email, exc.message,
        )
        seed.refresh_from_db()
        if seed.status not in (ContentSeed.SeedStatus.COMPLETED, ContentSeed.SeedStatus.FAILED):
            seed.status = ContentSeed.SeedStatus.FAILED
            seed.error_message = exc.message
            seed.save(update_fields=["status", "error_message", "updated_at"])
        try:
            Notification.create_for_user(
                seed.user, "system",
                f"AI budget reached: {exc.message} View Billing to upgrade.",
            )
        except Exception:
            pass  # Notifications are best-effort.
        return {"error": exc.message, "error_type": "plan_limit"}
    except Exception as exc:
        logger.error("generate_from_seed failed for seed %s: %s", seed_id, exc, exc_info=True)
        seed.refresh_from_db()
        if seed.status not in (ContentSeed.SeedStatus.COMPLETED, ContentSeed.SeedStatus.FAILED):
            seed.status = ContentSeed.SeedStatus.FAILED
            seed.error_message = f"Generation failed: {exc}"
            seed.save(update_fields=["status", "error_message", "updated_at"])
        return {"error": str(exc)}

    # Fire off Content DNA + engagement prediction as separate async tasks
    # so they don't block the user from seeing their generated posts.
    post_ids = [str(p.id) for p in posts]
    try:
        post_generate_analytics.delay(post_ids)
    except Exception as e:
        logger.warning("Failed to queue post analytics for seed %s: %s", seed_id, e)

    # Auto-schedule if user has Commerce Autopilot or auto-approve on
    from apps.agents.adapt_agent import auto_schedule_post
    from apps.products.commerce_autopilot import should_auto_publish_commerce

    if should_auto_publish_commerce(seed.user):
        for post in posts:
            try:
                auto_schedule_post(post)
            except Exception as e:
                logger.warning("Auto-schedule failed for post %s: %s", post.id, e)

    return {
        "seed_id": str(seed_id),
        "posts_created": len(posts),
        "post_ids": [str(p.id) for p in posts],
    }


@shared_task(name="content.regenerate_post_async", soft_time_limit=180, time_limit=210)
def regenerate_post_async(post_id: str):
    """
    Regenerate a single post asynchronously via the Create Agent.
    Updates the post in-place and sends a notification on completion or failure.
    """
    from apps.content.models import Post
    from apps.agents.create_agent import regenerate_single_post
    from apps.notifications.models import Notification

    try:
        post = Post.objects.select_related("social_account", "user", "seed").get(pk=post_id)
    except Post.DoesNotExist:
        logger.error("Post %s not found for regeneration", post_id)
        return {"error": "Post not found"}

    try:
        post = regenerate_single_post(post)
        # Save version snapshot
        from apps.content.models import PostVersion
        last_ver = post.versions.order_by("-version_number").values_list("version_number", flat=True).first()
        PostVersion.objects.create(
            post=post,
            version_number=(last_ver or 0) + 1,
            content_text=post.content_text,
            source="regeneration",
        )
        Notification.create_for_user(
            post.user, "agent_action",
            f"Post regenerated for {post.platform or 'unknown'}: {post.content_text[:80]}…",
            related_post=post,
        )
        return {"success": True, "post_id": str(post.id)}
    except Exception as exc:
        logger.exception("Regeneration failed for post %s", post_id)
        Notification.create_for_user(
            post.user, "system",
            f"Regeneration failed for your {post.platform or 'unknown'} post. The original content was kept.",
            related_post=post,
        )
        return {"error": str(exc)}


@shared_task(name="content.retry_image_generation", soft_time_limit=90, time_limit=120)
def retry_image_generation(post_id: str):
    """Retry AI image generation for a post using its stored media_prompt."""
    from apps.content.models import Post
    try:
        post = Post.objects.select_related("user", "social_account").get(id=post_id)
    except Post.DoesNotExist:
        return {"error": "Post not found"}

    prompt = post.media_prompt or ""
    if not prompt.strip():
        post.media_status = "failed"
        post.save(update_fields=["media_status", "updated_at"])
        return {"error": "No image prompt to retry"}

    try:
        from apps.agents.visual_strategy import apply_visual_strategy
        result = apply_visual_strategy(post, {
            "strategy": "ai_photo",
            "image_prompt": prompt,
        })
        if result:
            return {"status": "success", "url": result}
        return {"status": "failed"}
    except Exception as exc:
        logger.exception("Retry image generation failed for post %s: %s", post_id, exc)
        post.media_status = "failed"
        post.save(update_fields=["media_status", "updated_at"])
        return {"error": str(exc)}


def _notify_post_status(post):
    """Push WebSocket update so studio cards refresh without aggressive polling."""
    try:
        from apps.notifications.realtime import send_user_event
        send_user_event(post.user_id, "post_status", {
            "post_id": str(post.pk),
            "status": post.media_status,
        })
    except Exception:
        pass


@shared_task(name="content.generate_post_images", soft_time_limit=180, time_limit=240)
def generate_post_images(post_id: str):
    """
    Generate AI images for a post based on its post_format.

    Routes:
    - text:     no-op (text posts don't need images)
    - image:    generate one image from media_prompt, square or portrait
    - carousel: generate one image per slide that has an image_prompt
    - story:    generate one image at 9:16 aspect ratio
    - reel:     generate one image at 9:16 aspect ratio (used as thumbnail)

    After generation, media_status is set to GENERATED (or FAILED).
    Sets media_urls for image/story/reel, and updates carousel_slides
    in-place with each slide's image_url.
    """
    from apps.content.models import Post
    from apps.content.image_gen import generate_image, generate_carousel_images

    try:
        post = Post.objects.select_related("user").get(pk=post_id)
    except Post.DoesNotExist:
        logger.warning("generate_post_images: post %s not found", post_id)
        return

    fmt = post.post_format or Post.PostFormat.TEXT
    if fmt == Post.PostFormat.TEXT:
        return  # Text posts don't need images

    post.media_status = Post.MediaStatus.PENDING
    post.save(update_fields=["media_status", "updated_at"])

    try:
        if fmt == Post.PostFormat.CAROUSEL:
            slides = list(post.carousel_slides or [])
            if not slides:
                logger.info("generate_post_images: no slides on carousel post %s", post_id)
                post.media_status = Post.MediaStatus.FAILED
                post.save(update_fields=["media_status", "updated_at"])
                return

            aspect = post.aspect_ratio or Post.AspectRatio.SQUARE
            slides = generate_carousel_images(slides, aspect)
            image_urls = [s["image_url"] for s in slides if s.get("image_url")]

            post.carousel_slides = slides
            post.media_urls = image_urls
            post.media_status = (
                Post.MediaStatus.GENERATED if image_urls else Post.MediaStatus.FAILED
            )
            # Sync visual_strategy so existing carousel routing in publish_post still works
            post.visual_strategy = "carousel"
            post.save(update_fields=[
                "carousel_slides", "media_urls", "media_status", "visual_strategy", "updated_at",
            ])
            logger.info(
                "generate_post_images: carousel post %s — %d/%d slides have images",
                post_id, len(image_urls), len(slides),
            )
            if (post.visual_metadata or {}).get("reel_variant"):
                _queue_reel_compose(post_id)

        elif fmt in (Post.PostFormat.STORY, Post.PostFormat.REEL):
            prompt = (post.media_prompt or "").strip()
            if not prompt:
                logger.info("generate_post_images: no prompt on story/reel post %s", post_id)
                post.media_status = Post.MediaStatus.FAILED
                post.save(update_fields=["media_status", "updated_at"])
                return

            url = generate_image(prompt, aspect_ratio="story")
            if url:
                post.media_urls = [url]
                post.aspect_ratio = Post.AspectRatio.STORY
                post.media_status = Post.MediaStatus.GENERATED
                post.save(update_fields=[
                    "media_urls", "aspect_ratio", "media_status", "updated_at",
                ])
                logger.info("generate_post_images: story/reel post %s — image generated", post_id)
                if fmt == Post.PostFormat.REEL:
                    _queue_reel_compose(post_id)
            else:
                post.media_status = Post.MediaStatus.FAILED
                post.save(update_fields=["media_status", "updated_at"])
                logger.warning("generate_post_images: image gen failed for story/reel post %s", post_id)

        else:  # image format
            prompt = (post.media_prompt or "").strip()
            if not prompt:
                logger.info("generate_post_images: no prompt on image post %s", post_id)
                post.media_status = Post.MediaStatus.FAILED
                post.save(update_fields=["media_status", "updated_at"])
                return

            aspect = post.aspect_ratio or Post.AspectRatio.SQUARE
            url = generate_image(prompt, aspect_ratio=aspect)
            if url:
                post.media_urls = [url]
                post.media_status = Post.MediaStatus.GENERATED
                post.save(update_fields=["media_urls", "media_status", "updated_at"])
                logger.info("generate_post_images: image post %s — image generated", post_id)
            else:
                post.media_status = Post.MediaStatus.FAILED
                post.save(update_fields=["media_status", "updated_at"])
                logger.warning("generate_post_images: image gen failed for image post %s", post_id)

    except Exception as exc:
        logger.exception("generate_post_images failed for post %s", post_id)
        try:
            post.media_status = Post.MediaStatus.FAILED
            post.save(update_fields=["media_status", "updated_at"])
        except Exception:
            pass
        return {"error": str(exc)}

    _notify_post_status(post)
    return {"post_id": post_id, "status": post.media_status}


def _build_reel_hook_texts(post, meta: dict, slide_count: int) -> list[str]:
    """Product name on first frame; price on last frame only (no mid-slide copy)."""
    from apps.content.reel_director import build_hook_texts

    product_name = ""
    price_label = ""
    if post.product:
        product_name = post.product.name or ""
        price_label = post.product.display_price or ""

    return build_hook_texts(
        slide_count=slide_count,
        slide_roles=[""] * slide_count,
        product_name=product_name,
        price_label=price_label,
        hook_override=meta.get("reel_hook_text", ""),
    )


def _apply_reel_director(post, image_sources: list[str], meta: dict):
    """
    Build ReelComposePlan when director is enabled; mutates meta with recipe fields.
    Returns (sources, plan) — plan may be None.
    """
    from django.conf import settings

    if not getattr(settings, "REEL_DIRECTOR_ENABLED", True):
        return image_sources, None

    from apps.content.reel_director import build_reel_plan
    from apps.products.photoroom_plus import detect_product_category

    category = "general"
    analysis = meta.get("analysis") or {}
    if post.product:
        category = detect_product_category(post.product, analysis)

    plan = build_reel_plan(
        image_sources,
        seed=str(post.pk),
        category=category,
        product_name=(post.product.name if post.product else "") or "",
        price_label=(post.product.display_price if post.product else "") or "",
        hook_override=meta.get("reel_hook_text", ""),
        recipe_id=meta.get("reel_recipe_id"),
    )
    if not plan:
        return image_sources, None

    meta.update(plan.to_metadata())
    return plan.image_urls, plan


@shared_task(name="content.compose_reel_video", soft_time_limit=300, time_limit=360)
def compose_reel_video(post_id: str):
    """
    Compose a motion Reel MP4 from post images + royalty-free music bed.

    Runs after generate_post_images (single 9:16 frame) or directly for
    carousel→reel variants that already have slide images.
    """
    import uuid

    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    from apps.content.models import MediaAttachment, Post
    from apps.content.reel_music import ensure_audio_bed, infer_mood_from_post, pick_music_track
    from apps.content.video_compose import VideoComposeError, compose_carousel_to_reel, compose_motion_reel

    try:
        post = Post.objects.select_related("user").get(pk=post_id)
    except Post.DoesNotExist:
        logger.warning("compose_reel_video: post %s not found", post_id)
        return

    if post.post_format != Post.PostFormat.REEL:
        logger.info("compose_reel_video: post %s is not reel format — skipping", post_id)
        return

    if _post_has_reel_video(post):
        logger.info("compose_reel_video: post %s already has video — skipping", post_id)
        return

    meta = dict(post.visual_metadata or {})
    meta["video_compose_status"] = "pending"
    post.visual_metadata = meta
    post.save(update_fields=["visual_metadata", "updated_at"])

    image_sources = _collect_reel_image_sources(post)
    if not image_sources:
        meta["video_compose_status"] = "failed"
        meta["video_compose_error"] = "No images available for reel composition"
        post.visual_metadata = meta
        post.media_status = Post.MediaStatus.FAILED
        post.save(update_fields=["visual_metadata", "media_status", "updated_at"])
        logger.warning("compose_reel_video: no images for post %s", post_id)
        return {"error": "no_images"}

    reel_plan = None
    try:
        image_sources, reel_plan = _apply_reel_director(post, image_sources, meta)
        post.visual_metadata = meta
        post.save(update_fields=["visual_metadata", "updated_at"])
    except Exception as exc:
        logger.exception(
            "compose_reel_video: reel director failed for post %s", post_id,
        )
        meta["video_compose_status"] = "failed"
        meta["video_compose_error"] = f"Reel director: {exc}"[:500]
        post.visual_metadata = meta
        post.media_status = Post.MediaStatus.FAILED
        post.save(update_fields=["visual_metadata", "media_status", "updated_at"])
        return {"error": str(exc)}

    template = (
        reel_plan.template
        if reel_plan
        else (meta.get("reel_template") or "slideshow")
    )
    mood = (
        reel_plan.music_mood
        if reel_plan
        else (meta.get("music_mood") or infer_mood_from_post(post.content_intent, post.content_text))
    )
    track = pick_music_track(mood=mood, seed=str(post.pk))
    slide_count = len(image_sources)
    est_duration = max(slide_count * 3.0 - 0.5 * max(slide_count - 1, 0), 5.0)

    from apps.content.reel_music import resolve_track_path

    audio_path = resolve_track_path(track)
    generated_audio = audio_path is None
    if generated_audio:
        try:
            audio_path = ensure_audio_bed(track, est_duration + 2)
        except RuntimeError as exc:
            meta["video_compose_status"] = "failed"
            meta["video_compose_error"] = str(exc)
            post.visual_metadata = meta
            post.media_status = Post.MediaStatus.FAILED
            post.save(update_fields=["visual_metadata", "media_status", "updated_at"])
            return {"error": str(exc)}

    thumbnail_url = None
    for url in post.media_urls or []:
        if url and not _is_video_url(url):
            thumbnail_url = url
            break

    hook_texts = (
        reel_plan.hook_texts
        if reel_plan
        else _build_reel_hook_texts(post, meta, len(image_sources))
    )

    # Photoroom animate: single-hero only; multi-slide director plans use FFmpeg.
    use_photoroom = (
        not reel_plan
        and len(image_sources) <= 2
        and (
            meta.get("composition_hero_url")
            or meta.get("prefer_photoroom_video")
        )
    )
    if use_photoroom:
        try:
            from apps.products.photoroom_video import try_photoroom_reel_for_post

            video_url = try_photoroom_reel_for_post(post, image_sources)
            if video_url:
                _notify_post_status(post)
                logger.info(
                    "compose_reel_video: post %s via Photoroom animate (%s)",
                    post_id, video_url[:80],
                )
                return {"post_id": post_id, "video_url": video_url, "status": "done", "backend": "photoroom"}
        except Exception as exc:
            logger.warning(
                "compose_reel_video: Photoroom animate failed for %s, using FFmpeg: %s",
                post_id, exc,
            )

    try:
        from apps.content.video_compose import compose_from_plan

        if reel_plan:
            mp4_bytes = compose_from_plan(reel_plan, audio_path=audio_path)
        elif template == "carousel_to_video":
            mp4_bytes = compose_carousel_to_reel(
                image_sources,
                audio_path=audio_path,
                hook_texts=hook_texts,
                template=template,
            )
        else:
            mp4_bytes = compose_motion_reel(
                image_sources,
                slide_duration_sec=3.5 if len(image_sources) == 1 else 3.0,
                transition_sec=0.5,
                audio_path=audio_path,
                template=template,
                hook_texts=hook_texts,
            )
    except VideoComposeError as exc:
        meta["video_compose_status"] = "failed"
        meta["video_compose_error"] = str(exc)
        post.visual_metadata = meta
        post.media_status = Post.MediaStatus.FAILED
        post.save(update_fields=["visual_metadata", "media_status", "updated_at"])
        logger.exception("compose_reel_video failed for post %s", post_id)
        return {"error": str(exc)}
    except Exception as exc:
        meta["video_compose_status"] = "failed"
        meta["video_compose_error"] = str(exc)[:500]
        post.visual_metadata = meta
        post.media_status = Post.MediaStatus.FAILED
        post.save(update_fields=["visual_metadata", "media_status", "updated_at"])
        logger.exception("compose_reel_video unexpected error for post %s", post_id)
        return {"error": str(exc)}
    finally:
        if generated_audio and audio_path:
            try:
                from pathlib import Path
                import tempfile

                if str(audio_path).startswith(tempfile.gettempdir()):
                    Path(audio_path).unlink(missing_ok=True)
            except Exception:
                pass

    file_name = f"reel_videos/{uuid.uuid4().hex}.mp4"
    saved_name = default_storage.save(file_name, ContentFile(mp4_bytes))
    public_url = _public_url_for_file(saved_name)

    if not public_url:
        meta["video_compose_status"] = "failed"
        meta["video_compose_error"] = "Could not generate public URL for composed reel"
        post.visual_metadata = meta
        post.media_status = Post.MediaStatus.FAILED
        post.save(update_fields=["visual_metadata", "media_status", "updated_at"])
        return {"error": "no_public_url"}

    post.attachments.filter(file_type="video").delete()
    MediaAttachment.objects.create(
        post=post,
        file=saved_name,
        file_type="video",
        order=0,
        alt_text=f"Motion reel — {track.get('title', 'background music')}",
    )

    meta.update({
        "video_compose_status": "done",
        "reel_template": template,
        "reel_recipe_id": meta.get("reel_recipe_id"),
        "reel_video_url": public_url,
        "reel_thumbnail_url": thumbnail_url,
        "music_track_id": track.get("id"),
        "music_mood": mood,
        "music_attribution": track.get("attribution", ""),
    })
    post.visual_metadata = meta
    post.media_urls = [public_url]
    post.aspect_ratio = Post.AspectRatio.STORY
    post.media_status = Post.MediaStatus.GENERATED
    post.save(update_fields=[
        "visual_metadata", "media_urls", "aspect_ratio", "media_status", "updated_at",
    ])
    _notify_post_status(post)

    logger.info("compose_reel_video: post %s composed (%d bytes)", post_id, len(mp4_bytes))
    return {"post_id": post_id, "video_url": public_url, "status": "done"}


@shared_task(
    name="content.publish_post",
    bind=True,
    max_retries=8,     # up to 8 retries — enough for a 4-hour outage window
    soft_time_limit=360,
    time_limit=420,
)
def publish_post(self, post_id: str):
    """
    Publish a single post to its platform.

    Retry strategy:
      - Auth errors (401/403/PlatformAuthError): no retry — fail immediately
      - Rate limit (429): retry at 15min, 30min, 90min
      - Outage (5xx):     retry at 30min, 60min, 90min, 120min (covers 4-hour window)
      - Other transient:  retry at 1min, 2min, 4min (original backoff)
    """
    from apps.content.models import Post
    from apps.platforms.providers import get_provider
    from apps.notifications.models import Notification

    try:
        post = Post.objects.select_related("social_account", "user").get(pk=post_id)
    except Post.DoesNotExist:
        logger.error("Post %s not found for publishing", post_id)
        return {"error": "Post not found"}

    # Guard: only publish approved/scheduled posts
    if post.status not in (Post.Status.APPROVED, Post.Status.SCHEDULED):
        logger.warning("Post %s has status %s, skipping publish", post_id, post.status)
        return {"error": f"Post status is {post.status}, not publishable"}

    # ── Emergency pause — halt all autonomous publishing ──────────────
    profile = getattr(post.user, "profile", None)
    if profile and profile.emergency_pause:
        logger.info("EMERGENCY PAUSE: skipping publish for post %s (user %s)", post_id, post.user.email)
        return {"error": "Publishing paused — emergency pause is active"}

    # ── Content safety gate — last line of defense before going live ──
    from apps.content.safety import check_content_safety
    safety = check_content_safety(post.content_text, user=post.user)
    if safety.blocked:
        # Hard block: content is dangerous, revert to pending approval
        post.status = Post.Status.PENDING_APPROVAL
        post.ai_reasoning = f"SAFETY BLOCKED: {safety.summary}"
        post.save(update_fields=["status", "ai_reasoning", "updated_at"])
        Notification.create_for_user(
            post.user, "system",
            f"⚠️ Post blocked by safety check: {safety.summary[:150]}. Please review and edit.",
            related_post=post,
        )
        logger.warning("SAFETY BLOCKED post %s: %s", post_id, safety.summary)
        return {"error": f"Content blocked: {safety.summary}"}
    elif not safety.is_safe:
        # Soft block: risky content, send back for human review
        post.status = Post.Status.PENDING_APPROVAL
        post.ai_reasoning = f"SAFETY REVIEW (score={safety.risk_score}): {safety.summary}"
        post.save(update_fields=["status", "ai_reasoning", "updated_at"])
        Notification.create_for_user(
            post.user, "system",
            f"⚠️ Post needs review (risk score {safety.risk_score}): {safety.summary[:150]}",
            related_post=post,
        )
        logger.info("SAFETY REVIEW post %s (score=%d): %s", post_id, safety.risk_score, safety.summary)
        return {"error": f"Content flagged for review: {safety.summary}"}

    # ── Reel/video gate — wait for MP4 composition before publishing ─────
    _post_format_early = getattr(post, "post_format", "") or ""
    if _post_format_early == Post.PostFormat.REEL:
        compose_status = (post.visual_metadata or {}).get("video_compose_status")
        if not _post_has_reel_video(post):
            if compose_status in (None, "pending"):
                logger.info(
                    "publish_post: reel video not ready for post %s — retrying in 90s",
                    post_id,
                )
                post.status = Post.Status.SCHEDULED
                post.save(update_fields=["status", "updated_at"])
                raise self.retry(countdown=90, exc=Exception("Reel video composition in progress"))
            _fail_post(post, "Reel video is not ready — composition failed or was not started.")
            Notification.create_for_user(
                post.user, "publish_failed",
                "Your Reel video could not be composed. Open the post in Studio and retry.",
                related_post=post,
            )
            return {"error": "reel_video_not_ready"}

    # Mark as publishing
    post.status = Post.Status.PUBLISHING
    post.save(update_fields=["status", "updated_at"])

    account = post.social_account
    provider = get_provider(account.platform)

    if not provider:
        _fail_post(post, f"No provider found for platform: {account.platform}")
        Notification.create_for_user(
            post.user, "publish_failed",
            f"Failed to publish to {account.get_platform_display()}: unsupported platform",
            related_post=post,
        )
        return {"error": "No provider"}

    # Check token freshness
    if account.is_token_expired and account.refresh_token:
        try:
            tokens = provider.refresh_access_token(account.refresh_token)
            account.access_token = tokens["access_token"]
            if tokens.get("refresh_token"):
                account.refresh_token = tokens["refresh_token"]
            if tokens.get("expires_at"):
                account.token_expires_at = tokens["expires_at"]
            account.save(update_fields=["access_token", "refresh_token", "token_expires_at", "updated_at"])
        except Exception as e:
            _fail_post(post, f"Token refresh failed: {e}")
            account.mark_error(f"Token refresh failed: {e}")
            Notification.create_for_user(
                post.user, "publish_failed",
                f"Failed to publish to {account.get_platform_display()}: authentication expired. Please reconnect.",
                related_post=post,
            )
            return {"error": "Token refresh failed"}

    if account.needs_reauth:
        _fail_post(post, "Account needs re-authentication")
        Notification.create_for_user(
            post.user, "publish_failed",
            f"{account.get_platform_display()} needs to be reconnected.",
            related_post=post,
        )
        return {"error": "Needs reauth"}

    # Publish
    try:
        # Build platform-specific publish kwargs from stored OAuth metadata
        publish_kwargs = {"account": account}
        meta = account.metadata or {}
        if account.platform == "facebook":
            pages = meta.get("pages", [])
            if pages:
                # Honour the user's selected Page (set via Settings → Platforms).
                # Falls back to the first page for accounts that haven't selected one.
                selected_id = meta.get("selected_page_id")
                selected_page = (
                    next((p for p in pages if p["id"] == selected_id), None)
                    if selected_id else None
                ) or pages[0]
                publish_kwargs["page_id"] = selected_page["id"]
                publish_kwargs["page_access_token"] = selected_page.get("access_token", account.access_token)
                logger.debug(
                    "Facebook publish: using page '%s' (%s) for account %s",
                    selected_page.get("name"), selected_page["id"], account.pk,
                )
            else:
                logger.warning(
                    "Facebook account %s has no pages in metadata — "
                    "user may need to reconnect with Pages permissions",
                    account.pk,
                )
                _fail_post(post, "Facebook account has no Pages — reconnect with Pages permissions.")
                Notification.create_for_user(
                    post.user, "publish_failed",
                    "Your Facebook account needs to be reconnected. "
                    "Go to Settings → Platforms → Facebook and reconnect to grant Pages access.",
                    related_post=post,
                )
                return {"error": "Facebook account has no pages in metadata"}
        elif account.platform == "instagram":
            # Instagram stores its Business Account ID under ig_business_id,
            # not in a "pages" list. The access_token on the account is already
            # the page token (set during OAuth: access_token=page_token).
            ig_user_id = meta.get("ig_business_id") or account.platform_user_id
            publish_kwargs["ig_user_id"] = ig_user_id or ""
            # Store page token explicitly so first-comment logic can retrieve it
            # consistently, matching the same pattern as the Facebook branch.
            publish_kwargs["page_access_token"] = meta.get("page_access_token") or account.access_token

        # ── UTM tracking — campaign-aware ───────────────────────────────
        # Make sure the Post's own utm_* fields are populated so the URL
        # tagger uses them (campaign attribution depends on it). This is
        # cheap, idempotent, and a no-op for re-runs.
        post.populate_utm()
        post.save(update_fields=["utm_source", "utm_medium", "utm_campaign", "utm_content", "updated_at"])

        # Add UTM tracking to any URLs in the content body
        publish_content = add_utm_tracking(post.content_text, account.platform, str(post.id), post=post)

        # Strip invisible Unicode characters (zero-width spaces, soft hyphens,
        # BOM markers) that LLMs occasionally emit and that cause LinkedIn and
        # other platform APIs to silently truncate the post body.
        publish_content_raw = publish_content
        publish_content = sanitize_content(publish_content)
        if len(publish_content) != len(publish_content_raw):
            logger.warning(
                "SANITIZE [%s] post=%s: stripped %d invisible char(s). "
                "This is likely the cause of past platform truncation.",
                account.platform, post.id,
                len(publish_content_raw) - len(publish_content),
            )

        # Strip markdown syntax (**bold**, *italic*, etc.) that LLMs emit but
        # social platforms render as literal asterisks/underscores.
        if account.platform in _PLAIN_TEXT_PLATFORMS:
            stripped = strip_markdown(publish_content)
            if stripped != publish_content:
                logger.warning(
                    "MARKDOWN [%s] post=%s: stripped markdown syntax before publish.",
                    account.platform, post.id,
                )
                publish_content = stripped

        # ── Diagnostic: content audit at publish time ─────────────────
        _db_len = len(post.content_text) if post.content_text else 0
        _pub_len = len(publish_content) if publish_content else 0
        logger.info(
            "AUDIT [%s] post=%s db=%d pub=%d nl=%d",
            account.platform, post.id, _db_len, _pub_len,
            (publish_content or "").count("\n"),
        )
        logger.info("AUDIT first100=%r", (publish_content or "")[:100])
        logger.info("AUDIT last80=%r", (publish_content or "")[-80:])

        # Safety: block publishing to platforms that require media if none attached
        if post.needs_media:
            _fail_post(post, f"{account.get_platform_display()} requires an image but none is attached.")
            Notification.create_for_user(
                post.user, "publish_failed",
                f"{account.get_platform_display()} requires an image. Upload one and retry.",
                related_post=post,
            )
            return {"error": "Media required"}

        # ── Collect media for publishing ──────────────────────────────
        # Two forms:
        #   media_files  – raw bytes read from storage (preferred: works
        #                  with any backend, no public URL needed)
        #   media_urls   – absolute URLs (AI-generated images or pre-signed
        #                  storage URLs, used by APIs that *require* a URL,
        #                  e.g. Instagram Container API)
        import mimetypes
        from django.core.files.storage import default_storage

        # Determine post format for media routing.
        # post_format is the authoritative source; fall back to visual_strategy for
        # older posts created before post_format existed.
        _post_format = getattr(post, "post_format", "") or ""
        _visual_strategy = getattr(post, "visual_strategy", "") or ""
        is_carousel_post = _post_format == "carousel" or _visual_strategy == "carousel"
        is_story_post = _post_format == "story"
        is_reel_post = _post_format == "reel"

        media_files = []   # [(filename, bytes, content_type), ...]
        media_urls_list = list(post.media_urls or [])  # AI-generated / carousel slides (already public)

        for attachment in post.attachments.order_by("order"):
            if not attachment.file:
                continue
            # Build the public URL (needed for URL-based APIs and fallback)
            url = _public_url_for_file(attachment.file.name)

            # Read file bytes from storage (works with S3, R2, local FS)
            try:
                with default_storage.open(attachment.file.name, "rb") as fh:
                    data = fh.read()
                fname = attachment.file.name.rsplit("/", 1)[-1]
                ctype = mimetypes.guess_type(fname)[0] or "image/jpeg"
                media_files.append((fname, data, ctype))
            except Exception as e:
                logger.warning("Could not read attachment %s from storage: %s", attachment.pk, e)
                if url:
                    try:
                        import httpx
                        dl_resp = httpx.get(url, timeout=30, follow_redirects=True)
                        dl_resp.raise_for_status()
                        fname = attachment.file.name.rsplit("/", 1)[-1]
                        ctype = (
                            dl_resp.headers.get("content-type", "").split(";")[0]
                            or mimetypes.guess_type(fname)[0]
                            or "image/jpeg"
                        )
                        media_files.append((fname, dl_resp.content, ctype))
                        logger.info("Downloaded attachment %s via public URL (%d bytes)", attachment.pk, len(dl_resp.content))
                    except Exception as dl_err:
                        logger.warning("Could not download attachment %s from %s: %s", attachment.pk, url, dl_err)

            # Carousel: post.media_urls already has ordered slide URLs — don't prepend
            # attachment URLs (same files, would duplicate and reverse order).
            if url and not is_carousel_post:
                media_urls_list.insert(0, url)

        absolute_media_urls = _resolve_absolute_media_urls(
            post, is_carousel_post=is_carousel_post,
        ) or None

        if post.needs_media and not absolute_media_urls and not media_files:
            _fail_post(
                post,
                "No public media URLs — check storage/CDN (HTTPS required for Instagram).",
            )
            Notification.create_for_user(
                post.user, "publish_failed",
                "Publishing failed: images are not publicly reachable. "
                "Open the post in Studio, regenerate media, or retry.",
                related_post=post,
            )
            return {"error": "no_public_media"}

        reel_video_url = _reel_video_url(absolute_media_urls) if is_reel_post else None
        if reel_video_url:
            publish_kwargs["video_url"] = reel_video_url

        # Route publish to the correct platform API based on post_format.
        if account.platform == "instagram":
            if is_story_post:
                publish_kwargs["media_type"] = "STORIES"
            elif is_reel_post:
                publish_kwargs["media_type"] = "REELS"
            elif absolute_media_urls and (is_carousel_post or len(absolute_media_urls) > 1):
                publish_kwargs["media_type"] = "CAROUSEL"
        elif account.platform == "facebook":
            if is_reel_post:
                publish_kwargs["media_type"] = "REELS"
            elif is_story_post:
                publish_kwargs["media_type"] = "STORIES"
        elif account.platform == "tiktok" and is_reel_post:
            publish_kwargs["privacy_level"] = _resolve_tiktok_privacy(account)
            publish_kwargs["is_aigc"] = True
        elif account.platform == "linkedin" and is_reel_post and reel_video_url:
            publish_kwargs["post_type"] = "video"

        # Safety net: detect and fix encrypted tokens not decrypted by ORM
        token = account.access_token
        if token and token.startswith("gAAAAA"):
            from apps.platforms.encryption import decrypt_token
            logger.warning(
                "Token for %s still encrypted after ORM load (len=%d). "
                "Attempting explicit decrypt.",
                account.platform, len(token),
            )
            token = decrypt_token(token)
            if token.startswith("gAAAAA"):
                logger.error(
                    "Explicit decrypt ALSO failed for %s. Token is unrecoverable — "
                    "user must reconnect.",
                    account.platform,
                )

        result = provider.publish_post(
            access_token=token,
            content=publish_content,
            media_urls=absolute_media_urls,
            media_files=media_files or None,
            **publish_kwargs,
        )
    except Exception as exc:
        from apps.platforms.providers.base import PlatformAuthError
        from apps.platforms.error_codes import translate_error
        from apps.platforms.outage import record_failure

        exc_str = str(exc)
        platform = account.platform

        # ── Detect error type ─────────────────────────────────────────────
        # Extract HTTP status code from the exception message if present
        status_code = None
        for code in (401, 403, 429, 500, 502, 503, 504):
            if str(code) in exc_str:
                status_code = code
                break

        is_auth_error = isinstance(exc, PlatformAuthError) or status_code in (401, 403)
        is_rate_limit = status_code == 429
        is_outage = status_code in (500, 502, 503, 504)

        # Translate to user-friendly message
        error_info = translate_error(platform, status_code, exc_str)

        # ── Auth errors — fail immediately, no retry ──────────────────────
        if is_auth_error or error_info.is_auth:
            logger.error("Auth error publishing post %s (%s): %s", post_id, platform, exc_str)
            _fail_post(post, f"Authentication error: {exc_str}")
            account.mark_error(exc_str, status_code=status_code or 401)
            Notification.create_for_user(
                post.user, "publish_failed",
                f"❌ {error_info.user_message} {error_info.fix}",
                related_post=post,
            )
            return {"error": "auth_error"}

        # ── Outage — record failure, retry with long windows ─────────────
        if is_outage or error_info.is_outage:
            record_failure(platform)
            account.mark_error(exc_str, status_code=status_code)
            # Retry schedule: 30min, 60min, 90min, 120min (4×)
            outage_countdowns = [1800, 3600, 5400, 7200]
            retry_num = self.request.retries
            if retry_num < len(outage_countdowns):
                countdown = outage_countdowns[retry_num]
                logger.warning(
                    "Outage retry %d for post %s (%s) in %ds",
                    retry_num + 1, post_id, platform, countdown,
                )
                # Only notify user on first outage retry
                if retry_num == 0:
                    Notification.create_for_user(
                        post.user, "publish_failed",
                        f"⏳ {error_info.user_message} {error_info.fix}",
                        related_post=post,
                    )
                post.save(update_fields=["updated_at"])
                raise self.retry(exc=exc, countdown=countdown)
            else:
                _fail_post(post, f"Outage: platform unavailable after {retry_num} retries: {exc_str}")
                Notification.create_for_user(
                    post.user, "publish_failed",
                    f"❌ {platform.title()} was unavailable for too long. "
                    f"Your post has been saved — reschedule it when the platform recovers.",
                    related_post=post,
                )
                return {"error": "outage_max_retries"}

        # ── Rate limit — retry with moderate back-off ─────────────────────
        if is_rate_limit or error_info.is_rate_limit:
            account.mark_error(exc_str, status_code=429)
            rate_countdowns = [900, 1800, 5400]  # 15min, 30min, 90min
            retry_num = self.request.retries
            if retry_num < len(rate_countdowns):
                countdown = rate_countdowns[retry_num]
                logger.warning(
                    "Rate limit retry %d for post %s (%s) in %ds",
                    retry_num + 1, post_id, platform, countdown,
                )
                if retry_num == 0:
                    Notification.create_for_user(
                        post.user, "publish_failed",
                        f"⏳ {error_info.user_message} {error_info.fix}",
                        related_post=post,
                    )
                post.save(update_fields=["updated_at"])
                raise self.retry(exc=exc, countdown=countdown)
            else:
                _fail_post(post, f"Rate limit exceeded after {retry_num} retries")
                Notification.create_for_user(
                    post.user, "publish_failed",
                    f"❌ {error_info.user_message} {error_info.fix}",
                    related_post=post,
                )
                return {"error": "rate_limit_max_retries"}

        # ── Other transient errors — original exponential backoff ─────────
        logger.exception("Publishing post %s raised an exception", post_id)
        try:
            post.save(update_fields=["updated_at"])
            self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            _fail_post(post, f"Max retries exceeded: {exc_str}")
            Notification.create_for_user(
                post.user, "publish_failed",
                f"❌ Failed to publish to {account.get_platform_display()} after multiple attempts. "
                f"Error: {exc_str[:200]}",
                related_post=post,
            )
            return {"error": "max_retries_exceeded"}

    if result.success:
        post.status = Post.Status.PUBLISHED
        post.published_at = timezone.now()
        post.platform_post_id = result.platform_post_id
        post.platform_post_url = result.url
        post.save(update_fields=[
            "status", "published_at", "platform_post_id",
            "platform_post_url", "updated_at",
        ])
        account.mark_synced()

        if post.product_id:
            from apps.partners.webhooks import notify_post_published
            notify_post_published(post)

        # Clear any outage flags — this platform is working
        from apps.platforms.outage import record_success as clear_outage
        clear_outage(account.platform)

        logger.info(
            "PUBLISH SUCCESS [%s] post=%s: platform_id=%s, "
            "content_len=%d chars sent, url=%s",
            account.platform, post.id,
            result.platform_post_id,
            len(publish_content or ""),
            result.url,
        )

        # ── TikTok: queue post-publish verification ───────────────────────
        # TikTok sometimes returns 200 but the post never appears. Verify
        # the post actually exists 2 minutes after publishing.
        if account.platform == "tiktok" and result.platform_post_id:
            verify_tiktok_post.apply_async(
                args=[post_id, result.platform_post_id, account.access_token],
                countdown=120,
            )

        # ── Facebook first-comment link strategy ─────────────────────────
        # Facebook reduces organic reach 50-70% for posts with outbound links
        # in the body. We post the CTA/product URL as the first comment
        # immediately after publishing — full reach preserved, link visible
        # to engaged readers who expand or scroll to comments.
        if account.platform == "facebook" and result.platform_post_id:
            first_comment_text = (post.first_comment or "").strip()
            # Fall back to cta_url if no explicit first_comment was set
            if not first_comment_text and post.cta_type == "link" and post.cta_url:
                label = (post.cta_text or "Learn more").strip()
                tracked_url = post.tracked_url(post.cta_url)
                first_comment_text = f"{label}: {tracked_url}"
            # Tag any URLs the user (or AI) already embedded in first_comment
            elif first_comment_text:
                first_comment_text = add_utm_tracking(
                    first_comment_text, "facebook", str(post.id), post=post,
                )
            if first_comment_text:
                page_token = publish_kwargs.get("page_access_token", account.access_token)
                try:
                    fc_result = provider.post_comment(
                        page_token=page_token,
                        post_id=result.platform_post_id,
                        message=first_comment_text,
                    )
                    if fc_result.get("success"):
                        logger.info(
                            "Facebook first comment posted on post %s (comment_id=%s)",
                            result.platform_post_id, fc_result.get("id"),
                        )
                    else:
                        logger.warning(
                            "Facebook first comment failed on post %s: %s",
                            result.platform_post_id, fc_result.get("error"),
                        )
                except Exception as fc_err:
                    logger.warning(
                        "Facebook first comment error for post %s: %s", post_id, fc_err,
                    )

        # ── Instagram first-comment: save/link-in-bio CTA ───────────────────
        # Links in IG captions are not clickable — the bio link is the only
        # working click path. A first comment immediately below the caption
        # reinforces the CTA and prompts saves (the top IG algorithm signal).
        if account.platform == "instagram" and result.platform_post_id:
            ig_fc_text = (post.first_comment or "").strip()
            if not ig_fc_text and post.cta_type == "link" and post.cta_url:
                # IG caption links aren't clickable, but first-comment links are
                # still tappable on mobile and copy-pasteable. Surface the CTA
                # here when no first_comment was authored — and tag it so the
                # click flows back through Pixel attribution.
                label = (post.cta_text or "Tap link in bio").strip()
                tracked_url = post.tracked_url(post.cta_url)
                ig_fc_text = f"{label}: {tracked_url}"
            elif ig_fc_text:
                ig_fc_text = add_utm_tracking(
                    ig_fc_text, "instagram", str(post.id), post=post,
                )
            else:
                ig_fc_text = "💾 Save this for later!"
            page_token = publish_kwargs.get("page_access_token", account.access_token)
            try:
                ig_fc_result = provider.post_comment(
                    page_token=page_token,
                    post_id=result.platform_post_id,
                    message=ig_fc_text,
                )
                if ig_fc_result.get("success"):
                    logger.info(
                        "Instagram first comment posted on post %s (comment_id=%s)",
                        result.platform_post_id, ig_fc_result.get("id"),
                    )
                else:
                    logger.warning(
                        "Instagram first comment failed on post %s: %s",
                        result.platform_post_id, ig_fc_result.get("error"),
                    )
            except Exception as ig_fc_err:
                logger.warning(
                    "Instagram first comment error for post %s: %s", post_id, ig_fc_err,
                )

        # ── LinkedIn first-comment: link strategy ───────────────────────────
        # LinkedIn reduces organic reach ~50% for posts with outbound links
        # in the body. We post the CTA/product URL as the first comment
        # immediately after publishing — full reach preserved, link stays
        # visible to readers who engage.
        if account.platform == "linkedin" and result.platform_post_id:
            li_fc_text = (post.first_comment or "").strip()
            # Fall back to cta_url if no explicit first_comment was set
            if not li_fc_text and post.cta_type == "link" and post.cta_url:
                label = (post.cta_text or "Learn more").strip()
                tracked_url = post.tracked_url(post.cta_url)
                li_fc_text = f"{label}: {tracked_url}"
            # Tag any URLs the user (or AI) already embedded in first_comment
            elif li_fc_text:
                li_fc_text = add_utm_tracking(
                    li_fc_text, "linkedin", str(post.id), post=post,
                )
            if li_fc_text:
                try:
                    li_fc_result = provider.post_comment(
                        access_token=account.access_token,
                        post_id=result.platform_post_id,
                        message=li_fc_text,
                        account=account,
                    )
                    if li_fc_result.get("success"):
                        logger.info(
                            "LinkedIn first comment posted on post %s (comment_id=%s)",
                            result.platform_post_id, li_fc_result.get("id"),
                        )
                    else:
                        logger.warning(
                            "LinkedIn first comment failed on post %s: %s",
                            result.platform_post_id, li_fc_result.get("error"),
                        )
                except Exception as li_fc_err:
                    logger.warning(
                        "LinkedIn first comment error for post %s: %s", post_id, li_fc_err,
                    )

        Notification.create_for_user(
            post.user, "post_published",
            f"Published to {account.get_platform_display()}: {post.content_text[:80]}...",
            related_post=post,
        )
        # Schedule metrics fetch in 1 hour
        fetch_post_metrics.apply_async(args=[str(post.id)], countdown=3600)
        logger.info("Post %s published successfully to %s", post_id, account.platform)
        return {"success": True, "platform_post_id": result.platform_post_id}
    else:
        _fail_post(post, result.error)
        Notification.create_for_user(
            post.user, "publish_failed",
            f"Failed to publish to {account.get_platform_display()}: {result.error[:100]}",
            related_post=post,
        )
        return {"error": result.error}


def _fail_post(post, error_message: str):
    """Mark a post as failed with an error message."""
    post.status = post.Status.FAILED
    post.ai_reasoning = f"Publish error: {error_message}"
    post.save(update_fields=["status", "ai_reasoning", "updated_at"])
    logger.error("Post %s failed: %s", post.pk, error_message)


@shared_task(name="content.recover_stuck_publishing_posts")
def recover_stuck_publishing_posts():
    """
    Fail posts left in PUBLISHING after worker timeout or IG container hangs.

    Runs every 10 minutes via Celery Beat so the queue UI does not spin forever.
    """
    from datetime import timedelta

    from apps.content.models import Post
    from apps.notifications.models import Notification

    cutoff = timezone.now() - timedelta(minutes=12)
    stuck = Post.objects.filter(
        status=Post.Status.PUBLISHING,
        updated_at__lt=cutoff,
    ).select_related("user", "social_account")[:50]

    recovered = 0
    for post in stuck:
        platform = post.social_account.get_platform_display() if post.social_account else "platform"
        _fail_post(
            post,
            "Publishing timed out — the platform did not confirm in time. Retry from Studio.",
        )
        Notification.create_for_user(
            post.user, "publish_failed",
            f"Publishing to {platform} timed out. Open the post and tap Retry.",
            related_post=post,
        )
        recovered += 1

    if recovered:
        logger.warning("recover_stuck_publishing_posts: cleared %d stuck post(s)", recovered)
    return {"recovered": recovered}


@shared_task(
    name="content.check_and_publish_due_posts",
    soft_time_limit=4 * 60,
    time_limit=5 * 60,
)
@single_run("content.check_and_publish_due_posts", timeout=4 * 60)
def check_and_publish_due_posts():
    """
    Periodic task: find all posts due for publishing and fire publish tasks.
    Also auto-schedules approved posts that are missing a scheduled_at time.
    Runs every 5 minutes via Celery Beat.
    """
    from apps.agents.adapt_agent import auto_schedule_post
    from apps.content.models import Post

    now = timezone.now()

    # ── Step 1: Auto-schedule approved posts missing scheduled_at ─────
    # These are posts the user approved (or Strategist created) but never
    # got a time assigned — e.g. auto_approve was just enabled, or the
    # user approved from the dashboard without picking a time.
    unscheduled = Post.objects.filter(
        status=Post.Status.APPROVED,
        scheduled_at__isnull=True,
    ).select_related("social_account", "user", "user__profile")[:20]  # cap per cycle

    auto_scheduled = 0
    for post in unscheduled:
        try:
            result = auto_schedule_post(post)
            if result:
                auto_scheduled += 1
        except Exception as e:
            logger.warning("Auto-schedule failed for post %s: %s", post.pk, e)

    if auto_scheduled:
        logger.info("Auto-scheduled %d approved posts that were missing scheduled_at", auto_scheduled)

    # ── Step 2: Dispatch posts whose scheduled_at has arrived ─────────
    due_posts = Post.objects.filter(
        status__in=[Post.Status.APPROVED, Post.Status.SCHEDULED],
        scheduled_at__lte=now,
    ).values_list("id", flat=True)

    count = 0
    for post_id in due_posts:
        publish_post.delay(str(post_id))
        count += 1

    if count:
        logger.info("Dispatched %d posts for publishing", count)
    else:
        # Diagnostic: log pipeline state so we can see why nothing publishes
        total_approved = Post.objects.filter(status=Post.Status.APPROVED).count()
        total_scheduled = Post.objects.filter(status=Post.Status.SCHEDULED).count()
        no_schedule = Post.objects.filter(
            status__in=[Post.Status.APPROVED, Post.Status.SCHEDULED],
            scheduled_at__isnull=True,
        ).count()
        future = Post.objects.filter(
            status__in=[Post.Status.APPROVED, Post.Status.SCHEDULED],
            scheduled_at__gt=now,
        ).count()
        if total_approved or total_scheduled or no_schedule:
            logger.info(
                "Publish check: 0 due. %d approved, %d scheduled, "
                "%d missing scheduled_at, %d scheduled for future.",
                total_approved, total_scheduled, no_schedule, future,
            )
    return {"dispatched": count, "auto_scheduled": auto_scheduled}


@shared_task(name="content.fetch_post_metrics", soft_time_limit=60, time_limit=90)
def fetch_post_metrics(post_id: str):
    """
    Fetch engagement metrics for a published post from its platform.
    Includes circuit-breaker: skips accounts that recently failed with
    permission errors to avoid hammering the API with known-bad tokens.
    """
    from apps.analytics.models import PostMetric
    from apps.content.models import Post
    from apps.platforms.providers import get_provider

    try:
        post = Post.objects.select_related("social_account").get(pk=post_id)
    except Post.DoesNotExist:
        logger.error("Post %s not found for metrics fetch", post_id)
        return {"error": "Post not found"}

    if post.status != Post.Status.PUBLISHED or not post.platform_post_id:
        return {"error": "Post not published or no platform_post_id"}

    account = post.social_account
    provider = get_provider(account.platform)
    if not provider:
        return {"error": f"No provider for {account.platform}"}

    # ── Circuit breaker: skip accounts with recent permission failures ────
    # If this account's metadata has a metrics_permission_error timestamp
    # within the last 6 hours, skip the API call entirely.
    import datetime as _dt
    meta = account.metadata or {}
    perm_error_at = meta.get("metrics_permission_error_at")
    if perm_error_at:
        try:
            error_time = _dt.datetime.fromisoformat(perm_error_at)
            if timezone.now() - error_time < _dt.timedelta(hours=6):
                return {
                    "skipped": True,
                    "reason": "Account has recent permission error — circuit breaker active",
                    "post_id": post_id,
                }
        except (ValueError, TypeError):
            pass  # Invalid timestamp, proceed normally

    try:
        # For Facebook/Instagram, use the page token — the user-level token
        # does NOT have pages_read_engagement permission.
        token = account.access_token
        meta = account.metadata or {}
        if account.platform == "facebook":
            pages = meta.get("pages", [])
            # Honour selected_page_id: fetch metrics for the page Kova publishes to.
            selected_id = meta.get("selected_page_id")
            selected_page = (
                next((p for p in pages if p["id"] == selected_id), None)
                if selected_id else None
            ) or (pages[0] if pages else None)
            page_token = selected_page.get("access_token") if selected_page else None
            if not page_token:
                logger.warning(
                    "No page access token for Facebook account %s (user %s) — "
                    "skipping metrics fetch. User needs to reconnect.",
                    account.id, account.user_id,
                )
                return {
                    "error": "No page token for facebook — reconnect required",
                    "post_id": post_id,
                }
            token = page_token
        elif account.platform == "instagram":
            # Instagram stores its page token at metadata["page_access_token"],
            # NOT in metadata["pages"] (that's the Facebook structure).
            # account.access_token is also the page token (set during OAuth).
            page_token = meta.get("page_access_token") or account.access_token
            if not page_token:
                logger.warning(
                    "No page access token for Instagram account %s (user %s) — "
                    "skipping metrics fetch. User needs to reconnect.",
                    account.id, account.user_id,
                )
                return {
                    "error": "No page token for instagram — reconnect required",
                    "post_id": post_id,
                }
            token = page_token

        metrics_data = provider.get_post_metrics(
            access_token=token,
            platform_post_id=post.platform_post_id,
        )
    except Exception as e:
        error_str = str(e)
        # Detect permission errors and activate circuit breaker
        if "pages_read_engagement" in error_str or "OAuthException" in error_str:
            meta = account.metadata or {}
            meta["metrics_permission_error_at"] = timezone.now().isoformat()
            account.metadata = meta
            account.save(update_fields=["metadata", "updated_at"])
            logger.warning(
                "Circuit breaker activated for %s account %s — "
                "permission error, will skip metrics for 6 hours. "
                "User needs to reconnect with pages_read_engagement.",
                account.platform, account.id,
            )
        else:
            logger.warning("Failed to fetch metrics for post %s: %s", post_id, e)
        return {"error": error_str}

    metric, _created = PostMetric.objects.update_or_create(
        post=post,
        defaults={
            "impressions": metrics_data.impressions,
            "reach": metrics_data.reach,
            "likes": metrics_data.likes,
            "comments": metrics_data.comments,
            "shares": metrics_data.shares,
            "saves": metrics_data.saves,
            "clicks": metrics_data.clicks,
            "engagement_rate": _calc_engagement_rate(metrics_data),
        },
    )

    # Intelligence: validate engagement prediction against actual metrics
    from apps.agents.memory import validate_prediction
    validate_prediction(post)

    logger.info("Metrics updated for post %s", post_id)
    return {"success": True, "post_id": post_id}


def _calc_engagement_rate(metrics):
    """Calculate engagement rate from metrics."""
    total_engagement = metrics.likes + metrics.comments + metrics.shares + metrics.saves
    if metrics.impressions > 0:
        return round((total_engagement / metrics.impressions) * 100, 2)
    return 0.0


@shared_task(
    name="content.fetch_all_recent_metrics",
    soft_time_limit=10 * 60,
    time_limit=12 * 60,
)
@single_run("content.fetch_all_recent_metrics", timeout=15 * 60)
def fetch_all_recent_metrics():
    """
    Periodic task: fetch metrics for all posts published in the last 7 days.
    Should be called by Celery Beat every 6 hours.
    """
    from datetime import timedelta

    from apps.content.models import Post

    cutoff = timezone.now() - timedelta(days=7)
    recent_posts = Post.objects.filter(
        status=Post.Status.PUBLISHED,
        published_at__gte=cutoff,
        platform_post_id__gt="",
    ).values_list("id", flat=True)

    count = 0
    for post_id in recent_posts:
        fetch_post_metrics.delay(str(post_id))
        count += 1

    if count:
        logger.info("Queued metrics fetch for %d recent posts", count)
    return {"queued": count}


# ── A/B Testing Tasks ────────────────────────────────────────────────────────

@shared_task(name="content.generate_ab_test_variants", soft_time_limit=5 * 60, time_limit=6 * 60)
def generate_ab_test_variants(ab_test_id: str):
    """
    Run the Create Agent to generate variants for an A/B test.
    Called when user creates a new A/B test.
    """
    from apps.content.models import ABTest
    from apps.agents.create_agent import generate_ab_variants
    from apps.agents.analyst_agent import extract_content_dna, predict_engagement

    try:
        ab_test = ABTest.objects.select_related(
            "user", "user__profile", "social_account", "seed",
        ).get(pk=ab_test_id)
    except ABTest.DoesNotExist:
        logger.error("ABTest %s not found", ab_test_id)
        return {"error": "ABTest not found"}

    posts = generate_ab_variants(ab_test)

    # Tag each variant with Content DNA and engagement prediction
    for post in posts:
        try:
            extract_content_dna(post)
        except Exception as e:
            logger.warning("Content DNA extraction failed for variant %s: %s", post.id, e)
        try:
            predict_engagement(post)
        except Exception as e:
            logger.warning("Engagement prediction failed for variant %s: %s", post.id, e)

    return {
        "ab_test_id": str(ab_test_id),
        "variants_created": len(posts),
        "post_ids": [str(p.id) for p in posts],
    }


@shared_task(name="content.evaluate_ab_tests", soft_time_limit=10 * 60, time_limit=12 * 60)
@single_run("content.evaluate_ab_tests", timeout=15 * 60)
def evaluate_ab_tests():
    """
    Periodic task: find running A/B tests past their duration and evaluate them.
    Should be called by Celery Beat every hour.
    """
    from datetime import timedelta
    from apps.content.models import ABTest
    from apps.agents.analyst_agent import evaluate_ab_test

    now = timezone.now()
    overdue_tests = ABTest.objects.filter(
        status=ABTest.Status.RUNNING,
        started_at__isnull=False,
    ).select_related("user", "social_account")

    evaluated = 0
    for test in overdue_tests:
        if now > test.started_at + timedelta(hours=test.test_duration_hours):
            try:
                evaluate_ab_test(test)
                evaluated += 1
            except Exception as e:
                logger.error("Failed to evaluate A/B test %s: %s", test.id, e)

    if evaluated:
        logger.info("Auto-evaluated %d A/B tests", evaluated)
    return {"evaluated": evaluated}


# ── Content Recycling Engine ─────────────────────────────────────────────────

@shared_task(name="content.recycle_top_content", soft_time_limit=15 * 60, time_limit=18 * 60)
@single_run("content.recycle_top_content", timeout=20 * 60)
def recycle_top_content():
    """
    Find high-performing published posts (30+ days old) and create
    ContentSeeds to repurpose them on different platforms or with fresh angles.
    Runs daily. Max 1 recycle-seed per user per day.
    """
    from datetime import timedelta

    from django.contrib.auth import get_user_model
    from django.db.models import F, Q

    from apps.analytics.models import PostMetric
    from apps.content.models import ContentSeed, Post
    from apps.platforms.models import SocialAccount

    User = get_user_model()
    cutoff = timezone.now() - timedelta(days=30)
    recycled = 0

    for user in User.objects.filter(is_active=True):
        # Skip if already recycled recently
        recent_recycle = ContentSeed.objects.filter(
            user=user,
            notes__startswith="[Recycle]",
            created_at__gte=timezone.now() - timedelta(hours=24),
        ).exists()
        if recent_recycle:
            continue

        platforms = list(
            SocialAccount.objects.filter(user=user, is_active=True)
            .values_list("platform", flat=True)
        )
        if not platforms:
            continue

        # Find top-performing posts: published 30+ days ago, with good engagement
        top_posts = (
            Post.objects.filter(
                user=user,
                status=Post.Status.PUBLISHED,
                published_at__lte=cutoff,
                published_at__isnull=False,
                metrics__isnull=False,
            )
            .select_related("metrics")
            .order_by("-metrics__engagement_rate")[:10]
        )

        for post in top_posts:
            metrics = post.metrics
            # Require meaningful engagement
            total_engagement = (
                metrics.likes + metrics.comments + metrics.shares + metrics.saves
            )
            if total_engagement < 5:
                continue

            # Don't recycle the same post twice
            already_recycled = ContentSeed.objects.filter(
                user=user,
                notes__contains=str(post.id),
            ).exists()
            if already_recycled:
                continue

            # Pick different platforms for cross-posting
            other_platforms = [p for p in platforms if p != post.platform]
            target = other_platforms[:2] if other_platforms else [post.platform]

            seed = ContentSeed.objects.create(
                user=user,
                idea=(
                    f"Repurpose top-performing content:\n\n"
                    f"Original ({post.platform}): {post.content_text[:300]}\n\n"
                    f"Performance: {total_engagement} engagements, "
                    f"{metrics.engagement_rate or 0:.1f}% rate\n\n"
                    f"Give it a fresh angle for {', '.join(target)}."
                ),
                notes=f"[Recycle] From post {post.id} ({post.platform})",
                target_platforms=target,
            )
            generate_from_seed.delay(str(seed.pk))
            recycled += 1
            break  # Max 1 per user

    logger.info("Content recycling: created %d seeds", recycled)
    return {"recycled": recycled}


# ══════════════════════════════════════════════════════════════════════════════
# VOICE TO CAMPAIGN
# ══════════════════════════════════════════════════════════════════════════════


@shared_task(name="content.process_voice_brief", soft_time_limit=5 * 60, time_limit=6 * 60)
def process_voice_brief(voice_brief_id: str):
    """
    Process a voice memo into a full campaign.

    Pipeline: Audio → Whisper transcription → LLM intent extraction →
    Campaign creation → ContentSeed generation → optional EmailCampaign.
    """
    import time
    from django.utils import timezone

    from apps.content.models import VoiceBrief
    from apps.agents.models import AgentAction

    start = time.time()

    try:
        vb = VoiceBrief.objects.select_related("user", "user__profile").get(pk=voice_brief_id)
    except VoiceBrief.DoesNotExist:
        logger.error("VoiceBrief %s not found", voice_brief_id)
        return {"error": "not_found"}

    user = vb.user
    profile = getattr(user, "profile", None)

    try:
        # ── Step 1: Transcribe ──
        vb.status = VoiceBrief.Status.TRANSCRIBING
        vb.save(update_fields=["status"])

        from apps.agents.llm_router import call_llm, call_whisper
        transcript_result = call_whisper(vb.audio_file.path)
        vb.transcript = transcript_result.get("text", "")
        vb.language_detected = transcript_result.get("language", "en")
        vb.save(update_fields=["transcript", "language_detected"])

        if not vb.transcript.strip():
            raise ValueError("Transcription returned empty text")

        # ── Step 2: Extract intent ──
        vb.status = VoiceBrief.Status.EXTRACTING
        vb.save(update_fields=["status"])

        brand_context = ""
        if profile:
            brand_context = f"Industry: {profile.industry or 'general'}. Brand voice: {profile.brand_voice or 'professional'}."

        extraction_prompt = (
            "You are a marketing AI assistant. Extract structured campaign intent from this voice transcript.\n\n"
            f"Brand context: {brand_context}\n\n"
            f"Transcript: \"{vb.transcript}\"\n\n"
            "Return a JSON object with these keys:\n"
            "- products: list of product/service names mentioned\n"
            "- platforms: list of social platforms mentioned (instagram, facebook, twitter, tiktok, linkedin, whatsapp) — default to ['instagram', 'facebook'] if none mentioned\n"
            "- urgency: one of 'today', 'this_week', 'this_month', 'no_rush'\n"
            "- audience: target audience description if mentioned\n"
            "- cta_type: call-to-action type if mentioned (link, phone, whatsapp, email) or null\n"
            "- tone: detected tone (excited, urgent, casual, professional, etc.)\n"
            "- key_message: the core marketing message in one sentence\n"
            "- include_email: true if user mentioned email, subscribers, newsletter\n"
            "- include_whatsapp_status: true if user mentioned WhatsApp Status, WA status, status update, or posting to status\n"
            "- campaign_name: a suggested campaign name (short, catchy)\n"
            "Return ONLY valid JSON."
        )

        extraction_response = call_llm(
            prompt=extraction_prompt,
            task="voice_extraction",
            user=user,
            json_mode=True,
        )

        import json
        try:
            vb.ai_extraction = json.loads(extraction_response["text"])
        except (json.JSONDecodeError, KeyError):
            vb.ai_extraction = {"raw_response": extraction_response.get("text", ""), "key_message": vb.transcript[:200]}

        vb.save(update_fields=["ai_extraction"])

        # ── Step 3: Generate Campaign + Seeds via shared builder ──
        vb.status = VoiceBrief.Status.GENERATING
        vb.save(update_fields=["status"])

        extraction = vb.ai_extraction
        key_message = extraction.get("key_message", vb.transcript[:200])
        campaign_prompt = (
            f"{key_message}\n\n"
            f"Full voice transcript: {vb.transcript}\n\n"
            f"Tone: {extraction.get('tone', 'professional')}. "
            f"Products: {', '.join(extraction.get('products', []))}. "
            f"Audience: {extraction.get('audience', '')}. "
            f"Platforms to prioritize: {', '.join(extraction.get('platforms', []))}."
        )

        urgency = extraction.get("urgency", "this_week")
        duration_days = {"today": 3, "this_week": 7, "this_month": 14}.get(urgency, 7)

        transcript_lower = vb.transcript.lower()
        include_status = bool(extraction.get("include_whatsapp_status")) or any(
            phrase in transcript_lower
            for phrase in ("whatsapp status", "wa status", "status update", "post to status")
        )

        from apps.campaigns.tasks import build_campaign_from_prompt

        result = build_campaign_from_prompt(
            user,
            campaign_prompt,
            duration_days=duration_days,
            voice_brief=vb,
            include_email=bool(extraction.get("include_email")),
            include_status=include_status,
            auto_generate=True,
        )

        if result.get("error"):
            raise ValueError(result["error"])

        if result.get("email_campaign_id"):
            from apps.emails.models import EmailCampaign
            vb.email_campaign = EmailCampaign.objects.filter(pk=result["email_campaign_id"]).first()

        # ── Complete ──
        vb.status = VoiceBrief.Status.COMPLETED
        vb.completed_at = timezone.now()
        vb.processing_time_ms = int((time.time() - start) * 1000)
        vb.save()

        # Log agent action
        AgentAction.objects.create(
            user=user,
            agent_type="create",
            action_type="voice_to_campaign",
            input_data={"transcript": vb.transcript[:500]},
            output_data={
                "campaign_id": result.get("campaign_id"),
                "seeds": vb.seeds_created,
                "email_created": vb.email_campaign is not None,
            },
            tokens_used=extraction_response.get("tokens_used", 0),
            model_used=extraction_response.get("model", ""),
        )

        logger.info(
            "Voice brief %s completed: campaign=%s, seeds=%d, email=%s",
            voice_brief_id, result.get("campaign_id"), vb.seeds_created, bool(vb.email_campaign),
        )
        return {
            "status": "completed",
            "campaign_id": result.get("campaign_id"),
            "seeds_created": vb.seeds_created,
        }

    except Exception as e:
        logger.exception("Voice brief %s failed: %s", voice_brief_id, e)
        vb.status = VoiceBrief.Status.FAILED
        vb.error_message = str(e)[:1000]
        vb.save(update_fields=["status", "error_message"])


@shared_task(name="content.verify_tiktok_post", max_retries=3, soft_time_limit=30)
def verify_tiktok_post(post_id: str, tiktok_post_id: str, access_token: str):
    """
    Verify a TikTok post actually exists after publishing.

    TikTok occasionally returns a 200 success but the post never appears.
    This task runs 2 minutes after publish and re-checks via the TikTok API.
    If not found after 3 attempts (2min, 5min, 15min), notify the user.
    """
    import httpx
    from apps.content.models import Post
    from apps.notifications.models import Notification

    try:
        post = Post.objects.select_related("user", "social_account").get(pk=post_id)
    except Post.DoesNotExist:
        return {"error": "post_not_found"}

    try:
        resp = httpx.post(
            "https://open.tiktokapis.com/v2/video/list/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "filters": {"video_ids": [tiktok_post_id]},
                "fields": ["id", "title", "create_time"],
            },
            timeout=15.0,
        )
        data = resp.json()
        videos = data.get("data", {}).get("videos", [])
        if videos:
            logger.info("TikTok post %s verified — exists on platform", tiktok_post_id)
            return {"verified": True}

        # Not found yet — retry with increasing delays
        retry_delays = [300, 900]  # 5min, 15min
        attempt = verify_tiktok_post.request.retries
        if attempt < len(retry_delays):
            raise verify_tiktok_post.retry(countdown=retry_delays[attempt])

        # Still not found after all retries
        logger.warning("TikTok post %s not found after 3 checks — notifying user", tiktok_post_id)
        Notification.create_for_user(
            user=post.user,
            notification_type=Notification.NotificationType.SYSTEM,
            message=(
                f"⚠️ Your TikTok post may not have published correctly. "
                f"Check your TikTok profile to confirm it's live. "
                f"If it's missing, you can reschedule it from your Queue."
            ),
        )
        return {"verified": False}

    except verify_tiktok_post.MaxRetriesExceededError:
        return {"verified": False, "error": "max_retries"}
    except Exception as exc:
        logger.warning("TikTok verification error for post %s: %s", post_id, exc)
        return {"error": str(exc)}


# Autopilot tasks live in autopilot.py — import so Celery workers register them.
from apps.content.autopilot import (  # noqa: F401, E402
    execute_autopilot_plan,
    plan_user_week,
    plan_weekly_autopilot,
    send_autopilot_review_emails,
)
