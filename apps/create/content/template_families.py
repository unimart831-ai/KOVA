"""Canonical Template Families — single source of truth for campaign structure.

V1: 12 narrative families. Formats (image/carousel/story/reel/status) and
platforms are variation axes, not separate families.

Unifies:
  - carousel_strategy.CAROUSEL_TEMPLATES
  - service_templates.SERVICE_TEMPLATES
  - professional_templates.PROFESSIONAL_TEMPLATES
  - authority_packs pack types
  - campaign_bundle CTA profiles (partially)

Legacy short keys (offer, faq, portfolio, …) resolve via LEGACY_TO_FAMILY.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TemplateFamily:
    key: str
    label: str
    content_intent: str
    slide_roles: tuple[str, ...] = ()
    hook_patterns: tuple[str, ...] = ()
    cta_primary: str = ""
    cta_whatsapp: str = ""
    cta_story: str = ""
    angles: tuple[str, ...] = ()
    suggested_formats: tuple[str, ...] = ("image", "carousel")
    preferred_platforms: tuple[str, ...] = ()
    include_shop_link: bool = False
    reel_style: str = "product_showcase"
    # Legacy carousel key used by CAROUSEL_TEMPLATES consumers
    carousel_key: str = "offer"
    # Legacy service / professional short keys (optional)
    service_key: str = ""
    professional_key: str = ""

    def as_carousel_dict(self) -> dict[str, Any]:
        return {
            "type": self.label,
            "objective": self.content_intent,
            "slide_roles": self.slide_roles,
        }

    def as_service_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "hook_patterns": list(self.hook_patterns),
            "cta": self.cta_whatsapp or self.cta_primary,
            "content_intent": self.content_intent,
            "angles": list(self.angles),
        }

    def as_professional_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "hook_patterns": list(self.hook_patterns),
            "cta": self.cta_primary,
            "content_intent": self.content_intent,
            "platforms": list(self.preferred_platforms),
        }


TEMPLATE_FAMILIES: dict[str, TemplateFamily] = {
    "product_spotlight": TemplateFamily(
        key="product_spotlight",
        label="Product Spotlight",
        content_intent="awareness",
        slide_roles=("hook", "reveal", "feature", "benefit", "cta"),
        hook_patterns=(
            "Proud of this project for {client}.",
            "How we delivered {outcome} for {client}.",
            "Meet {service} — built for {audience}.",
        ),
        cta_primary="Shop now",
        cta_whatsapp="Order on WhatsApp",
        cta_story="Shop now — link in bio 👆",
        angles=("showcase", "features", "portfolio"),
        suggested_formats=("image", "carousel", "reel"),
        preferred_platforms=("instagram", "facebook", "whatsapp"),
        include_shop_link=True,
        reel_style="product_showcase",
        carousel_key="product_launch",
        professional_key="portfolio",
    ),
    "launch": TemplateFamily(
        key="launch",
        label="New Product / Service Launch",
        content_intent="awareness",
        slide_roles=("hook", "reveal", "feature", "benefit", "cta"),
        hook_patterns=(
            "Just dropped: {service}.",
            "New for {audience} — {service} is here.",
        ),
        cta_primary="See what's new",
        cta_whatsapp="Ask about the launch on WhatsApp",
        cta_story="New drop — link in bio 👆",
        angles=("launch", "new", "reveal"),
        suggested_formats=("image", "carousel", "reel", "story"),
        include_shop_link=True,
        reel_style="product_showcase",
        carousel_key="product_launch",
    ),
    "offer": TemplateFamily(
        key="offer",
        label="Promotion & Offers",
        content_intent="offer",
        slide_roles=("hook", "problem", "solution", "proof", "offer", "cta"),
        hook_patterns=(
            "This week only — {service} at a special rate.",
            "New client offer: {service} from {price}.",
        ),
        cta_primary="Order now",
        cta_whatsapp="Order on WhatsApp",
        cta_story="Shop the offer — link in bio 👆",
        angles=("urgency", "promotion", "new_clients"),
        suggested_formats=("image", "carousel", "story", "reel"),
        include_shop_link=True,
        reel_style="product_showcase",
        carousel_key="offer",
        service_key="offer",
    ),
    "educational": TemplateFamily(
        key="educational",
        label="Educational / Tips",
        content_intent="authority",
        slide_roles=("hook", "problem", "insight", "example", "cta"),
        hook_patterns=(
            "3 mistakes in {industry}.",
            "What most {audience} get wrong about {topic}.",
        ),
        cta_primary="Save this for later",
        cta_whatsapp="Ask us a question on WhatsApp",
        cta_story="Tip — save this 👆",
        angles=("tips", "education", "howto"),
        suggested_formats=("carousel", "image", "reel"),
        preferred_platforms=("instagram", "facebook", "linkedin"),
        reel_style="authority",
        carousel_key="educational",
    ),
    "faq": TemplateFamily(
        key="faq",
        label="FAQ / Objections",
        content_intent="awareness",
        slide_roles=("hook", "question", "answer", "question", "cta"),
        hook_patterns=(
            "FAQ: How to choose in {industry}.",
            "Before you buy — read this.",
        ),
        cta_primary="Get answers",
        cta_whatsapp="Ask on WhatsApp",
        cta_story="Got questions? Link in bio",
        angles=("faq", "objections", "trust"),
        suggested_formats=("carousel", "story"),
        reel_style="service_showcase",
        carousel_key="faq",
    ),
    "testimonial": TemplateFamily(
        key="testimonial",
        label="Testimonials & Reviews",
        content_intent="social_proof",
        slide_roles=("hook", "quote", "proof", "benefit", "cta"),
        hook_patterns=(
            "Our clients keep coming back — here's why.",
            '"{quote}" — happy customer at {business}.',
        ),
        cta_primary="See why they chose us",
        cta_whatsapp="DM us or tap the link to book",
        cta_story="Real reviews — link in bio",
        angles=("testimonial", "word_of_mouth", "reviews"),
        suggested_formats=("image", "carousel", "story"),
        reel_style="service_showcase",
        carousel_key="testimonial",
        service_key="testimonial",
    ),
    "before_after": TemplateFamily(
        key="before_after",
        label="Before & After / Results",
        content_intent="sales",
        slide_roles=("hook", "before", "after", "proof", "cta"),
        hook_patterns=(
            "See the difference in just one visit.",
            "From {pain} to {outcome} — real results.",
        ),
        cta_primary="Get these results",
        cta_whatsapp="Book your slot on WhatsApp",
        cta_story="Results speak — book via link",
        angles=("before_after", "results", "trust"),
        suggested_formats=("carousel", "image", "reel"),
        reel_style="service_showcase",
        carousel_key="before_after",
        service_key="transformation",
    ),
    "case_study": TemplateFamily(
        key="case_study",
        label="Case Study",
        content_intent="social_proof",
        slide_roles=("hook", "challenge", "solution", "result", "cta"),
        hook_patterns=(
            "The challenge: {pain}. The result: {outcome}.",
            "{client} came to us with {pain} — here's what changed.",
        ),
        cta_primary="Want similar results?",
        cta_whatsapp="DM CASE for the full breakdown",
        cta_story="Case study — link in bio",
        angles=("case_study", "proof", "results"),
        suggested_formats=("carousel", "image"),
        preferred_platforms=("linkedin", "facebook", "instagram"),
        reel_style="authority",
        carousel_key="case_study",
        professional_key="case_study",
    ),
    "thought_leadership": TemplateFamily(
        key="thought_leadership",
        label="Thought Leadership",
        content_intent="authority",
        slide_roles=("hook", "trend", "insight", "action", "cta"),
        hook_patterns=(
            "3 lessons from {years} years in {industry}.",
            "What most {audience} get wrong about {topic}.",
        ),
        cta_primary="Follow for more",
        cta_whatsapp="Book a strategy call on WhatsApp",
        cta_story="Insight — follow for more",
        angles=("authority", "insight", "trend"),
        suggested_formats=("carousel", "image", "reel"),
        preferred_platforms=("linkedin", "instagram", "facebook"),
        reel_style="authority",
        carousel_key="industry_insight",
        professional_key="thought_leadership",
    ),
    "booking_cta": TemplateFamily(
        key="booking_cta",
        label="Booking / Consultation CTA",
        content_intent="offer",
        slide_roles=("hook", "problem", "solution", "offer", "cta"),
        hook_patterns=(
            "Taking on {slots} new clients this month.",
            "Free 15-min consult for {audience} — limited slots.",
        ),
        cta_primary="Book a consultation",
        cta_whatsapp="Book on WhatsApp",
        cta_story="Book now — link in bio 👆",
        angles=("booking", "consult", "slots"),
        suggested_formats=("image", "story", "carousel"),
        preferred_platforms=("instagram", "facebook", "whatsapp"),
        reel_style="service_showcase",
        carousel_key="faq",
        professional_key="consultation_cta",
        service_key="offer",
    ),
    "behind_the_brand": TemplateFamily(
        key="behind_the_brand",
        label="Behind the Brand",
        content_intent="awareness",
        slide_roles=("hook", "story", "value", "proof", "cta"),
        hook_patterns=(
            "Why we started {business}.",
            "The story behind {service}.",
        ),
        cta_primary="Follow our journey",
        cta_whatsapp="Say hi on WhatsApp",
        cta_story="Our story — link in bio",
        angles=("founder", "story", "values"),
        suggested_formats=("image", "reel", "story"),
        reel_style="authority",
        carousel_key="educational",
    ),
    "seasonal": TemplateFamily(
        key="seasonal",
        label="Seasonal & Timely",
        content_intent="awareness",
        slide_roles=("hook", "moment", "offer", "cta"),
        hook_patterns=(
            "This season in {industry} — don't miss it.",
            "Timely tip for {audience}.",
        ),
        cta_primary="Act this week",
        cta_whatsapp="Message us on WhatsApp today",
        cta_story="Limited time — link in bio",
        angles=("seasonal", "timely", "event"),
        suggested_formats=("image", "story", "carousel"),
        include_shop_link=True,
        reel_style="product_showcase",
        carousel_key="offer",
    ),
}

# Objective / intent → family (goal-first Studio)
OBJECTIVE_TO_FAMILY: dict[str, str] = {
    "sales": "offer",
    "leads": "educational",
    "awareness": "launch",
    "bookings": "booking_cta",
    "offer": "offer",
    "authority": "thought_leadership",
    "social_proof": "testimonial",
    "proof": "case_study",
    "solution": "educational",
    "problem_awareness": "educational",
    "educate": "educational",
}

# Business-model defaults when objective is weak/missing
BUSINESS_MODEL_DEFAULT_FAMILY: dict[str, str] = {
    "product": "offer",
    "service": "booking_cta",
    "professional": "thought_leadership",
    "digital": "product_spotlight",
    "multiple": "offer",
}

# Legacy carousel keys → family
LEGACY_CAROUSEL_TO_FAMILY: dict[str, str] = {
    "educational": "educational",
    "faq": "faq",
    "offer": "offer",
    "case_study": "case_study",
    "testimonial": "testimonial",
    "product_launch": "launch",
    "before_after": "before_after",
    "industry_insight": "thought_leadership",
}

# Legacy service keys → family
LEGACY_SERVICE_TO_FAMILY: dict[str, str] = {
    "transformation": "before_after",
    "testimonial": "testimonial",
    "offer": "offer",
}

# Legacy professional keys → family
LEGACY_PROFESSIONAL_TO_FAMILY: dict[str, str] = {
    "portfolio": "product_spotlight",
    "case_study": "case_study",
    "thought_leadership": "thought_leadership",
    "consultation_cta": "booking_cta",
}

# Reverse: family → legacy carousel key (for CAROUSEL_TEMPLATES compat)
FAMILY_TO_LEGACY_CAROUSEL: dict[str, str] = {
    f.key: f.carousel_key for f in TEMPLATE_FAMILIES.values()
}

VALID_FAMILY_KEYS = frozenset(TEMPLATE_FAMILIES.keys())


def get_family(key: str) -> TemplateFamily:
    if key in TEMPLATE_FAMILIES:
        return TEMPLATE_FAMILIES[key]
    legacy = (
        LEGACY_CAROUSEL_TO_FAMILY.get(key)
        or LEGACY_SERVICE_TO_FAMILY.get(key)
        or LEGACY_PROFESSIONAL_TO_FAMILY.get(key)
    )
    if legacy and legacy in TEMPLATE_FAMILIES:
        return TEMPLATE_FAMILIES[legacy]
    return TEMPLATE_FAMILIES["offer"]


def resolve_template_family(
    *,
    objective: str = "",
    intent: str = "",
    target_intent: str = "",
    business_model: str = "",
    asset_type: str = "",
    forced_family: str = "",
    forced_service: str = "",
    forced_professional: str = "",
) -> str:
    """Pick a canonical family key from campaign + business context."""
    if forced_family and forced_family in VALID_FAMILY_KEYS:
        return forced_family
    if forced_service and forced_service in LEGACY_SERVICE_TO_FAMILY:
        return LEGACY_SERVICE_TO_FAMILY[forced_service]
    if forced_professional and forced_professional in LEGACY_PROFESSIONAL_TO_FAMILY:
        return LEGACY_PROFESSIONAL_TO_FAMILY[forced_professional]

    at = (asset_type or "").lower().strip()
    if at == "portfolio":
        return "product_spotlight"
    if at == "case_study":
        return "case_study"
    if at == "testimonial":
        return "testimonial"
    if at == "service":
        # Prefer booking CTA for services unless objective overrides below
        pass

    signals = (target_intent, intent, objective)
    for key in signals:
        if not key:
            continue
        normalized = str(key).lower().replace("-", "_")
        if normalized in VALID_FAMILY_KEYS:
            return normalized
        if normalized in OBJECTIVE_TO_FAMILY:
            return OBJECTIVE_TO_FAMILY[normalized]
        if normalized in LEGACY_CAROUSEL_TO_FAMILY:
            return LEGACY_CAROUSEL_TO_FAMILY[normalized]

    bm = (business_model or "product").lower().strip()
    # Preserve legacy carousel defaults when no objective/intent was provided
    if not any(signals):
        if at == "service" or bm == "service":
            return "faq"
        if bm == "professional":
            return "educational"
    if at == "service" or bm == "service":
        return BUSINESS_MODEL_DEFAULT_FAMILY.get("service", "booking_cta")
    if bm == "professional":
        return BUSINESS_MODEL_DEFAULT_FAMILY.get("professional", "thought_leadership")
    return BUSINESS_MODEL_DEFAULT_FAMILY.get(bm, "offer")


def family_to_legacy_carousel(family_key: str) -> str:
    family = get_family(family_key)
    return family.carousel_key


def family_to_legacy_service(family_key: str) -> str:
    family = get_family(family_key)
    return family.service_key or "offer"


def family_to_legacy_professional(family_key: str) -> str:
    family = get_family(family_key)
    return family.professional_key or "thought_leadership"


def build_legacy_carousel_templates() -> dict[str, dict[str, Any]]:
    """CAROUSEL_TEMPLATES-shaped dict keyed by legacy short names.

    Canonical LEGACY_CAROUSEL_TO_FAMILY wins when multiple families share a
    carousel_key (e.g. offer + seasonal both map to ``offer``).
    """
    out: dict[str, dict[str, Any]] = {}
    for legacy, family_key in LEGACY_CAROUSEL_TO_FAMILY.items():
        out[legacy] = get_family(family_key).as_carousel_dict()
    for fam in TEMPLATE_FAMILIES.values():
        if fam.carousel_key not in out:
            out[fam.carousel_key] = fam.as_carousel_dict()
    return out


def build_legacy_intent_to_template() -> dict[str, str]:
    """INTENT_TO_TEMPLATE-shaped map → legacy carousel keys."""
    out: dict[str, str] = {}
    for intent, family_key in OBJECTIVE_TO_FAMILY.items():
        out[intent] = family_to_legacy_carousel(family_key)
    return out


def bundle_profile_from_family(family_key: str) -> dict[str, Any]:
    """Shape expected by campaign_bundle.get_bundle_profile consumers."""
    fam = get_family(family_key)
    return {
        "carousel_intent": fam.carousel_key if fam.carousel_key in (
            "offer", "faq", "educational",
        ) else ("faq" if fam.key == "booking_cta" else "offer"),
        "cta_primary": fam.cta_primary,
        "cta_whatsapp": fam.cta_whatsapp or fam.cta_primary,
        "cta_story": fam.cta_story,
        "include_shop_link": fam.include_shop_link,
        "reel_style": fam.reel_style,
        "template_family": fam.key,
    }


def _safe_format_hooks(patterns: tuple[str, ...], context: dict) -> list[str]:
    defaults = {
        "client": "a leading client",
        "outcome": "measurable growth",
        "pain": "a complex challenge",
        "industry": "your industry",
        "audience": "customers",
        "topic": "growth",
        "years": "10+",
        "slots": "3",
        "business": "our business",
        "service": "our offer",
        "price": "our best rate",
        "quote": "Best experience we've had!",
    }
    defaults.update({k: v for k, v in (context or {}).items() if v is not None})
    hooks = []
    for h in patterns:
        try:
            hooks.append(h.format(**defaults))
        except Exception:
            hooks.append(h)
    return hooks


def apply_family_to_blueprint(
    blueprint: dict,
    family_key: str,
    *,
    context: dict | None = None,
) -> dict:
    """Write unified family metadata onto a blueprint dict."""
    fam = get_family(family_key)
    hooks = _safe_format_hooks(fam.hook_patterns, context or {})

    meta = dict(blueprint.get("metadata") or {})
    meta.update({
        "template_family": fam.key,
        "template_label": fam.label,
        "suggested_hooks": hooks,
        "suggested_cta": fam.cta_whatsapp or fam.cta_primary,
        "content_intent": fam.content_intent,
        "angles": list(fam.angles),
        "preferred_platforms": list(fam.preferred_platforms),
        "suggested_formats": list(fam.suggested_formats),
    })
    # Keep legacy keys for old prompt readers
    if fam.service_key:
        meta["service_template"] = fam.service_key
    if fam.professional_key:
        meta["professional_template"] = fam.professional_key

    out = dict(blueprint)
    out["metadata"] = meta
    out["template_family"] = fam.key
    return out


def family_prompt_section(blueprint: dict) -> str:
    """Create Agent prompt block for the resolved family."""
    meta = blueprint.get("metadata") or {}
    key = blueprint.get("template_family") or meta.get("template_family")
    if not key or key not in VALID_FAMILY_KEYS:
        return ""
    fam = get_family(key)
    lines = [
        f"### TEMPLATE FAMILY: {fam.label} ({fam.key})",
        f"- Content intent: {fam.content_intent}",
        f"- Preferred formats: {', '.join(fam.suggested_formats)}",
    ]
    hooks = meta.get("suggested_hooks") or []
    if hooks:
        lines.append(f"- Suggested hook: {hooks[0]}")
    if meta.get("suggested_cta"):
        lines.append(f"- CTA to weave in: {meta['suggested_cta']}")
    if fam.slide_roles:
        lines.append(f"- Carousel slide roles: {' → '.join(fam.slide_roles)}")
    return "\n".join(lines)


def resolve_family_for_seed(seed, *, campaign=None, asset=None) -> str:
    """Resolve + optionally read forced family from seed/campaign."""
    blueprint = getattr(seed, "blueprint", None) or {}
    meta = blueprint.get("metadata") or {}
    forced = (
        getattr(seed, "template_family", None)
        or getattr(campaign, "template_family", None)
        or blueprint.get("template_family")
        or meta.get("template_family")
        or ""
    )
    profile = getattr(getattr(seed, "user", None), "profile", None)
    bm = getattr(profile, "business_model", "") or ""
    objective = (
        getattr(campaign, "objective", None)
        or blueprint.get("objective")
        or ""
    )
    asset_type = ""
    if asset is not None:
        asset_type = getattr(asset, "asset_type", "") or ""
    proposal = blueprint.get("proposal") or {}
    return resolve_template_family(
        objective=str(objective),
        intent=str(proposal.get("intent", "")),
        target_intent=getattr(seed, "target_intent", "") or "",
        business_model=bm,
        asset_type=str(asset_type),
        forced_family=str(forced),
        forced_service=str(meta.get("service_template", "")),
        forced_professional=str(meta.get("professional_template", "")),
    )
