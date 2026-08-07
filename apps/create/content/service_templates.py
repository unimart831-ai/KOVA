"""Service-business content template packs — thin wrappers over Template Families."""

from __future__ import annotations

import hashlib

from apps.create.content.template_families import (
    LEGACY_SERVICE_TO_FAMILY,
    TEMPLATE_FAMILIES,
    apply_family_to_blueprint,
    family_to_legacy_service,
    family_prompt_section,
    resolve_template_family,
)

VALID_SERVICE_TEMPLATES = frozenset({"transformation", "testimonial", "offer"})

SERVICE_TEMPLATES: dict[str, dict] = {
    "transformation": TEMPLATE_FAMILIES["before_after"].as_service_dict(),
    "testimonial": TEMPLATE_FAMILIES["testimonial"].as_service_dict(),
    "offer": TEMPLATE_FAMILIES["offer"].as_service_dict(),
}


def pick_service_template(asset, *, seed: str = "") -> str:
    """Deterministic template rotation per asset → legacy service key."""
    if not asset:
        return "offer"
    meta = getattr(asset, "metadata", None) or {}
    forced = meta.get("service_template", "")
    if forced in VALID_SERVICE_TEMPLATES:
        return forced
    if meta.get("template_family"):
        return family_to_legacy_service(meta["template_family"])

    key = f"{getattr(asset, 'id', '')}:{seed}"
    digest = hashlib.md5(key.encode()).hexdigest()
    options = sorted(VALID_SERVICE_TEMPLATES)
    legacy = options[int(digest[:8], 16) % len(options)]
    # Prefer family resolver when objective-like signals exist
    family = resolve_template_family(
        business_model="service",
        asset_type=getattr(asset, "asset_type", "") or "service",
        forced_service=legacy,
    )
    return family_to_legacy_service(family)


def template_context(asset, user) -> dict:
    """Fill template placeholders from asset + profile."""
    profile = getattr(user, "profile", None)
    meta = getattr(asset, "metadata", None) or {}
    price = meta.get("price") or meta.get("price_kes") or ""
    currency = meta.get("currency") or "KES"
    price_label = f"{currency} {price}" if price else "our best rate"
    return {
        "service": getattr(asset, "title", "our service"),
        "business": (profile.company_name if profile else "") or "us",
        "price": price_label,
        "pain": "stressed, overdue for self-care",
        "outcome": "refreshed and confident",
        "quote": "Best service I've had in Nairobi!",
        "industry": (profile.get_industry_display() if profile and profile.industry else "your industry"),
        "audience": "customers",
        "topic": getattr(asset, "title", "our service"),
        "client": "our clients",
        "years": "5+",
        "slots": "5",
    }


def apply_service_template_to_blueprint(blueprint: dict, template_key: str, asset, user) -> dict:
    """Enrich blueprint metadata with service template guidance."""
    if template_key not in VALID_SERVICE_TEMPLATES:
        return blueprint
    family = LEGACY_SERVICE_TO_FAMILY.get(template_key, "offer")
    return apply_family_to_blueprint(
        blueprint,
        family,
        context=template_context(asset, user),
    )


def service_template_prompt_lines(blueprint: dict) -> str:
    """Extra prompt lines derived from service / family metadata."""
    section = family_prompt_section(blueprint)
    if section:
        return section
    meta = blueprint.get("metadata") or {}
    key = meta.get("service_template")
    if key not in VALID_SERVICE_TEMPLATES:
        return ""
    lines = [
        f"### SERVICE TEMPLATE: {meta.get('template_label', key)}",
        f"- Content intent: {meta.get('content_intent', 'offer')}",
    ]
    hooks = meta.get("suggested_hooks") or []
    if hooks:
        lines.append(f"- Suggested hook: {hooks[0]}")
    if meta.get("suggested_cta"):
        lines.append(f"- CTA to weave in: {meta['suggested_cta']}")
    return "\n".join(lines)
