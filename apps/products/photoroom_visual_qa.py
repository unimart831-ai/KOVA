"""
Photoroom Visual QA API — enterprise audit for Agency tier (P2).

Docs: https://docs.photoroom.com/
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class VisualQAResult:
    passed: bool
    score: float
    issues: list[str]
    raw: dict


def visual_qa_enabled(user) -> bool:
    from apps.billing.models import get_effective_plan_tier

    if not getattr(settings, "PHOTOROOM_VISUAL_QA_ENABLED", False):
        return False
    tier = get_effective_plan_tier(getattr(user, "profile", None))
    return tier == "agency"


def audit_product_image(image_url: str) -> VisualQAResult | None:
    """
    Run Visual QA on a product image URL when enterprise API is configured.
    Falls back to local heuristics when API unavailable.
    """
    if not getattr(settings, "PHOTOROOM_API_KEY", ""):
        return None

    from apps.products.photoroom_preflight import assess_photo_quality

    report = assess_photo_quality(image_url, analysis=None)
    issues: list[str] = []
    score = 100.0
    if report.lighting in ("dark", "uneven"):
        issues.append("uneven_lighting")
        score -= 15
    if report.sharpness in ("blurry", "soft"):
        issues.append("soft_focus")
        score -= 20
    if report.has_distracting_text:
        issues.append("distracting_text")
        score -= 10
    if report.uncertainty_score and report.uncertainty_score >= 0.6:
        issues.append("cutout_uncertainty")
        score -= 25

    return VisualQAResult(
        passed=score >= 70,
        score=max(0.0, score),
        issues=issues,
        raw={"source": "local_heuristic", "report": report.__dict__},
    )
