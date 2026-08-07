"""Reel composition bridge — Kling via Fal."""

from __future__ import annotations

import logging
import uuid

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from apps.create.media.content_types import MediaPlan
from apps.create.media.fal_client import generate_kling_reel

logger = logging.getLogger(__name__)


def _attach_video_to_post(post, video_url: str, *, backend: str = "kling") -> str:
  from apps.create.content.models import MediaAttachment, Post

  if video_url.startswith(("http://", "https://")):
    import requests
    resp = requests.get(video_url, timeout=120)
    resp.raise_for_status()
    mp4_bytes = resp.content
  else:
    mp4_bytes = b""

  path = f"reels/kling_{post.pk}_{uuid.uuid4().hex[:8]}.mp4"
  saved = default_storage.save(path, ContentFile(mp4_bytes))
  public_url = default_storage.url(saved)

  MediaAttachment.objects.create(
    post=post,
    file=saved,
    file_type="video",
    order=0,
  )

  meta = dict(post.visual_metadata or {})
  meta["video_compose_status"] = "done"
  meta["reel_compose_backend"] = backend
  meta["reel_video_url"] = public_url
  post.visual_metadata = meta
  post.media_urls = [public_url] + [u for u in (post.media_urls or []) if u != public_url]
  post.media_status = Post.MediaStatus.GENERATED
  post.save(update_fields=["visual_metadata", "media_urls", "media_status", "updated_at"])
  return public_url


def try_kling_reel_for_post(post, image_sources: list[str]) -> str | None:
  """Generate reel via Kling when media plan requests it (QA-gated)."""
  from apps.create.content.campaign_qa import score_post_qa
  from django.conf import settings

  min_qa = int(getattr(settings, "KLING_MIN_CAMPAIGN_QA", 75))
  seed = getattr(post, "seed", None)
  campaign = getattr(seed, "marketing_campaign", None) if seed else None
  if campaign and campaign.quality_score and campaign.quality_score < min_qa:
    ps = score_post_qa(post, seed=seed)
    if ps.overall < min_qa:
      logger.info(
        "Kling blocked for post %s — campaign QA %s < %s",
        post.pk, ps.overall, min_qa,
      )
      return None

  prompt = (post.visual_metadata or {}).get("kling_prompt") or ""
  if not prompt and post.product_id:
    try:
      plan = MediaPlan.from_metadata(
        (post.product.business_asset.metadata or {}).get("media_plan")
      )
      prompt = plan.kling_prompt
    except Exception:
      pass
  if not prompt:
    prompt = f"Professional product showcase for {post.platform}"

  hero = image_sources[0] if image_sources else None
  if not hero:
    return None

  video_url = generate_kling_reel(hero, prompt=prompt)
  if not video_url:
    return None

  try:
    return _attach_video_to_post(post, video_url, backend="kling")
  except Exception as exc:
    logger.warning("Kling reel attach failed for post %s: %s", post.pk, exc)
    return None
