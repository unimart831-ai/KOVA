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

    def hook_texts_for_compose(self, slide_roles: list[str] | None = None) -> list[str]:
        """
        Overlay text aligned to slide roles — text only on hook/cta beats.

        When slide_roles is provided, returns a same-length list with copy
        only on hook and cta indices (product hero slides stay clean).
        """
        roles = list(slide_roles or self.slide_roles() or [])
        if not roles:
            texts = [self.hook] if self.hook else []
            for scene in self.scenes:
                if scene.text and scene.text not in texts:
                    texts.append(scene.text)
            return texts

        out = [""] * len(roles)
        # Prefer strategy hook on first hook-like role
        hook_text = (self.hook or "").strip()
        cta_text = (self.cta_label or "").strip()

        for idx, role in enumerate(roles):
            role_l = (role or "").lower()
            if role_l in ("hook", "problem", "insight", "reveal") and not out[idx]:
                # Prefer scene text for this role, else campaign hook
                scene_text = ""
                if idx < len(self.scenes) and self.scenes[idx].text:
                    scene_text = self.scenes[idx].text.strip()
                out[idx] = scene_text or hook_text
            elif role_l in ("cta", "offer") and not out[idx]:
                scene_text = ""
                if idx < len(self.scenes) and self.scenes[idx].text:
                    scene_text = self.scenes[idx].text.strip()
                out[idx] = scene_text or cta_text
            # feature/benefit/hero/staging → leave blank (product-first)
        return out

    def slide_roles(self) -> list[str]:
        return [s.type for s in self.scenes]


def build_reel_strategy(seed, campaign=None) -> ReelStrategy:
    """Build reel strategy from campaign objective and context."""
    from apps.create.content.campaign_bundle import _campaign_context, get_bundle_profile, _resolve_business_model

    ctx = _campaign_context(seed)
    bundle = get_bundle_profile(seed)
    bm = _resolve_business_model(seed)
    hook = ctx["hook"][:120]
    objective = (
        getattr(campaign, "objective", None)
        or (getattr(seed, "blueprint", None) or {}).get("objective")
        or "sales"
    )
    objective = str(objective).lower()

    if bm == "service":
        scenes = [
            ReelSceneSpec(type="hook", text=f"Need {ctx['name']}?"),
            ReelSceneSpec(type="feature", text="How it works"),
            ReelSceneSpec(type="benefit", text="Why clients book again"),
            ReelSceneSpec(type="cta", text="Book now"),
        ]
        mood = "calm"
        cta_label = bundle["cta_whatsapp"] if ctx.get("price") else bundle["cta_primary"]
    elif bm == "professional":
        scenes = [
            ReelSceneSpec(type="insight", text=hook[:80] or "Expert insight"),
            ReelSceneSpec(type="example", text=ctx["title"][:80]),
            ReelSceneSpec(type="benefit", text="Results we've delivered"),
            ReelSceneSpec(type="cta", text="Book a consultation"),
        ]
        mood = "authoritative"
        cta_label = bundle["cta_primary"]
    elif objective in ("sales", "offer", "leads"):
        scenes = [
            ReelSceneSpec(type="problem", text="The struggle is real"),
            ReelSceneSpec(type="feature", text=ctx["name"]),
            ReelSceneSpec(type="benefit", text="Why customers love it"),
            ReelSceneSpec(type="cta", text="Link in bio"),
        ]
        mood = "urgent" if objective == "sales" else "upbeat"
        cta_label = bundle["cta_whatsapp"] if ctx.get("price") else bundle["cta_primary"]
    elif objective in ("awareness", "announce"):
        scenes = [
            ReelSceneSpec(type="hook", text=hook),
            ReelSceneSpec(type="reveal", text=f"Meet {ctx['name']}"),
            ReelSceneSpec(type="benefit", text="See why it matters"),
            ReelSceneSpec(type="cta", text="Follow for more"),
        ]
        mood = "upbeat"
        cta_label = "Follow for more"
    else:
        scenes = [
            ReelSceneSpec(type="insight", text="Quick tip"),
            ReelSceneSpec(type="example", text=ctx["title"][:80]),
            ReelSceneSpec(type="cta", text="Save this"),
        ]
        mood = "upbeat"
        cta_label = bundle.get("cta_primary", "Shop now")

    duration = int(sum(s.duration_sec for s in scenes))
    return ReelStrategy(
        hook=hook,
        objective=objective,
        duration_sec=max(12, min(30, duration)),
        scenes=scenes,
        music_mood=mood,
        cta_label=cta_label,
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
