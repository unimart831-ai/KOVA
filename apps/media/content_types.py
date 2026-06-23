"""Content format types and media production plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ContentFormat(str, Enum):
  SINGLE_POST = "single_post"
  CAROUSEL = "carousel"
  STORY = "story"
  REEL = "reel"
  TIKTOK = "tiktok"
  WHATSAPP_OFFER = "whatsapp_offer"


class EnhancementBackend(str, Enum):
  PHOTOROOM = "photoroom"
  FLUX_EDIT = "flux_edit"
  NONE = "none"


class ReelBackend(str, Enum):
  KLING = "kling"
  PHOTOROOM = "photoroom"
  FFMPEG = "ffmpeg"


class CarouselBackend(str, Enum):
  BANNERBEAR = "bannerbear"
  LOCAL = "local"


@dataclass
class MediaPlan:
  """What to produce from one business asset."""

  formats: list[ContentFormat] = field(default_factory=list)
  enhancement: EnhancementBackend = EnhancementBackend.PHOTOROOM
  reel_backend: ReelBackend = ReelBackend.FFMPEG
  carousel_backend: CarouselBackend = CarouselBackend.LOCAL
  scene_pack: str = "auto"
  kling_prompt: str = ""
  flux_edit_prompt: str = ""
  rationale: str = ""

  def to_metadata(self) -> dict:
    return {
      "formats": [f.value for f in self.formats],
      "enhancement": self.enhancement.value,
      "reel_backend": self.reel_backend.value,
      "carousel_backend": self.carousel_backend.value,
      "scene_pack": self.scene_pack,
      "kling_prompt": self.kling_prompt,
      "flux_edit_prompt": self.flux_edit_prompt,
      "rationale": self.rationale,
    }

  @classmethod
  def from_metadata(cls, data: dict | None) -> MediaPlan:
    if not isinstance(data, dict):
      return cls()
    formats = []
    for raw in data.get("formats") or []:
      try:
        formats.append(ContentFormat(raw))
      except ValueError:
        continue
    try:
      enhancement = EnhancementBackend(data.get("enhancement", "photoroom"))
    except ValueError:
      enhancement = EnhancementBackend.PHOTOROOM
    try:
      reel_backend = ReelBackend(data.get("reel_backend", "ffmpeg"))
    except ValueError:
      reel_backend = ReelBackend.FFMPEG
    try:
      carousel_backend = CarouselBackend(data.get("carousel_backend", "local"))
    except ValueError:
      carousel_backend = CarouselBackend.LOCAL
    return cls(
      formats=formats,
      enhancement=enhancement,
      reel_backend=reel_backend,
      carousel_backend=carousel_backend,
      scene_pack=data.get("scene_pack") or "auto",
      kling_prompt=data.get("kling_prompt") or "",
      flux_edit_prompt=data.get("flux_edit_prompt") or "",
      rationale=data.get("rationale") or "",
    )
