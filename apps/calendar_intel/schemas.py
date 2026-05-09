"""
Pydantic schemas for holiday-draft generation output.

The Claude generator returns structured JSON matching `HolidayDraftsOutput`.
We validate before persisting to ensure shape stability.

See KOVA_HOLIDAY_AWARENESS.md Appendix A.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# Per-platform max lengths matching the prompt's hard rules.
PLATFORM_LIMITS = {
    "instagram": 2200,
    "linkedin": 3000,
    "twitter": 280,
    "facebook": 63206,
}


class PlatformVersions(BaseModel):
    """Optional per-platform copy. The generator emits versions for the
    platforms the user actually has connected — the rest are None."""
    model_config = ConfigDict(extra="ignore")

    instagram: Optional[str] = Field(None, max_length=PLATFORM_LIMITS["instagram"])
    linkedin: Optional[str] = Field(None, max_length=PLATFORM_LIMITS["linkedin"])
    twitter: Optional[str] = Field(None, max_length=PLATFORM_LIMITS["twitter"])
    facebook: Optional[str] = Field(None, max_length=PLATFORM_LIMITS["facebook"])

    def items_with_content(self) -> list[tuple[str, str]]:
        """Return [(platform, text), ...] for platforms that actually have copy."""
        return [
            (k, v) for k, v in self.model_dump().items()
            if v and v.strip()
        ]


class HolidayDraftItem(BaseModel):
    """One angle/draft. May contain copy for multiple platforms (one Post each)."""
    model_config = ConfigDict(extra="ignore")

    angle_used: str = Field(..., min_length=3, max_length=200)
    rationale: str = Field("", max_length=500)
    platform_versions: PlatformVersions
    suggested_publish_time: Optional[str] = Field(
        None,
        description="ISO 8601 datetime in user-local time. Optional — falls back "
                    "to a sensible default if missing.",
    )


class HolidayDraftsOutput(BaseModel):
    """Top-level schema returned by the generator."""
    model_config = ConfigDict(extra="ignore")

    drafts: list[HolidayDraftItem] = Field(..., min_length=1, max_length=4)
