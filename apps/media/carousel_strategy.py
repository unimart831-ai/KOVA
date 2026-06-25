"""
Carousel Strategy — campaign-driven carousel JSON (single source for rendering).

Create Agent / media factory produces this; renderers consume it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# Business-type carousel templates (auto-selected from campaign intent)
CAROUSEL_TEMPLATES: dict[str, dict[str, Any]] = {
    "educational": {
        "type": "Educational",
        "objective": "authority",
        "slide_roles": ("hook", "problem", "insight", "example", "cta"),
    },
    "faq": {
        "type": "FAQ",
        "objective": "awareness",
        "slide_roles": ("hook", "question", "answer", "question", "cta"),
    },
    "offer": {
        "type": "Offer",
        "objective": "sales",
        "slide_roles": ("hook", "problem", "solution", "proof", "offer", "cta"),
    },
    "case_study": {
        "type": "Case Study",
        "objective": "social_proof",
        "slide_roles": ("hook", "challenge", "solution", "result", "cta"),
    },
    "testimonial": {
        "type": "Testimonial",
        "objective": "social_proof",
        "slide_roles": ("hook", "quote", "proof", "benefit", "cta"),
    },
    "product_launch": {
        "type": "Product Launch",
        "objective": "awareness",
        "slide_roles": ("hook", "reveal", "feature", "benefit", "cta"),
    },
    "before_after": {
        "type": "Before/After",
        "objective": "sales",
        "slide_roles": ("hook", "before", "after", "proof", "cta"),
    },
    "industry_insight": {
        "type": "Industry Insight",
        "objective": "authority",
        "slide_roles": ("hook", "trend", "insight", "action", "cta"),
    },
}

INTENT_TO_TEMPLATE = {
    "sales": "offer",
    "offer": "offer",
    "leads": "educational",
    "awareness": "product_launch",
    "bookings": "faq",
    "authority": "industry_insight",
    "social_proof": "testimonial",
    "proof": "case_study",
    "solution": "educational",
    "problem_awareness": "educational",
    "educate": "educational",
}


@dataclass
class CarouselSlideSpec:
    role: str
    text: str = ""
    heading: str = ""
    body: str = ""
    image_prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> CarouselSlideSpec:
        return cls(
            role=data.get("role", "slide"),
            text=data.get("text", ""),
            heading=data.get("heading", data.get("text", "")),
            body=data.get("body", ""),
            image_prompt=data.get("image_prompt", ""),
        )


@dataclass
class CarouselStrategy:
    type: str = "Offer"
    objective: str = "sales"
    template_key: str = "offer"
    slides: list[CarouselSlideSpec] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "objective": self.objective,
            "template_key": self.template_key,
            "slides": [s.to_dict() for s in self.slides],
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> CarouselStrategy | None:
        if not data or not isinstance(data, dict):
            return None
        slides = [
            CarouselSlideSpec.from_dict(s) if isinstance(s, dict) else CarouselSlideSpec(role="slide")
            for s in (data.get("slides") or [])
        ]
        return cls(
            type=data.get("type", "Offer"),
            objective=data.get("objective", "sales"),
            template_key=data.get("template_key", "offer"),
            slides=slides,
        )

    def to_carousel_slides(self) -> list[dict[str, Any]]:
        """Format for Post.carousel_slides."""
        out = []
        for spec in self.slides:
            out.append({
                "heading": spec.heading or spec.text or spec.role.replace("_", " ").title(),
                "body": spec.body,
                "funnel_role": spec.role,
                "image_prompt": spec.image_prompt,
            })
        return out


def select_carousel_template(
    *,
    objective: str = "sales",
    intent: str = "",
    target_intent: str = "",
) -> str:
    """Pick template key from campaign intent."""
    for key in (target_intent, intent, objective):
        if not key:
            continue
        normalized = str(key).lower().replace("-", "_")
        if normalized in INTENT_TO_TEMPLATE:
            return INTENT_TO_TEMPLATE[normalized]
        if normalized in CAROUSEL_TEMPLATES:
            return normalized
    return "offer"


def build_carousel_strategy(seed, campaign=None) -> CarouselStrategy:
    """Build carousel strategy from campaign context (rule-based v1)."""
    from apps.content.campaign_bundle import _campaign_context

    ctx = _campaign_context(seed)
    blueprint = getattr(seed, "blueprint", None) or {}
    objective = (
        getattr(campaign, "objective", None)
        or blueprint.get("objective")
        or "sales"
    )
    target_intent = getattr(seed, "target_intent", "") or ""
    template_key = select_carousel_template(
        objective=str(objective),
        intent=str(blueprint.get("proposal", {}).get("intent", "")),
        target_intent=target_intent,
    )
    template = CAROUSEL_TEMPLATES[template_key]
    name, price, title = ctx["name"], ctx["price"], ctx["title"]

    role_copy = {
        "hook": (f"Wait — {name}", f"Something worth your attention. Swipe 👉"),
        "problem": ("Sound familiar?", f"Tired of settling for less? You deserve better."),
        "solution": ("Here's the fix", f"{name} delivers what you've been missing."),
        "proof": ("Real results", "Trusted by customers who switched and never looked back."),
        "offer": ("Limited time", f"{price + ' — ' if price else ''}Grab yours before it's gone."),
        "cta": ("Ready?", "Tap the link in bio to order today."),
        "insight": ("Did you know?", f"The smartest move in {title[:40]} starts here."),
        "example": ("See it in action", f"{name} in real life — not just hype."),
        "question": ("Quick question", "What's holding you back?"),
        "answer": ("The answer", f"{name} solves the #1 pain point."),
        "challenge": ("The challenge", "Most businesses struggle with visibility."),
        "result": ("The outcome", "More sales, less stress."),
        "quote": ("Customer love", f'"Best decision we made." — Happy customer'),
        "benefit": ("Why it works", "Quality + value + service."),
        "reveal": ("Introducing", f"Meet {name}."),
        "feature": ("Standout feature", "Built for how you actually work."),
        "before": ("Before", "The old way wasn't cutting it."),
        "after": ("After", f"Life with {name} — upgraded."),
        "trend": ("Trend alert", "What's working right now in your niche."),
        "action": ("Your move", "Apply this in your business this week."),
    }

    slides: list[CarouselSlideSpec] = []
    for role in template["slide_roles"]:
        heading, body = role_copy.get(role, (role.replace("_", " ").title(), ""))
        slides.append(CarouselSlideSpec(
            role=role,
            text=heading,
            heading=heading,
            body=body,
            image_prompt=(
                f"Square carousel slide, role={role}, product={name}, "
                f"premium marketing visual, no embedded text"
            ),
        ))

    return CarouselStrategy(
        type=template["type"],
        objective=template.get("objective", str(objective)),
        template_key=template_key,
        slides=slides,
    )


def merge_llm_carousel_strategy(base: CarouselStrategy, llm_slides: list[dict]) -> CarouselStrategy:
    """Overlay LLM-generated slide copy onto strategy structure."""
    if not llm_slides:
        return base
    merged: list[CarouselSlideSpec] = []
    for i, spec in enumerate(base.slides):
        llm = llm_slides[i] if i < len(llm_slides) and isinstance(llm_slides[i], dict) else {}
        merged.append(CarouselSlideSpec(
            role=spec.role,
            text=llm.get("text") or llm.get("heading") or spec.text,
            heading=llm.get("heading") or llm.get("text") or spec.heading,
            body=llm.get("body") or spec.body,
            image_prompt=llm.get("image_prompt") or spec.image_prompt,
        ))
    return CarouselStrategy(
        type=base.type,
        objective=base.objective,
        template_key=base.template_key,
        slides=merged,
    )


def carousel_strategy_prompt_section(strategy: CarouselStrategy) -> str:
    lines = [
        "### CAROUSEL STRATEGY (required for Instagram carousel)",
        f"Type: {strategy.type} · Objective: {strategy.objective}",
        "Slides must follow this story arc:",
    ]
    for spec in strategy.slides:
        lines.append(f"- **{spec.role}**: {spec.heading} — {spec.body[:80]}")
    lines.append(
        'Include carousel_slides in JSON with heading, body, funnel_role, image_prompt per slide.'
    )
    return "\n".join(lines)
