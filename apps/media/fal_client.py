"""
Fal.ai client — Flux image edit + Kling video generation.

Docs: https://fal.ai/models
Uses queue API with polling. No-op when FAL_KEY is unset.
"""

from __future__ import annotations

import logging
import time
import uuid

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

FAL_QUEUE_BASE = "https://queue.fal.run"
MEDIA_FOLDER = "media_engine"


def fal_enabled() -> bool:
  if not getattr(settings, "MEDIA_ORCHESTRATION_ENABLED", True):
    return False
  return bool(getattr(settings, "FAL_KEY", "") or getattr(settings, "FAL_API_KEY", ""))


def _api_key() -> str:
  return (getattr(settings, "FAL_API_KEY", "") or getattr(settings, "FAL_KEY", "")).strip()


def _headers() -> dict[str, str]:
  return {
    "Authorization": f"Key {_api_key()}",
    "Content-Type": "application/json",
  }


def _submit(model_id: str, payload: dict) -> dict | None:
  url = f"{FAL_QUEUE_BASE}/{model_id}"
  try:
    resp = requests.post(url, json=payload, headers=_headers(), timeout=60)
    resp.raise_for_status()
    return resp.json()
  except Exception as exc:
    logger.warning("Fal submit failed (%s): %s", model_id, exc)
    return None


def _poll_result(queue_response: dict, *, max_wait_sec: int = 180) -> dict | None:
  status_url = queue_response.get("status_url") or queue_response.get("response_url")
  if not status_url:
    request_id = queue_response.get("request_id")
    if request_id:
      status_url = queue_response.get("status_url")
    if not status_url:
      return queue_response if queue_response.get("video") or queue_response.get("images") else None

  deadline = time.time() + max_wait_sec
  while time.time() < deadline:
    try:
      resp = requests.get(status_url, headers=_headers(), timeout=30)
      resp.raise_for_status()
      data = resp.json()
      status = (data.get("status") or "").upper()
      if status in ("COMPLETED", "OK", "SUCCESS") or data.get("video") or data.get("images"):
        return data
      if status in ("FAILED", "ERROR"):
        logger.warning("Fal job failed: %s", data.get("error") or data)
        return None
    except Exception as exc:
      logger.warning("Fal poll error: %s", exc)
    time.sleep(2)
  logger.warning("Fal poll timeout")
  return None


def _save_remote_video(url: str, *, prefix: str = "kling") -> str | None:
  try:
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    if len(resp.content) < 1000:
      return None
    path = f"{MEDIA_FOLDER}/{prefix}_{uuid.uuid4().hex[:12]}.mp4"
    saved = default_storage.save(path, ContentFile(resp.content))
    return default_storage.url(saved)
  except Exception as exc:
    logger.warning("Fal video save failed: %s", exc)
    return None


def _extract_video_url(result: dict) -> str | None:
  if not result:
    return None
  video = result.get("video")
  if isinstance(video, dict):
    return video.get("url")
  if isinstance(video, str):
    return video
  output = result.get("output")
  if isinstance(output, dict):
    v = output.get("video")
    if isinstance(v, dict):
      return v.get("url")
    return v
  return None


def _extract_image_url(result: dict) -> str | None:
  if not result:
    return None
  images = result.get("images") or result.get("output", {}).get("images")
  if isinstance(images, list) and images:
    first = images[0]
    if isinstance(first, dict):
      return first.get("url")
    if isinstance(first, str):
      return first
  image = result.get("image")
  if isinstance(image, dict):
    return image.get("url")
  return None


def generate_kling_reel(
  image_url: str,
  *,
  prompt: str,
  duration: str = "5",
  aspect_ratio: str = "9:16",
) -> str | None:
  """Image-to-video via Kling on Fal. Returns public video URL."""
  if not fal_enabled():
    return None
  model = getattr(settings, "FAL_KLING_MODEL", "fal-ai/kling-video/v2.1/master/image-to-video")
  payload = {
    "image_url": image_url,
    "prompt": prompt[:500],
    "duration": duration,
    "aspect_ratio": aspect_ratio,
  }
  queued = _submit(model, payload)
  if not queued:
    return None
  result = _poll_result(queued)
  video_url = _extract_video_url(result or {})
  if not video_url:
    return None
  return _save_remote_video(video_url, prefix="kling")


def flux_edit_image(
  image_url: str,
  *,
  prompt: str,
) -> str | None:
  """Creative image transform via Flux on Fal. Returns image URL."""
  if not fal_enabled():
    return None
  model = getattr(settings, "FAL_FLUX_EDIT_MODEL", "fal-ai/flux-pro/kontext")
  payload = {
    "image_url": image_url,
    "prompt": prompt[:800],
  }
  queued = _submit(model, payload)
  if not queued:
    return None
  result = _poll_result(queued, max_wait_sec=120)
  out_url = _extract_image_url(result or {})
  return out_url
