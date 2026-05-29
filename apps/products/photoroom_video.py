"""
Photoroom Video API — generates product videos from static images.
Used for auto-generating Reels/TikTok content from Snap2sell photos.

API: POST https://image-api.photoroom.com/v1/animate
- Input: product image (multipart imageFile or public HTTPS URL)
- Output: MP4 video (3-7 seconds)

Docs: https://docs.photoroom.com/video-api-enterprise-plan/overview
"""
from __future__ import annotations

import logging
import uuid

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

PHOTOROOM_VIDEO_URL = "https://image-api.photoroom.com/v1/animate"
VIDEO_FOLDER = "product_videos"


def video_generation_enabled() -> bool:
    """Video API available when keyed; sandbox mode allows watermarked test calls."""
    if not getattr(settings, "PHOTOROOM_API_KEY", ""):
        return False
    if getattr(settings, "PHOTOROOM_VIDEO_ENABLED", False):
        return True
    if getattr(settings, "PHOTOROOM_REEL_USE_VIDEO_API", True):
        return bool(getattr(settings, "PHOTOROOM_SANDBOX", False))
    return False


def reel_should_use_photoroom_video(post) -> bool:
    """Commerce reels prefer Photoroom animate when enabled (single hero frame)."""
    if not video_generation_enabled():
        return False
    if not getattr(settings, "PHOTOROOM_REEL_USE_VIDEO_API", True):
        return False
    meta = post.visual_metadata or {}
    if meta.get("reel_compose_backend") == "ffmpeg":
        return False
    return True


def _resolve_image_url(image_url: str) -> str | None:
    from apps.products.photoroom import _resolve_public_image_url

    if image_url.startswith(("http://", "https://")):
        return image_url
    return _resolve_public_image_url(image_url)


def _load_image_for_video(image_url: str) -> tuple[bytes, str] | None:
    from apps.products.photoroom import _load_image_bytes

    if image_url.startswith(("http://", "https://")):
        try:
            resp = requests.get(image_url, timeout=60)
            resp.raise_for_status()
            if resp.content and len(resp.content) > 500:
                return resp.content, "image.jpg"
        except Exception as exc:
            logger.warning("Photoroom video image download failed: %s", exc)
    return _load_image_bytes(image_url)


def generate_product_video(
    image_url: str,
    prompt: str = "Slowly rotate the product with soft lighting",
    duration_seconds: int = 5,
    aspect_ratio: str = "9:16",
) -> str | None:
    """
    Generate a product video from a static image via Photoroom Video API.

    Returns storage path to the saved MP4 file, or None on failure.
    """
    from apps.products.photoroom import _api_key_headers
    from apps.products.photoroom_api import check_sandbox_quota, record_sandbox_call

    allowed, limit_msg = check_sandbox_quota()
    if not allowed:
        logger.warning("Photoroom video skipped: %s", limit_msg)
        return None

    api_key, headers = _api_key_headers()
    if not api_key:
        logger.warning("Photoroom API key not configured for video generation")
        return None

    headers = {**headers, "Accept": "video/mp4"}

    form_data = {
        "prompt": prompt,
        "durationSeconds": str(min(max(duration_seconds, 3), 7)),
        "aspectRatio": aspect_ratio,
    }

    loaded = _load_image_for_video(image_url)
    files = None
    if loaded:
        file_bytes, file_name = loaded
        files = {"imageFile": (file_name, file_bytes, "image/jpeg")}
    else:
        public_url = _resolve_image_url(image_url)
        if not public_url or not public_url.startswith("https://"):
            logger.warning(
                "Photoroom Video needs image bytes or a public HTTPS URL, got: %s",
                (image_url or "")[:80],
            )
            return None
        form_data["imageUrl"] = public_url

    try:
        resp = requests.post(
            PHOTOROOM_VIDEO_URL,
            headers=headers,
            data=form_data,
            files=files,
            timeout=120,
        )
        if resp.status_code != 200:
            logger.error(
                "Photoroom Video API error %s: %s",
                resp.status_code,
                resp.text[:200],
            )
            return None

        video_bytes = resp.content
        if not video_bytes or len(video_bytes) < 1000:
            logger.warning("Photoroom returned empty or tiny video response")
            return None

        record_sandbox_call()

        filename = f"{VIDEO_FOLDER}/{uuid.uuid4().hex}.mp4"
        saved_path = default_storage.save(filename, ContentFile(video_bytes))
        logger.info("Product video saved: %s (%d bytes)", saved_path, len(video_bytes))
        return saved_path

    except requests.Timeout:
        logger.error("Photoroom Video API timed out (120s)")
        return None
    except Exception:
        logger.exception("Photoroom Video API unexpected error")
        return None


