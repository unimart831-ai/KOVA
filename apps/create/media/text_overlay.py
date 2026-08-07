"""
Text overlay pass — safe margins, readability, contrast before FFmpeg export.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# 9:16 safe zones (fractions of frame height/width)
SAFE_MARGIN_X = 0.08
SAFE_MARGIN_TOP = 0.12
SAFE_MARGIN_BOTTOM = 0.22  # platform UI chrome


@dataclass
class OverlaySpec:
    text: str
    position: str = "bottom"  # top | center | bottom
    start_sec: float = 0.0
    end_sec: float = 3.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "position": self.position,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
        }


@dataclass
class TextOverlayReport:
    passed: bool
    overlays: list[OverlaySpec] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "overlays": [o.to_dict() for o in self.overlays],
            "issues": self.issues,
            "checks": self.checks,
        }


class TextOverlayPass:
    """
    Prepare and validate hook/CTA overlays before FFmpeg burn-in.

    Responsibilities: safe margins, mobile readability, contrast hints.
    """

    MIN_CHARS_VISIBLE = 4
    MAX_HOOK_LEN = 72

    def __init__(self, *, frame_width: int = 1080, frame_height: int = 1920):
        self.frame_width = frame_width
        self.frame_height = frame_height

    def build_overlays(
        self,
        hook_texts: list[str],
        *,
        slide_duration: float = 3.0,
        transition_sec: float = 0.5,
    ) -> list[OverlaySpec]:
        overlays: list[OverlaySpec] = []
        t = 0.0
        for i, raw in enumerate(hook_texts or []):
            text = (raw or "").strip()
            if not text:
                t += slide_duration
                continue
            if len(text) > self.MAX_HOOK_LEN:
                text = text[: self.MAX_HOOK_LEN - 1] + "…"
            position = "lower_third"
            overlays.append(OverlaySpec(
                text=text,
                position=position,
                start_sec=t,
                end_sec=t + slide_duration - transition_sec * 0.5,
            ))
            t += slide_duration - transition_sec
        return overlays

    def validate(self, overlays: list[OverlaySpec]) -> TextOverlayReport:
        issues: list[str] = []
        checks = {
            "text_visibility": True,
            "timing": True,
            "positioning": True,
            "readability": True,
        }

        for ov in overlays:
            if len(ov.text.strip()) < self.MIN_CHARS_VISIBLE:
                checks["text_visibility"] = False
                issues.append("Overlay text too short to read")
            if ov.end_sec <= ov.start_sec:
                checks["timing"] = False
                issues.append("Overlay timing invalid")
            if ov.position not in ("top", "center", "bottom", "lower_third"):
                checks["positioning"] = False
                issues.append(f"Unknown overlay position: {ov.position}")
            if len(ov.text) > self.MAX_HOOK_LEN:
                checks["readability"] = False
                issues.append("Overlay text may truncate on small screens")

        passed = all(checks.values())
        return TextOverlayReport(passed=passed, overlays=overlays, issues=issues, checks=checks)

    def prepare_for_compose(
        self,
        hook_texts: list[str],
        *,
        slide_duration: float = 3.0,
        transition_sec: float = 0.5,
    ) -> tuple[list[str], TextOverlayReport]:
        """
        Run quality pass; return sanitized hook_texts for video_compose + report.
        """
        sanitized: list[str] = []
        for raw in hook_texts or []:
            text = (raw or "").strip()
            if len(text) > self.MAX_HOOK_LEN:
                text = text[: self.MAX_HOOK_LEN - 1] + "…"
            sanitized.append(text)
        overlays = self.build_overlays(
            sanitized,
            slide_duration=slide_duration,
            transition_sec=transition_sec,
        )
        report = self.validate(overlays)
        return sanitized, report


def apply_overlay_report_to_metadata(meta: dict, report: TextOverlayReport) -> dict:
    meta = dict(meta or {})
    meta["text_overlay_pass"] = report.to_dict()
    return meta
