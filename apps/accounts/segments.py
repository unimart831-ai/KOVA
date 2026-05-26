from __future__ import annotations

from collections.abc import Iterable


MERCHANT_INDUSTRIES = {
    "ecommerce",
    "wholesale_retail",
    "fashion_beauty",
    "food_restaurant",
    "agriculture",
    "travel_tourism",
}

SERVICE_INDUSTRIES = {
    "agency",
    "consulting",
    "health",
    "finance",
    "real_estate",
    "salon_beauty",
    "legal",
    "education",
    "construction",
    "logistics_transport",
}

DIGITAL_INDUSTRIES = {
    "saas",
}

EXPERT_INDUSTRIES = {
    "creator",
    "media_entertainment",
    "nonprofit",
    "other",
}

SERVICE_KEYWORDS = {
    "consultation",
    "consulting",
    "session",
    "appointment",
    "call",
    "coaching",
    "service",
    "training",
    "workshop",
    "audit",
    "strategy day",
    "retainer",
    "booking",
    "quote",
}

DIGITAL_KEYWORDS = {
    "ebook",
    "e-book",
    "template",
    "download",
    "course",
    "guide",
    "membership",
    "subscription",
    "software",
    "saas",
    "toolkit",
    "digital",
    "webinar",
    "masterclass",
    "resource",
    "licence",
    "license",
}

EXPERT_GOAL_KEYWORDS = {
    "grow followers",
    "grow audience",
    "personal brand",
    "thought leadership",
    "build authority",
    "grow on social",
    "networking",
    "professional growth",
}

EXPERT_PLATFORMS = {"linkedin", "twitter", "x", "threads", "bluesky"}

MODE_LABELS = {
    "merchant": "Merchant mode",
    "service": "Service mode",
    "digital": "Digital mode",
    "expert": "Expert mode",
}

MODE_VALUE_PATHS = {
    "merchant": "Sell products, move stock, launch offers, and convert demand into purchases.",
    "service": "Turn attention into consultations, appointments, quotes, and repeat bookings.",
    "digital": "Sell access, downloads, templates, subscriptions, or learning products with low friction.",
    "expert": "Build authority, grow audience, and convert social attention into inbound opportunities.",
}

MODE_CTA_GUIDANCE = {
    "merchant": ["Shop now", "Order today", "Buy now", "DM to order"],
    "service": ["Book a consultation", "Schedule a session", "Request a quote", "Let's work together"],
    "digital": ["Get instant access", "Download now", "Enroll now", "Start learning today"],
    "expert": ["Reply to this", "DM me", "Join the list", "Book a call", "Let's connect"],
}

OFFER_PROMPT_GUIDANCE = {
    "product": {
        "heading": "### PRODUCT BEING PROMOTED",
        "url_label": "Purchase URL",
        "cta_hint": "Use this URL for 'Shop Now', 'Buy Now', or 'Get Yours' CTAs.",
    },
    "service": {
        "heading": "### SERVICE BEING PROMOTED",
        "url_label": "Primary booking / inquiry URL",
        "cta_hint": "Use this URL for 'Book a consultation', 'Schedule a session', 'Request a quote', or 'Let's work together' CTAs.",
    },
    "digital": {
        "heading": "### DIGITAL OFFER BEING PROMOTED",
        "url_label": "Primary access URL",
        "cta_hint": "Use this URL for 'Get instant access', 'Download now', 'Enroll now', or 'Start learning today' CTAs.",
    },
}


def _normalize_list(values) -> list[str]:
    if isinstance(values, str):
        raw = [values]
    elif isinstance(values, Iterable):
        raw = list(values)
    else:
        raw = []
    return [str(v).strip() for v in raw if str(v).strip()]


def _profile_text(profile) -> str:
    if not profile:
        return ""
    parts = [
        getattr(profile, "company_name", ""),
        getattr(profile, "industry_other", ""),
        getattr(profile, "target_audience", ""),
        " ".join(_normalize_list(getattr(profile, "key_offerings", []))),
        " ".join(_normalize_list(getattr(profile, "goals", []))),
    ]
    return " ".join(parts).lower()