def generate_product_reel_video(product, image_url: str | None = None) -> str | None:
    """Generate a reel-ready video for a product."""
    if not video_generation_enabled():
        return None

    if not image_url:
        image_url = _get_best_product_image_url(product)
    if not image_url:
        return None

    prompt = _build_video_prompt(product)

    path = generate_product_video(
        image_url=image_url,
        prompt=prompt,
        duration_seconds=5,
        aspect_ratio="9:16",
    )

    if path:
        try:
            from apps.agents.models import AgentAction

            AgentAction.objects.create(
                user=product.user,
                agent_type="create",
                action_type="commerce.video_generation",
                description=f"Generated product video for {product.name}",
                status=AgentAction.ActionStatus.COMPLETED,
                input_data={"product_id": str(product.pk), "prompt": prompt},
                output_data={"video_path": path},
            )
        except Exception:
            pass

    return path


def pick_reel_video_image_url(post, image_sources: list[str]) -> str | None:
    """Best single frame for /v1/animate (story polish or composition hero)."""
    meta = post.visual_metadata or {}
    hero = meta.get("composition_hero_url")
    if hero:
        return hero

    for url in image_sources:
        if url and "channel_story" in url:
            return url

    for url in image_sources:
        if url and ("studio_polish" in url or "studio_white" in url):
            return url

    return image_sources[0] if image_sources else None


def attach_photoroom_video_to_post(post, video_storage_path: str, *, thumbnail_url: str | None = None) -> str | None:
    """Attach MP4 to post and return public video URL."""
    from apps.content.models import MediaAttachment, Post
    from apps.content.tasks import _public_url_for_file

    public_url = _public_url_for_file(video_storage_path)
    if not public_url:
        return None

    post.attachments.filter(file_type="video").delete()
    MediaAttachment.objects.create(
        post=post,
        file=video_storage_path,
        file_type="video",
        order=0,
        alt_text="Photoroom product video",
    )

    meta = dict(post.visual_metadata or {})
    meta.update({
        "video_compose_status": "done",
        "reel_compose_backend": "photoroom_animate",
        "reel_video_url": public_url,
        "reel_thumbnail_url": thumbnail_url,
    })
    post.visual_metadata = meta
    post.media_urls = [public_url]
    post.aspect_ratio = Post.AspectRatio.STORY
    post.media_status = Post.MediaStatus.GENERATED
    post.save(update_fields=[
        "visual_metadata", "media_urls", "aspect_ratio", "media_status", "updated_at",
    ])
    return public_url


def try_photoroom_reel_for_post(post, image_sources: list[str]) -> str | None:
    """
    Attempt Photoroom /v1/animate for commerce reels. Returns public video URL or None.
    """
    if not reel_should_use_photoroom_video(post):
        return None

    image_url = pick_reel_video_image_url(post, image_sources)
    if not image_url:
        return None

    product = post.product
    if product:
        path = generate_product_reel_video(product, image_url=image_url)
    else:
        prompt = "Professional product showcase with gentle motion and studio lighting"
        path = generate_product_video(image_url=image_url, prompt=prompt)

    if not path:
        return None

    thumb = None
    for url in post.media_urls or image_sources:
        if url and not url.endswith(".mp4"):
            thumb = url
            break

    return attach_photoroom_video_to_post(post, path, thumbnail_url=thumb)


def _get_best_product_image_url(product) -> str | None:
    """Get the best available product image URL for video generation."""
    additional = product.additional_images or []
    for img_url in additional:
        if "channel_story" in img_url:
            return img_url
    for img_url in additional:
        if "studio_polish" in img_url or "product_variations" in img_url:
            return img_url

    if product.image:
        try:
            return product.image.url
        except Exception:
            pass

    if additional:
        return additional[0]

    return None


def _build_video_prompt(product) -> str:
    """Build an appropriate video motion prompt based on product type."""
    from apps.products.models import Product

    offering = getattr(product, "offering_type", Product.OfferingType.PRODUCT)
    category = ""
    if product.category:
        category = product.category.name.lower()

    if offering == Product.OfferingType.SERVICE:
        return "Gently animate with a professional motion effect, subtle zoom and lighting shift"

    if offering == Product.OfferingType.DIGITAL:
        return "Smooth reveal animation with a gentle glow effect and modern transitions"

    if "food" in category or "restaurant" in category:
        return "Slow appetizing reveal with steam or warmth effect, soft lighting"
    if "fashion" in category or "apparel" in category or "shoe" in category:
        return "Elegant slow rotation showcasing details, with soft studio lighting"
    if "beauty" in category or "cosmetic" in category:
        return "Luxurious slow zoom with sparkle highlights and soft reflections"
    if "electronics" in category or "tech" in category:
        return "Sleek modern rotation with subtle light reflections on the surface"
    if "jewelry" in category:
        return "Slow glamorous rotation with sparkle and light play"

    return "Professional product showcase with gentle rotation and studio lighting"
