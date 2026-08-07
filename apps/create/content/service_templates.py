"""Service-business content template packs (Wave 5 foundation)."""

from __future__ import annotations

import hashlib

VALID_SERVICE_TEMPLATES = frozenset({
    "transformation",
    "testimonial",
    "offer",
})

SERVICE_TEMPLATES: dict[str, dict] = {
    "transformation": {
        "label": "Before / After transformation",
        "hook_patterns": [
            "See the difference in just one visit.",
            "From {pain} to {outcome} — real results.",
        ],
        "cta": "Book your slot on WhatsApp — limited appointments this week.",
        "content_intent": "proof",
        "angles": ["before_after", "results", "trust"],
    },
    "testimonial": {
        "label": "Client testimonial / social proof",
        "hook_patterns": [
            "Our clients keep coming back — here's why.",
            "\"{quote}\" — happy customer at {business}.",
        ],
        "cta": "DM us or tap the link to book your appointment.",
        "content_intent": "proof",
        "angles": ["testimonial", "word_of_mouth", "reviews"],
    },
    "offer": {
        "label": "Limited-time service offer",
        "hook_patterns": [
            "This week only — {service} at a special rate.",
            "New client offer: {service} from {price}.",
        ],
        "cta": "Reply BOOK or use the link — slots fill fast.",
        "content_intent": "offer",
        "angles": ["urgency", "promotion", "new_clients"],
    },
}


def pick_service_template(asset, *, seed: str = "") -> str:
    """Deterministic template rotation per asset."""
    if not asset:
        return "offer"
    meta = getattr(asset, "metadata", None) or {}
    forced = meta.get("service_template", "")
    if forced in VALID_SERVICE_TEMPLATES:
        return forced
    key = f"{getattr(asset, 'id', '')}:{seed}"
    digest = hashlib.md5(key.encode()).hexdigest()
    options = sorted(VALID_SERVICE_TEMPLATES)
    return options[int(digest[:8], 16) % len(options)]


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
    }


def apply_service_template_to_blueprint(blueprint: dict, template_key: str, asset, user) -> dict:
    """Enrich blueprint metadata with service template guidance."""
    if template_key not in VALID_SERVICE_TEMPLATES:
        return blueprint
    tpl = SERVICE_TEMPLATES[template_key]
    ctx = template_context(asset, user)
    hooks = [h.format(**ctx) for h in tpl["hook_patterns"]]
    meta = dict(blueprint.get("metadata") or {})
    meta.update({
        "service_template": template_key,
        "template_label": tpl["label"],
        "suggested_hooks": hooks,
        "suggested_cta": tpl["cta"],
        "content_intent": tpl["content_intent"],
        "angles": tpl["angles"],
    })
    blueprint = dict(blueprint)
    blueprint["metadata"] = meta
    return blueprint


def service_template_prompt_lines(blueprint: dict) -> str:
    """Extra prompt lines derived from service template metadata."""
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