def _platform_set(profile, connected_platforms=None) -> set[str]:
    platforms = {str(p).lower() for p in _normalize_list(connected_platforms)}
    if platforms:
        return platforms
    profile_priority = getattr(profile, "platform_priority", {}) if profile else {}
    if isinstance(profile_priority, dict):
        platforms.update(str(k).lower() for k in profile_priority.keys() if k)
    return platforms


def infer_business_mode(profile, connected_platforms=None) -> str:
    if not profile:
        return "merchant"

    industry = (getattr(profile, "industry", "") or "").strip()
    text = _profile_text(profile)
    platforms = _platform_set(profile, connected_platforms)
    goals_text = " ".join(_normalize_list(getattr(profile, "goals", []))).lower()

    if any(keyword in text for keyword in DIGITAL_KEYWORDS):
        return "digital"
    if any(keyword in text for keyword in SERVICE_KEYWORDS):
        return "service"

    if industry in DIGITAL_INDUSTRIES:
        return "digital"
    if industry in SERVICE_INDUSTRIES:
        return "service"
    if industry in MERCHANT_INDUSTRIES:
        return "merchant"
    if industry in EXPERT_INDUSTRIES:
        return "expert"

    if any(keyword in goals_text for keyword in EXPERT_GOAL_KEYWORDS):
        return "expert"
    if platforms and platforms.issubset(EXPERT_PLATFORMS):
        return "expert"

    return "expert"


def get_mode_label(mode: str) -> str:
    return MODE_LABELS.get(mode, MODE_LABELS["expert"])


def get_mode_value_path(mode: str) -> str:
    return MODE_VALUE_PATHS.get(mode, MODE_VALUE_PATHS["expert"])


def get_mode_cta_guidance(mode: str) -> list[str]:
    return MODE_CTA_GUIDANCE.get(mode, MODE_CTA_GUIDANCE["expert"])


def get_offer_prompt_guidance(offering_type: str) -> dict[str, str]:
    return OFFER_PROMPT_GUIDANCE.get(offering_type or "product", OFFER_PROMPT_GUIDANCE["product"])


def build_segment_prompt_context(*, profile=None, connected_platforms=None) -> str:
    if not profile:
        return ""

    mode = infer_business_mode(profile, connected_platforms)
    audience = (getattr(profile, "target_audience", "") or "").strip() or "General audience"
    offerings = _normalize_list(getattr(profile, "key_offerings", []))[:5]
    goals = _normalize_list(getattr(profile, "goals", []))[:4]
    platforms = sorted(_platform_set(profile, connected_platforms))

    lines = [
        "### BUSINESS MODEL CONTEXT",
        f"- **Operating mode**: {get_mode_label(mode)}",
        f"- **Primary value path**: {get_mode_value_path(mode)}",
        f"- **Preferred CTA patterns**: {', '.join(get_mode_cta_guidance(mode))}",
        f"- **Target audience**: {audience}",
    ]
    if offerings:
        lines.append(f"- **Key offerings / topics**: {', '.join(offerings)}")
    if goals:
        lines.append(f"- **Current goals**: {', '.join(goals)}")
    if platforms:
        lines.append(f"- **Connected platforms**: {', '.join(platforms)}")

    if mode == "service":
        lines.append("- **Strategy note**: Prioritize expertise, results, trust, and clear booking or inquiry paths over product-selling language.")
    elif mode == "digital":
        lines.append("- **Strategy note**: Emphasize transformation, instant access, learning, implementation, or recurring value rather than shipping or stock.")
    elif mode == "expert":
        lines.append("- **Strategy note**: Prioritize thought leadership, authority, profile growth, list growth, and inbound opportunities over generic commerce CTAs unless the brief explicitly sells an offer.")
    else:
        lines.append("- **Strategy note**: Make offers concrete, timely, and easy to act on with strong proof and clear conversion steps.")

    return "\n".join(lines)


def get_mode_fallback_topics(mode: str) -> list[str]:
    topics = {
        "merchant": ["tip", "story", "product highlight", "customer win", "behind the scenes"],
        "service": ["client result", "service walkthrough", "FAQ", "trust builder", "behind the scenes"],
        "digital": ["how-to", "transformation story", "offer breakdown", "FAQ", "build note"],
        "expert": ["opinion", "lesson", "framework", "client insight", "behind the scenes"],
    }
    return topics.get(mode, topics["expert"])
