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


def build_surface_experience(*, profile=None, connected_platforms=None) -> dict:
    mode = infer_business_mode(profile, connected_platforms)
    surfaces = {
        "merchant": {
            "today_title": "Keep products moving today",
            "today_description": "Review stock, approve offer posts, and turn demand into purchases while the selling window is still hot.",
            "today_focus": ["Stock pressure", "Offer launches", "Revenue moves"],
            "today_actions": [
                {"label": "Review Queue", "url_name": "content:queue"},
                {"label": "Open Revenue", "url_name": "analytics:revenue"},
                {"label": "Snap to Sell", "url_name": "products:snap"},
            ],
            "workspace_title": "Run launches, approvals, and selling signals from one workspace",
            "workspace_description": "Use Standup for selling priorities, Moments for timely campaigns, and Listen to launch offers fast across your channels.",
            "workspace_focus": ["Offers", "Approvals", "Revenue"],
            "workspace_actions": [
                {"label": "Open Listen", "url_name": "command:listen"},
                {"label": "Open Standup", "url_name": "command:standup"},
            ],
            "catalog_kicker": "Fastest way to sell",
            "catalog_title": "Turn products into sellable campaigns fast",
            "catalog_description": "Snap, batch, and launch products with pricing, stock awareness, and promotion-ready copy in one flow.",
            "catalog_primary": {"label": "Snap to Sell", "url_name": "products:snap"},
            "catalog_secondary": {"label": "Batch Snap", "url_name": "products:snap_batch"},
            "catalog_empty_title": "No offers in your catalog yet",
            "catalog_empty_description": "Start with Snap to Sell and let Kova turn your products into listings, posts, and buying paths.",
            "nudge_title": "Connect a channel to turn attention into orders",
            "nudge_body": "Your AI selling loop gets stronger once Kova can see how your audience reacts, clicks, and converts.",
        },
        "service": {
            "today_title": "Turn attention into bookings",
            "today_description": "Prioritize replies, proof, and booking-ready follow-up so interested people move into consultations, appointments, and quotes.",
            "today_focus": ["Bookings", "Client proof", "Follow-up"],
            "today_actions": [
                {"label": "Open Bookings", "url_name": "bookings:list"},
                {"label": "Reply in Inbox", "url_name": "engage:inbox"},
                {"label": "Launch a service brief", "url_name": "command:listen"},
            ],
            "workspace_title": "Run your service pipeline from one workspace",
            "workspace_description": "Standup keeps client work and approvals clear, Moments finds relevant angles, and Listen turns one brief into booking-ready campaigns.",
            "workspace_focus": ["Bookings", "Credibility", "Client flow"],
            "workspace_actions": [
                {"label": "Create Booking Page", "url_name": "bookings:link_create"},
                {"label": "Open Listen", "url_name": "command:listen"},
            ],
            "catalog_kicker": "Bookable offers",
            "catalog_title": "Turn services into bookable offers",
            "catalog_description": "Package services with pricing, proof, and booking links so Kova can drive consultations instead of generic product CTAs.",
            "catalog_primary": {"label": "Add a service", "url_name": "products:add"},
            "catalog_secondary": {"label": "Create Booking Page", "url_name": "bookings:link_create"},
            "catalog_empty_title": "No service offers yet",
            "catalog_empty_description": "Add a service and connect it to booking so Kova can drive consultations, appointments, and quotes.",
            "nudge_title": "Connect a channel to turn interest into bookings",
            "nudge_body": "LinkedIn, Instagram, WhatsApp, and other channels give Kova the signal it needs to drive inquiries and appointments.",
        },
        "digital": {
            "today_title": "Turn content into access and signups",
            "today_description": "Focus on launches, lead capture, and conversion paths that move people into your digital offers, memberships, or learning products.",
            "today_focus": ["Launches", "Access paths", "Signups"],
            "today_actions": [
                {"label": "Launch from Workspace", "url_name": "command:listen"},
                {"label": "Review Queue", "url_name": "content:queue"},
                {"label": "Open Revenue", "url_name": "analytics:revenue"},
            ],
            "workspace_title": "Run launch loops and conversion sprints from one workspace",
            "workspace_description": "Standup keeps launches on track, Moments finds timely hooks, and Listen turns one idea into multi-touch campaigns for digital offers.",
            "workspace_focus": ["Launches", "Access", "Conversion"],
            "workspace_actions": [
                {"label": "Open Listen", "url_name": "command:listen"},
                {"label": "Open Standup", "url_name": "command:standup"},
            ],
            "catalog_kicker": "Digital launches",
            "catalog_title": "Launch digital offers with clearer access paths",
            "catalog_description": "Create digital offers with access links, delivery notes, and campaign-ready language that highlights instant value.",
            "catalog_primary": {"label": "Add a digital offer", "url_name": "products:add"},
            "catalog_secondary": {"label": "Launch from Workspace", "url_name": "command:listen"},
            "catalog_empty_title": "No digital offers yet",
            "catalog_empty_description": "Add a template, course, toolkit, or subscription so Kova can promote it with instant-access language.",
            "nudge_title": "Connect a channel to turn attention into signups",
            "nudge_body": "Your best growth loop comes from seeing which channels create clicks, replies, and conversions for digital offers.",
        },
        "expert": {
            "today_title": "Build authority and pipeline today",
            "today_description": "Focus on thought leadership, visibility, and the next conversations that turn audience attention into inbound opportunity.",
            "today_focus": ["Authority", "Visibility", "Pipeline"],
            "today_actions": [
                {"label": "Open Studio", "url_name": "content:studio"},
                {"label": "Launch a visibility sprint", "url_name": "command:listen"},
                {"label": "Open Leads", "url_name": "leads:list"},
            ],
            "workspace_title": "Operate your growth engine from one workspace",
            "workspace_description": "Standup keeps signals clear, Moments finds timely angles, and Listen turns one point of view into a multi-channel visibility sprint.",
            "workspace_focus": ["Authority", "Momentum", "Opportunities"],
            "workspace_actions": [
                {"label": "Open Listen", "url_name": "command:listen"},
                {"label": "Open Studio", "url_name": "content:studio"},
            ],
            "catalog_kicker": "Optional offers",
            "catalog_title": "Offers are optional — credibility is not",
            "catalog_description": "Use Kova to grow authority first, then add services or digital offers when you are ready to convert that attention.",
            "catalog_primary": {"label": "Open Studio", "url_name": "content:studio"},
            "catalog_secondary": {"label": "Open Workspace", "url_name": "command:home"},
            "catalog_empty_title": "No offers yet — your growth engine still works",
            "catalog_empty_description": "Use Studio and Workspace to grow authority now, then add services or digital offers when the time is right.",
            "nudge_title": "Connect your core channel to activate growth mode",
            "nudge_body": "Start with LinkedIn or your strongest platform so Kova can build visibility, authority, and inbound opportunity around real signals.",
        },
    }
    config = surfaces.get(mode, surfaces["expert"]).copy()
    config.update({
        "mode": mode,
        "mode_label": get_mode_label(mode),
        "mode_value_path": get_mode_value_path(mode),
    })
    return config
