"""
Reel Strategy — strategy-first reel production (never asset-first).

Generated during Campaign preparation; FFmpeg / Photoroom consume this.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ReelSceneSpec:
    type: str
    text: str = ""
    duration_sec: float = 3.5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReelStrategy:
    hook: str = ""
    objective: str = "sales"
    duration_sec: int = 15
    scenes: list[ReelSceneSpec] = field(default_factory=list)
    music_mood: str = "upbeat"
    cta_label: str = "Shop now"

    def to_dict(self) -> dict[str, Any]:
        return {
            "hook": self.hook,
            "objective": self.objective,
            "duration_sec": self.duration_sec,
            "scenes": [s.to_dict() for s in self.scenes],
            "music_mood": self.music_mood,
            "cta_label": self.cta_label,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> ReelStrategy | None:
        if not data or not isinstance(data, dict):
            return None
        scenes = [
            ReelSceneSpec(**s) if isinstance(s, dict) else ReelSceneSpec(type="hero")
            for s in (data.get("scenes") or [])
        ]
        return cls(
            hook=data.get("hook", ""),
            objective=data.get("objective", "sales"),
            duration_sec=int(data.get("duration_sec") or 15),
            scenes=scenes,
            music_mood=data.get("music_mood", "upbeat"),
            cta_label=data.get("cta_label", "Shop now"),
        )

    def hook_texts_for_compose(self) -> list[str]:
        """Overlay text per scene for FFmpeg burn-in."""
        texts = [self.hook] if self.hook else []
        for scene in self.scenes:
            if scene.text and scene.text not in texts:
                texts.append(scene.text)
        return texts

    def slide_roles(self) -> list[str]:
        return [s.type for s in self.scenes]


def build_reel_strategy(seed, campaign=None) -> ReelStrategy:
    """Build reel strategy from campaign objective and context."""
    from apps.content.campaign_bundle import _campaign_context

    ctx = _campaign_context(seed)
    hook = ctx["hook"][:120]
    objective = (
        getattr(campaign, "objective", None)
        or (getattr(seed, "blueprint", None) or {}).get("objective")
        or "sales"
    )
    objective = str(objective).lower()

    if objective in ("sales", "offer", "leads"):
        scenes = [
            ReelSceneSpec(type="problem", text="The struggle is real"),
            ReelSceneSpec(type="feature", text=ctx["name"]),
            ReelSceneSpec(type="benefit", text="Why customers love it"),
            ReelSceneSpec(type="cta", text="Link in bio"),
        ]
        mood = "urgent" if objective == "sales" else "upbeat"
    elif objective in ("awareness", "announce"):
        scenes = [
            ReelSceneSpec(type="hook", text=hook),
            ReelSceneSpec(type="reveal", text=f"Meet {ctx['name']}"),
            ReelSceneSpec(type="benefit", text="See why it matters"),
            ReelSceneSpec(type="cta", text="Follow for more"),
        ]
        mood = "upbeat"
    else:
        scenes = [
            ReelSceneSpec(type="insight", text="Quick tip"),
            ReelSceneSpec(type="example", text=ctx["title"][:80]),
            ReelSceneSpec(type="cta", text="Save this"),
        ]
        mood = "upbeat"

    duration = int(sum(s.duration_sec for s in scenes))
    return ReelStrategy(
        hook=hook,
        objective=objective,
        duration_sec=max(12, min(30, duration)),
        scenes=scenes,
        music_mood=mood,
        cta_label="Order on WhatsApp" if ctx.get("price") else "Shop now",
    )


def reel_strategy_to_compose_metadata(strategy: ReelStrategy) -> dict[str, Any]:
    """Fields merged into Post.visual_metadata before compose."""
    return {
        "reel_strategy": strategy.to_dict(),
        "reel_hook_text": strategy.hook,
        "reel_cta_label": strategy.cta_label,
        "music_mood": strategy.music_mood,
        "reel_slide_roles": strategy.slide_roles(),
    }
