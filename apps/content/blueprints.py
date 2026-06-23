"""
Content blueprint schema — asset-centric, platform-specific output spec.

Wave 4 foundation: one asset + objective → structured slots per platform.
Renderers and create_agent can consume validated blueprint dicts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

VALID_OBJECTIVES = frozenset({
    "sell",
    "announce",
    "educate",
    "social_proof",
    "book",
    "brand",
})

VALID_PLATFORMS = frozenset({
    "instagram",
    "facebook",
    "tiktok",
    "linkedin",
    "twitter",
    "whatsapp",
})

PLATFORM_SLOT_DEFAULTS: dict[str, list[str]] = {
    "instagram": ["hook", "caption", "hashtags", "cta"],
    "facebook": ["headline", "body", "cta"],
    "tiktok": ["hook", "on_screen_text", "caption", "cta"],
    "linkedin": ["headline", "body", "cta"],
    "twitter": ["tweet", "thread_hook"],
    "whatsapp": ["message", "cta"],
}


@dataclass
class PlatformBlueprint:
    platform: str
    format: str = "feed"
    slots: dict[str, str] = field(default_factory=dict)
    media_hints: list[str] = field(default_factory=list)
    max_length: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContentBlueprint:
    """Canonical content plan generated from a BusinessAsset."""

    asset_id: str
    asset_type: str
    objective: str
    title: str
    platforms: list[PlatformBlueprint] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "asset_type": self.asset_type,
            "objective": self.objective,
            "title": self.title,
            "platforms": [p.to_dict() for p in self.platforms],
            "metadata": self.metadata,
        }


def default_objective_for_asset_type(asset_type: str) -> str:
    mapping = {
        "product": "sell",
        "service": "book",
        "digital": "sell",
        "portfolio": "brand",
        "case_study": "social_proof",
        "testimonial": "social_proof",
        "offer": "announce",
        "event": "announce",
        "promotion": "sell",
    }
    return mapping.get(asset_type, "sell")


def build_blueprint_from_asset(
    asset,
    *,
    objective: str = "",
    platforms: list[str] | None = None,
) -> ContentBlueprint:
    """Build an empty slot scaffold from a BusinessAsset instance."""
    obj = objective or default_objective_for_asset_type(asset.asset_type)
    target_platforms = platforms or _platforms_for_objective(obj)

    platform_blueprints = []
    for platform in target_platforms:
        if platform not in VALID_PLATFORMS:
            continue
        slots = {key: "" for key in PLATFORM_SLOT_DEFAULTS.get(platform, ["body"])}
        platform_blueprints.append(
            PlatformBlueprint(
                platform=platform,
                format=_default_format(platform, asset.asset_type),
                slots=slots,
            )
        )

    return ContentBlueprint(
        asset_id=str(asset.id),
        asset_type=asset.asset_type,
        objective=obj,
        title=asset.title,
        platforms=platform_blueprints,
        metadata={
            "price": (asset.metadata or {}).get("price", ""),
            "currency": (asset.metadata or {}).get("currency", ""),
            "source": asset.source,
        },
    )


def validate_blueprint(data: dict) -> tuple[bool, list[str]]:
    """Validate a serialized blueprint dict. Returns (ok, errors)."""
    errors: list[str] = []
    if not data.get("asset_id"):
        errors.append("asset_id is required")
    objective = data.get("objective", "")
    if objective and objective not in VALID_OBJECTIVES:
        errors.append(f"invalid objective: {objective}")
    platforms = data.get("platforms") or []
    if not platforms:
        errors.append("at least one platform spec is required")
    for i, spec in enumerate(platforms):
        plat = spec.get("platform", "")
        if plat not in VALID_PLATFORMS:
            errors.append(f"platforms[{i}]: invalid platform {plat!r}")
    return (len(errors) == 0, errors)


def _platforms_for_objective(objective: str) -> list[str]:
    if objective == "book":
        return ["instagram", "facebook", "whatsapp"]
    if objective in ("social_proof", "brand"):
        return ["instagram", "linkedin", "facebook"]
    if objective == "educate":
        return ["linkedin", "instagram", "tiktok"]
    return ["instagram", "facebook", "tiktok"]


def _default_format(platform: str, asset_type: str) -> str:
    if platform == "tiktok":
        return "reel"
    if platform == "instagram" and asset_type in ("product", "promotion", "offer"):
        return "carousel"
    if platform == "whatsapp":
        return "status"
    return "feed"
