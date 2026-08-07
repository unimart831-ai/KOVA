"""Audience DNA — structured audience fields + inference."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class AudienceDNA:
    primary_audience: str = ""
    pain_points: list[str] | None = None
    desires: list[str] | None = None
    geography: str = ""
    buying_stage: str = "consideration"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def infer_audience_dna(user, profile=None) -> AudienceDNA:
    profile = profile or getattr(user, "profile", None)
    if not profile:
        return AudienceDNA()
    audience = (profile.target_audience or "").strip()
    pains: list[str] = []
    desires: list[str] = []
    if profile.content_pillars:
        desires.extend([str(p) for p in profile.content_pillars[:3]])
    country = (getattr(profile, "country", None) or "").strip()
    return AudienceDNA(
        primary_audience=audience,
        pain_points=pains,
        desires=desires,
        geography=country,
        buying_stage="consideration",
    )
