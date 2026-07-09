"""
Bannerbear client — branded carousel slide generation.

Docs: https://developers.bannerbear.com/
"""

from __future__ import annotations

import logging
import time

import requests
from django.conf import settings

from apps.media.brand_dna import BrandDNA

logger = logging.getLogger(__name__)

BANNERBEAR_API = "https://api.bannerbear.com/v2"


def bannerbear_enabled() -> bool:
  if not getattr(settings, "MEDIA_ORCHESTRATION_ENABLED", True):
    return False
  return bool(getattr(settings, "BANNERBEAR_API_KEY", ""))


def _headers() -> dict[str, str]:
  return {
    "Authorization": f"Bearer {settings.BANNERBEAR_API_KEY}",
    "Content-Type": "application/json",
  }


def _template_uid(plan_key: str) -> str:
  templates = getattr(settings, "BANNERBEAR_TEMPLATES", {}) or {}
  return (templates.get(plan_key) or "").strip()


def _poll_image(uid: str, *, max_wait_sec: int = 90) -> str | None:
  url = f"{BANNERBEAR_API}/images/{uid}"
  deadline = time.time() + max_wait_sec
  while time.time() < deadline:
    try:
      resp = requests.get(url, headers=_headers(), timeout=30)
      resp.raise_for_status()
      data = resp.json()
      if data.get("status") == "completed":
        return data.get("image_url") or data.get("image_url_png")
      if data.get("status") == "failed":
        logger.warning("Bannerbear image failed: %s", data)
        return None
    except Exception as exc:
      logger.warning("Bannerbear poll error: %s", exc)
    time.sleep(2)
  return None


def render_template(
  template_uid: str,
  modifications: list[dict],
  *,
  sync: bool = False,
) -> str | None:
  if not bannerbear_enabled() or not template_uid:
    return None
  payload = {
    "template": template_uid,
    "modifications": modifications,
  }
  if sync:
    payload["sync"] = "true"
  try:
    resp = requests.post(f"{BANNERBEAR_API}/images", json=payload, headers=_headers(), timeout=90)
    resp.raise_for_status()
    data = resp.json()
    if data.get("image_url"):
      return data["image_url"]
    uid = data.get("uid")
    if uid:
      return _poll_image(uid)
  except Exception as exc:
    logger.warning("Bannerbear render failed: %s", exc)
  return None


def build_product_carousel_slides(
  product,
  dna: BrandDNA,
  *,
  key_features: list | None = None,
) -> list[str]:
  """
  Build up to 6 branded carousel slide URLs via Bannerbear templates.

  Arc: cover → feature slides (unique images) → CTA with price.
  Returns empty list when templates or API are not configured.
  """
  template = _template_uid("product_carousel_cover")
  if not template:
    return []

  images = list(product.all_image_urls or [])
  if not images:
    return []

  # Prefer studio-polished assets when available (same curation as Pillow path)
  try:
    from apps.content.carousel_studio import curate_carousel_images

    curated = curate_carousel_images(images)
    if curated:
      images = curated
  except Exception:
    pass

  slides: list[str] = []
  price = product.display_price or ""
  features = [str(f).strip() for f in (key_features or []) if str(f).strip()]
  used_images: set[str] = set()

  def _next_image(preferred_idx: int) -> str:
    if preferred_idx < len(images) and images[preferred_idx] not in used_images:
      return images[preferred_idx]
    for img in images:
      if img not in used_images:
        return img
    return images[preferred_idx % len(images)]

  cover_img = _next_image(0)
  used_images.add(cover_img)
  cover = render_template(
    template,
    dna.bannerbear_modifications(
      title=product.name,
      subtitle=(product.description or "")[:120],
      price=price,
      image_url=cover_img,
      cta="Swipe for details →",
    ),
  )
  if cover:
    slides.append(cover)

  feature_template = _template_uid("product_carousel_slide")
  if feature_template:
    for idx, feat in enumerate(features[:3]):
      img = _next_image(idx + 1)
      used_images.add(img)
      url = render_template(
        feature_template,
        dna.bannerbear_modifications(
          title=str(feat)[:80],
          subtitle=dna.brand_name,
          image_url=img,
        ),
      )
      if url:
        slides.append(url)

  cta_template = _template_uid("product_carousel_cta")
  if cta_template and price:
    # Prefer a different image than the cover for the CTA slide
    cta_img = _next_image(1 if len(images) > 1 else 0)
    url = render_template(
      cta_template,
      dna.bannerbear_modifications(
        title=product.name,
        price=price,
        cta="Order on WhatsApp",
        image_url=cta_img,
      ),
    )
    if url:
      slides.append(url)

  return slides
