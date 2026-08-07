"""
Platform fit scoring — extends QA with per-platform native quality (0–100).

Publishing threshold for platform_fit: minimum 80 (configurable).
"""

from __future__ import annotations

import re
from typing import Any

from django.conf import settings

PLATFORM_FIT_MIN_SCORE = int(getattr(settings, "PLATFORM_FIT_MIN_SCORE", 80))

PLATFORM_FIT_RULES = {
    "instagram": {
        "tone_markers": ("you", "your", "save", "swipe", "✨", "💫"),
        "avoid": ("dear sir", "to whom", "hereby"),
        "format_bonus": ("carousel", "reel", "story"),
    },
    "facebook": {
        "tone_markers": ("?", "share", "community", "we", "us", "your thoughts"),
        "avoid": ("#fyp", "link in bio only"),
        "format_bonus": ("text", "image"),
    },
    "tiktok": {
        "tone_markers": ("!", "wait", "pov", "secret", "hack", "#"),
        "avoid": ("furthermore", "pursuant", "stakeholders"),
        "format_bonus": ("reel",),
    },
    "linkedin": {
        "tone_markers": ("insight", "lesson", "strategy", "business", "growth", "team"),
        "avoid": ("#fyp", "omg", "🔥🔥"),
        "format_bonus": ("text",),
    },
}


def score_platform_fit(
    post,
    *,
    blueprint: dict | None = None,
    audience: str = "",
) -> tuple[int, list[str]]:
    """
    Score 0–100: tone match, format match, CTA suitability, audience alignment.
    """
    def _attr(name: str, default: str = "") -> str:
        if isinstance(post, dict):
            return str(post.get(name, default) or default)
        return str(getattr(post, name, default) or default)

    plat = _attr("platform").lower()
    text = _attr("content_text").strip()
    fmt = _attr("post_format", "text").lower()
    issues: list[str] = []
    score = 65

    rules = PLATFORM_FIT_RULES.get(plat)
    if not rules:
        return 75, issues

    lower = text.lower()
    marker_hits = sum(1 for m in rules["tone_markers"] if m.lower() in lower)
    if marker_hits >= 2:
        score += 15
    elif marker_hits == 1:
        score += 8
    else:
        issues.append(f"Tone may not feel native on {plat}")

    for bad in rules["avoid"]:
        if bad.lower() in lower:
            score -= 12
            issues.append(f"Phrasing awkward for {plat}")

    if fmt in rules["format_bonus"]:
        score += 10

    # CTA suitability
    cta_url = _attr("cta_url")
    if cta_url:
        score += 8
    elif plat in ("instagram", "tiktok") and "link" in lower:
        score += 5
    else:
        issues.append("Weak CTA for platform")

    # Strong blueprint alignment implies native rewrite already applied
    dna = getattr(post, "content_dna", None) or {}
    if isinstance(dna, dict) and int(dna.get("blueprint_quality") or 0) >= 80:
        score += 10
    if getattr(post, "platform_rewritten", False) if not isinstance(post, dict) else post.get("platform_rewritten"):
        score += 8

    # Audience alignment (light heuristic)
    if audience and len(audience) > 5:
        aud_words = [w for w in audience.lower().split() if len(w) > 4][:5]
        if any(w in lower for w in aud_words):
            score += 7

    if blueprint:
        objective = str(blueprint.get("objective", "")).lower()
        if objective == "sales" and plat == "linkedin" and "buy now" in lower:
            score -= 5
            issues.append("Hard sell tone on LinkedIn")

    return max(0, min(100, score)), issues[:3]


def platform_fit_gate(score: int) -> tuple[bool, str]:
    if score < PLATFORM_FIT_MIN_SCORE:
        return False, f"Platform fit {score}/100 — minimum {PLATFORM_FIT_MIN_SCORE}"
    return True, ""


def enrich_post_qa_with_platform_fit(post_qa, post, *, blueprint=None, audience=""):
    """Add platform_fit to PostQAScore dimensions in-place style."""
    fit, fit_issues = score_platform_fit(post, blueprint=blueprint, audience=audience)
    post_qa.dimensions["platform_fit"] = fit
    post_qa.issues.extend(fit_issues)
    # Re-weight overall slightly toward platform_fit
    dims = post_qa.dimensions
    overall = int(round(
        dims.get("brand", 0) * 0.18
        + dims.get("visual", 0) * 0.22
        + dims.get("platform", 0) * 0.18
        + dims.get("platform_fit", 0) * 0.12
        + dims.get("cta", 0) * 0.18
        + dims.get("compliance", 0) * 0.12
    ))
    post_qa.overall = max(0, min(100, overall))
    return post_qa
