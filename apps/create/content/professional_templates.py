"""Professional-business content template packs — thin wrappers over Template Families."""

from __future__ import annotations

import hashlib

from apps.create.content.template_families import (
    LEGACY_PROFESSIONAL_TO_FAMILY,
    TEMPLATE_FAMILIES,
    apply_family_to_blueprint,
    family_to_legacy_professional,
    family_prompt_section,
    resolve_template_family,
)

VALID_PROFESSIONAL_TEMPLATES = frozenset({
    "portfolio",
    "case_study",
    "thought_leadership",
    "consultation_cta",
})

PROFESSIONAL_TEMPLATES: dict[str, dict] = {
    "portfolio": TEMPLATE_FAMILIES["product_spotlight"].as_professional_dict(),
    "case_study": TEMPLATE_FAMILIES["case_study"].as_professional_dict(),
    "thought_leadership": TEMPLATE_FAMILIES["thought_leadership"].as_professional_dict(),
    "consultation_cta": TEMPLATE_FAMILIES["booking_cta"].as_professional_dict(),
}


def pick_professional_template(asset, *, seed: str = "") -> str:
    meta = getattr(asset, "metadata", None) or {}
    forced = meta.get("professional_template", "")
    if forced in VALID_PROFESSIONAL_TEMPLATES:
        return forced
    if meta.get("template_family"):
        return family_to_legacy_professional(meta["template_family"])

    type_map = {
        "portfolio": "portfolio",
        "case_study": "case_study",
        "testimonial": "case_study",
    }
    asset_type = getattr(asset, "asset_type", "")
    if asset_type in type_map:
        return type_map[asset_type]

    key = f"{getattr(asset, 'id', '')}:{seed}"
    digest = hashlib.md5(key.encode()).hexdigest()
    options = sorted(VALID_PROFESSIONAL_TEMPLATES)
    legacy = options[int(digest[:8], 16) % len(options)]
    family = resolve_template_family(
        business_model="professional",
        asset_type=str(asset_type),
        forced_professional=legacy,
    )
    return family_to_legacy_professional(family)


def template_context(asset, user) -> dict:
    profile = getattr(user, "profile", None)
    meta = getattr(asset, "metadata", None) or {}
    industry = profile.get_industry_display() if profile and profile.industry else "our industry"
    return {
        "client": meta.get("client", "a leading client"),
        "outcome": meta.get("outcome", "measurable growth"),
        "pain": meta.get("pain", "a complex challenge"),
        "industry": industry,
        "audience": meta.get("audience", "business owners"),
        "topic": meta.get("topic", asset.title if asset else "strategy"),
        "years": meta.get("years", "10+"),
        "slots": meta.get("slots", "3"),
        "business": (profile.company_name if profile else "") or "our firm",
        "service": getattr(asset, "title", None) or "our services",
        "price": "our consultation rate",
        "quote": "Best decision we made this year.",
    }


def apply_professional_template_to_blueprint(blueprint: dict, template_key: str, asset, user) -> dict:
    if template_key not in VALID_PROFESSIONAL_TEMPLATES:
        return blueprint
    family = LEGACY_PROFESSIONAL_TO_FAMILY.get(template_key, "thought_leadership")
    data = apply_family_to_blueprint(
        blueprint,
        family,
        context=template_context(asset, user),
    )
    tpl = PROFESSIONAL_TEMPLATES[template_key]
    if tpl.get("platforms"):
        from apps.create.content.blueprints import PLATFORM_SLOT_DEFAULTS, PlatformBlueprint

        existing = {p.get("platform") for p in data.get("platforms") or []}
        platforms = list(data.get("platforms") or [])
        for plat in tpl["platforms"]:
            if plat not in existing:
                slots = {k: "" for k in PLATFORM_SLOT_DEFAULTS.get(plat, ["body"])}
                platforms.append(PlatformBlueprint(platform=plat, slots=slots).to_dict())
        data["platforms"] = platforms
    return data


def professional_template_prompt_lines(blueprint: dict) -> str:
    section = family_prompt_section(blueprint)
    if section:
        return section
    meta = blueprint.get("metadata") or {}
    key = meta.get("professional_template")
    if key not in VALID_PROFESSIONAL_TEMPLATES:
        return ""
    lines = [
        f"### PROFESSIONAL TEMPLATE: {meta.get('template_label', key)}",
        f"- Tone: authoritative, credible, client-outcome focused",
        f"- Content intent: {meta.get('content_intent', 'authority')}",
    ]
    hooks = meta.get("suggested_hooks") or []
    if hooks:
        lines.append(f"- Suggested hook: {hooks[0]}")
    if meta.get("suggested_cta"):
        lines.append(f"- CTA: {meta['suggested_cta']}")
    return "\n".join(lines)
