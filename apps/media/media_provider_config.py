"""
Centralized media provider configuration — no hardcoded API keys.

Reads from Django settings and exposes availability checks for orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.conf import settings


@dataclass(frozen=True)
class MediaProviderConfig:
    """Runtime config for external media providers."""

    photoroom_api_key: str = ""
    photoroom_basic_api_key: str = ""
    bannerbear_api_key: str = ""
    fal_key: str = ""
    media_orchestration_enabled: bool = False
    bannerbear_templates: dict[str, str] = field(default_factory=dict)
    fal_kling_model: str = ""
    fal_flux_model: str = ""

    @classmethod
    def from_settings(cls) -> MediaProviderConfig:
        templates = dict(getattr(settings, "BANNERBEAR_TEMPLATES", {}) or {})
        return cls(
            photoroom_api_key=(getattr(settings, "PHOTOROOM_API_KEY", "") or "").strip(),
            photoroom_basic_api_key=(getattr(settings, "PHOTOROOM_BASIC_API_KEY", "") or "").strip(),
            bannerbear_api_key=(getattr(settings, "BANNERBEAR_API_KEY", "") or "").strip(),
            fal_key=(
                getattr(settings, "FAL_KEY", "")
                or getattr(settings, "FAL_API_KEY", "")
                or ""
            ).strip(),
            media_orchestration_enabled=bool(getattr(settings, "MEDIA_ORCHESTRATION_ENABLED", False)),
            bannerbear_templates=templates,
            fal_kling_model=getattr(settings, "FAL_KLING_MODEL", "") or "",
            fal_flux_model=getattr(settings, "FAL_FLUX_EDIT_MODEL", "") or "",
        )

    @property
    def photoroom_ready(self) -> bool:
        return bool(self.photoroom_api_key or self.photoroom_basic_api_key)

    @property
    def bannerbear_ready(self) -> bool:
        return self.media_orchestration_enabled and bool(
            self.bannerbear_api_key and self.bannerbear_templates
        )

    @property
    def fal_ready(self) -> bool:
        return self.media_orchestration_enabled and bool(self.fal_key)

    def missing_for_production(self) -> list[str]:
        """Human-readable gaps for deploy checklists."""
        gaps: list[str] = []
        if not self.photoroom_ready:
            gaps.append("PHOTOROOM_API_KEY")
        if not self.bannerbear_ready:
            if not self.bannerbear_api_key:
                gaps.append("BANNERBEAR_API_KEY")
            if not self.bannerbear_templates:
                gaps.append("BANNERBEAR_TEMPLATES (cover/slide/cta UIDs)")
        if not self.fal_ready:
            gaps.append("FAL_KEY (optional — Kling/Flux)")
        return gaps

    def to_dict(self) -> dict[str, Any]:
        return {
            "photoroom_ready": self.photoroom_ready,
            "bannerbear_ready": self.bannerbear_ready,
            "fal_ready": self.fal_ready,
            "media_orchestration_enabled": self.media_orchestration_enabled,
            "bannerbear_template_keys": list(self.bannerbear_templates.keys()),
            "missing": self.missing_for_production(),
        }


def get_media_provider_config() -> MediaProviderConfig:
    return MediaProviderConfig.from_settings()
