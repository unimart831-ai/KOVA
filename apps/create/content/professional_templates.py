"""Professional-business content template packs (Wave 6 foundation)."""

from __future__ import annotations

import hashlib

VALID_PROFESSIONAL_TEMPLATES = frozenset({
    "portfolio",
    "case_study",
    "thought_leadership",
    "consultation_cta",
})

PROFESSIONAL_TEMPLATES: dict[str, dict] = {
    "portfolio": {
        "label": "Portfolio showcase",
        "hook_patterns": [
            "Proud of this project for {client}.",
            "How we delivered {outcome} for {client}.",
        ],
        "cta": "Need similar results? Book a consultation.",
        "content_intent": "authority",
        "platforms": ["linkedin", "instagram", "facebook"],
    },
    "case_study": {
        "label": "Case study / results",
        "hook_patterns": [
            "The challenge: {pain}. The result: {outcome}.",
            "{client} came to us with {pain} — here's what changed.",
        ],
        "cta": "DM me CASE for the full breakdown or book a call.",
        "content_intent": "proof",
        "platforms": ["linkedin", "facebook"],
    },
    "thought_leadership": {
        "label": "Thought leadership",
        "hook_patterns": [
            "3 lessons from {years} years in {industry}.",
            "What most {audience} get wrong about {topic}.",
        ],
        "cta": "Follow for more — or book a strategy call.",
        "content_intent": "authority",
        "platforms": ["linkedin", "twitter"],
    },
    "consultation_cta": {
        "label": "Consultation offer",
        "hook_patterns": [
            "Taking on {slots} new clients this month.",
            "Free 15-min consult for {audience} — limited slots.",
        ],
        "cta": "Comment CONSULT or use the link in bio.",
        "content_intent": "offer",
        "platforms": ["linkedin", "instagram", "facebook"],
    },
}


def pick_professional_template(asset, *, seed: str = "") -> str:
    meta = getattr(asset, "metadata", None) or {}
    forced = meta.get("professional_template", "")
    if forced in VALID_PROFESSIONAL_TEMPLATES:
        return forced

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
    return options[int(digest[:8], 16) % len(options)]


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
    }


def apply_professional_template_to_blueprint(blueprint: dict, template_key: str, asset, user) -> dict:
    if template_key not in VALID_PROFESSIONAL_TEMPLATES:
        return blueprint
    tpl = PROFESSIONAL_TEMPLATES[template_key]
    ctx = template_context(asset, user)
    hooks = [h.format(**ctx) for h in tpl["hook_patterns"]]
    meta = dict(blueprint.get("metadata") or {})
    meta.update({
        "professional_template": template_key,
        "template_label": tpl["label"],
        "suggested_hooks": hooks,
        "suggested_cta": tpl["cta"],
        "content_intent": tpl["content_intent"],
        "preferred_platforms": tpl["platforms"],
    })
    blueprint = dict(blueprint)
    blueprint["metadata"] = meta
    if tpl["platforms"]:
        from apps.create.content.blueprints import PLATFORM_SLOT_DEFAULTS, PlatformBlueprint

        existing = {p.get("platform") for p in blueprint.get("platforms") or []}
        platforms = list(blueprint.get("platforms") or [])
        for plat in tpl["platforms"]:
            if plat not in existing:
                slots = {k: "" for k in PLATFORM_SLOT_DEFAULTS.get(plat, ["body"])}
                platforms.append(PlatformBlueprint(platform=plat, slots=slots).to_dict())
        blueprint["platforms"] = platforms
    return blueprint


def professional_template_prompt_lines(blueprint: dict) -> str:
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
