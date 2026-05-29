"""
Photoroom Phase D — per-seller brand template (locked shadow, padding, AI seed, outline).

See docs/Photoroom upgrade.md § Phase D.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from apps.products.photoroom_plus import AI_BG_SEEDS, PlusVariantSpec

INDUSTRY_SHADOW: dict[str, str] = {
    "saas": "ai.floating",
    "ecommerce": "ai.soft",
    "agency": "ai.soft",
    "creator": "ai.soft",
    "consulting": "ai.soft",
    "nonprofit": "ai.soft",
    "education": "ai.soft",
    "health": "ai.soft",
    "food_restaurant": "ai.soft",
    "fashion_beauty": "ai.soft",
    "salon_beauty": "ai.soft",
    "wholesale_retail": "ai.soft",
    "travel_tourism": "ai.soft",
    "agriculture": "ai.soft",
    "logistics_transport": "ai.soft",
    "construction": "ai.soft",
    "media_entertainment": "ai.floating",
    "finance": "ai.hard",
    "legal": "ai.hard",
    "real_estate": "ai.hard",
}

INDUSTRY_PADDING: dict[str, float] = {
    "saas": 0.06,
    "ecommerce": 0.07,
    "fashion_beauty": 0.08,
    "salon_beauty": 0.08,
    "wholesale_retail": 0.07,
    "finance": 0.08,
    "legal": 0.08,
    "real_estate": 0.07,
}

VISUAL_STYLE_SUFFIX: dict[str, str] = {
    "photography": "natural authentic photography with consistent brand lighting",
    "illustration": "clean illustrated brand aesthetic",
    "flat_design": "minimal flat design, generous whitespace",
    "3d_render": "premium 3D product presentation",
    "collage": "editorial collage brand style",
    "abstract": "abstract artistic brand mood",
    "corporate": "professional corporate trustworthy brand",
    "vibrant": "vibrant colorful energetic brand palette",
    "dark_moody": "dark moody premium cinematic brand lighting",
    "auto": "cohesive premium social commerce brand style",
}


@dataclass(frozen=True)
class PhotoroomBrandTemplate:
    """Locked Plus styling applied to every scene for one seller."""

    enabled: bool
    shadow_mode: str
    padding: str
    ai_background_seed: int
    outline_color_hex: str
    studio_color_hex: str
    style_suffix: str
    source: str = "auto"  # auto | profile_override

    def as_log_dict(self) -> dict:
        return {
            "shadow_mode": self.shadow_mode,
            "padding": self.padding,
            "ai_seed": self.ai_background_seed,
            "outline_color": self.outline_color_hex,
            "studio_color": self.studio_color_hex,
            "source": self.source,
        }


def _hex_no_hash(value: str, fallback: str = "FFFFFF") -> str:
    raw = (value or fallback).strip().lstrip("#").upper()
    return raw[:6] if len(raw) >= 6 else fallback


def stable_ai_seed(user_id) -> int:
    idx = abs(hash(str(user_id))) % len(AI_BG_SEEDS)
    return AI_BG_SEEDS[idx]


def _style_suffix_for_profile(profile) -> str:
    if not profile:
        return VISUAL_STYLE_SUFFIX["auto"]
    visual = getattr(profile, "visual_style", None) or "auto"
    base = VISUAL_STYLE_SUFFIX.get(visual, VISUAL_STYLE_SUFFIX["auto"])
    voice = (getattr(profile, "brand_voice", None) or "").strip()
    if voice and len(voice) <= 120:
        return f"{base}. Brand tone: {voice[:120]}."
    if voice:
        return f"{base}. Brand tone: {voice[:120]}…"
    company = (getattr(profile, "company_name", None) or "").strip()
    if company:
        return f"{base}. Brand: {company}."
    return base


def build_photoroom_brand_template(profile, user_id) -> PhotoroomBrandTemplate:
    """Derive locked Plus template from profile + optional JSON overrides."""
    if not getattr(settings, "PHOTOROOM_BRAND_TEMPLATE_ENABLED", True):
        return PhotoroomBrandTemplate(
            enabled=False,
            shadow_mode=getattr(settings, "PHOTOROOM_DEFAULT_SHADOW", "ai.soft"),
            padding=str(getattr(settings, "PHOTOROOM_PADDING", 0.12)),
            ai_background_seed=stable_ai_seed(user_id),
            outline_color_hex="000000",
            studio_color_hex="FFFFFF",
            style_suffix="",
            source="disabled",
        )

    overrides: dict = {}
    if profile is not None:
        overrides = getattr(profile, "photoroom_brand_template", None) or {}
        if not isinstance(overrides, dict):
            overrides = {}

    if overrides.get("enabled") is False:
        return PhotoroomBrandTemplate(
            enabled=False,
            shadow_mode=getattr(settings, "PHOTOROOM_DEFAULT_SHADOW", "ai.soft"),
            padding=str(getattr(settings, "PHOTOROOM_PADDING", 0.12)),
            ai_background_seed=stable_ai_seed(user_id),
            outline_color_hex="000000",
            studio_color_hex="FFFFFF",
            style_suffix="",
            source="disabled",
        )

    industry = getattr(profile, "industry", None) or "other" if profile else "other"
    default_shadow = getattr(settings, "PHOTOROOM_DEFAULT_SHADOW", "ai.soft")
    shadow_mode = overrides.get("shadow_mode") or INDUSTRY_SHADOW.get(industry, default_shadow)

    pad_default = INDUSTRY_PADDING.get(industry, getattr(settings, "PHOTOROOM_PADDING", 0.12))
    padding = overrides.get("padding", pad_default)
    padding_str = str(padding) if not isinstance(padding, str) else padding

    ai_seed = overrides.get("ai_seed") or stable_ai_seed(user_id)
    ai_seed = int(ai_seed)

    brand_colors = getattr(profile, "brand_colors", None) or [] if profile else []
    studio_color = _hex_no_hash(brand_colors[0] if brand_colors else "FFFFFF")
    outline_color = _hex_no_hash(
        overrides.get("outline_color")
        or (brand_colors[1] if len(brand_colors) > 1 else "000000")
    )

    style_suffix = overrides.get("style_suffix") or _style_suffix_for_profile(profile)
    source = "profile_override" if overrides else "auto"

    return PhotoroomBrandTemplate(
        enabled=True,
        shadow_mode=str(shadow_mode),
        padding=padding_str,
        ai_background_seed=ai_seed,
        outline_color_hex=outline_color,
        studio_color_hex=studio_color,
        style_suffix=str(style_suffix),
        source=source,
    )


def brand_prompt_suffix(template: PhotoroomBrandTemplate | None) -> str:
    if template and template.enabled and template.style_suffix:
        return f" Consistent brand look: {template.style_suffix}"
    return ""


def apply_brand_template(
    resolved: dict[str, str],
    template: PhotoroomBrandTemplate | None,
    spec: PlusVariantSpec,
) -> dict[str, str]:
    """Merge seller-locked shadow, padding, seed, outline into Plus params."""
    if not template or not template.enabled:
        return resolved

    out = dict(resolved)
    if "padding" in out:
        out["padding"] = template.padding
    if "shadow.mode" in out:
        out["shadow.mode"] = template.shadow_mode
    if "background.seed" in out:
        out["background.seed"] = str(template.ai_background_seed)
    if "outline.color" in out:
        out["outline.color"] = template.outline_color_hex
    if spec.id == "studio_brand" and "background.color" in out:
        out["background.color"] = template.studio_color_hex
    if "background.prompt" in out:
        out["background.prompt"] = out["background.prompt"] + brand_prompt_suffix(template)
    for key in (
        "flatLay.prompt",
        "ghostMannequin.prompt",
        "virtualModel.prompt",
        "editWithAI.prompt",
    ):
        if key in out:
            out[key] = out[key] + brand_prompt_suffix(template)
    return out
