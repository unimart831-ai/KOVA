"""
Pydantic schemas for validating LLM output before it touches the DB.

The Create Agent (and other LLM-driven agents) receives JSON from models that
occasionally return wrong types, prose instead of numbers, or refuse a field
outright. Passing those values straight into Django fields crashes the task
mid-insert — the user sees zero posts generated and no error surfaces.

PostDraft coerces the fragile fields, logs refusals, and returns a clean
dict ready for Post.objects.create(**draft.to_post_kwargs()).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator

logger = logging.getLogger(__name__)


class PostDraft(BaseModel):
    """One post's worth of LLM-generated fields, validated."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    platform: str = ""
    content_text: str = ""
    content_type: str = "original"
    predicted_score: Optional[float] = None
    reasoning: str = ""
    angle: str = ""
    framework_used: str = ""
    image_prompt: str = ""
    visual_strategy: dict = {}

    @field_validator("predicted_score", mode="before")
    @classmethod
    def _coerce_score(cls, v: Any) -> Optional[float]:
        """
        Accept int/float as-is, numeric strings ("72", "72.5", "72%"), and
        clamp to [0, 100]. Reject prose / dict / list / anything else by
        returning None + a WARNING log so refusals are visible in prod.
        """
        if v is None or v == "":
            return None
        if isinstance(v, bool):
            # bool is a subclass of int — explicit reject, it's never a score
            return None
        if isinstance(v, (int, float)):
            return max(0.0, min(100.0, float(v)))
        if isinstance(v, str):
            cleaned = v.strip().rstrip("%").strip()
            try:
                return max(0.0, min(100.0, float(cleaned)))
            except ValueError:
                logger.warning(
                    "PostDraft: predicted_score rejected (not numeric). "
                    "First 120 chars: %r",
                    v[:120],
                )
                return None
        logger.warning(
            "PostDraft: predicted_score rejected (unexpected type %s)",
            type(v).__name__,
        )
        return None

    @field_validator("visual_strategy", mode="before")
    @classmethod
    def _coerce_visual_strategy(cls, v: Any) -> dict:
        return v if isinstance(v, dict) else {}

    @field_validator(
        "content_text", "content_type", "reasoning", "angle",
        "framework_used", "image_prompt", "platform",
        mode="before",
    )
    @classmethod
    def _coerce_str(cls, v: Any) -> str:
        if v is None:
            return ""
        return v if isinstance(v, str) else str(v)

    @classmethod
    def from_llm_dict(cls, data: Any) -> "PostDraft":
        """Parse one LLM post-dict; never raises — always returns a PostDraft."""
        if not isinstance(data, dict):
            logger.warning(
                "PostDraft: expected dict, got %s — treating as empty",
                type(data).__name__,
            )
            return cls()
        try:
            return cls.model_validate(data)
        except Exception as exc:
            logger.warning("PostDraft validation failed: %s", exc)
            return cls()

    def to_post_kwargs(self) -> dict:
        """Subset of fields ready to pass to Post.objects.create(...)."""
        return {
            "content_text": self.content_text,
            "predicted_engagement_score": self.predicted_score,
            "ai_reasoning": self.reasoning,
            "ai_angle": self.angle,
            "ai_framework": self.framework_used,
        }
