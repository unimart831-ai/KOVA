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
  Build up to 5 branded carousel slide URLs via Bannerbear templates.
  Returns empty list when templates or API are not configured.
  """
  template = _template_uid("product_carousel_cover")
  if not template:
    return []

  images = list(product.all_image_urls or [])
  if not images:
    return []

  slides: list[str] = []
  price = product.display_price or ""
  features = key_features or []

  cover = render_template(
    template,
    dna.bannerbear_modifications(
      title=product.name,
      subtitle=(product.description or "")[:120],
      price=price,
      image_url=images[0],
      cta="Shop now",
    ),
  )
  if cover:
    slides.append(cover)

  feature_template = _template_uid("product_carousel_slide")
  if feature_template:
    for idx, feat in enumerate(features[:3]):
      img = images[min(idx + 1, len(images) - 1)]
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
    url = render_template(
      cta_template,
      dna.bannerbear_modifications(
        title=product.name,
        price=price,
        cta="Order on WhatsApp",
        image_url=images[0],
      ),
    )
    if url:
      slides.append(url)

  return slides
