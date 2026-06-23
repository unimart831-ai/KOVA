"""Kova product voice — single source for in-app copy aligned with brand docs."""

from __future__ import annotations

HEADLINE = "Your AI team handles social media."
SUBHEAD = "You approve in 5 minutes."
NORTH_STAR = "The system that chases money for your business while you run the shop."

LOOP_STEPS = (
    ("Snap", "Send a photo or showcase piece"),
    ("Create", "Kova drafts platform-native posts"),
    ("Approve", "You review in Studio — ~5 minutes"),
    ("Publish", "Posts go live on your channels"),
    ("Leads", "Inquiries land in your inbox"),
    ("Reply", "Kova drafts responses; you send"),
    ("Close", "Booking or M-Pesa payment"),
    ("Money", "See what drove revenue"),
)

APPROVE_FIRST = "Nothing publishes until you approve — you're the strategist, Kova is the team."

# ── Marketing / landing (public) ─────────────────────────────────────────────
MARKETING_BADGE = "More customers. Less work."
MARKETING_CATEGORY = "The AI marketing employee for African businesses."
MARKETING_HERO_SUBHEAD = "Your marketing for today is already done. Approve in 5 minutes."
MARKETING_HERO_BODY = (
    "Send a product, service, or portfolio item on WhatsApp. Kova creates content, "
    "publishes it, follows up with leads, and helps you get paid through M-Pesa — "
    "while you run your business."
)
MARKETING_HERO_STRIP = (
    ("Send a photo", "On WhatsApp or in the app"),
    ("Get content", "Posts, reels, carousels"),
    ("Get customers", "Leads & reply drafts"),
    ("Get paid", "M-Pesa & bookings"),
)

WHATSAPP_LOOP_STEPS = (
    ("Send photo on WhatsApp", "Product, service, or portfolio"),
    ("Kova creates content", "Post, reel, carousel, story"),
    ("You approve", "~5 minutes in Studio"),
    ("Posts go live", "Instagram, Facebook, TikTok & more"),
    ("Leads arrive", "DMs, forms, booking intent"),
    ("Kova drafts replies", "You send — your voice"),
    ("Customer pays", "M-Pesa or booking confirmed"),
    ("Daily revenue summary", "What made you money"),
)

BUILT_FOR_TYPES = (
    ("Retail & fashion", "Snap products → shop link + posts"),
    ("Salons & barbers", "Bookings on every post"),
    ("Restaurants & F&B", "Menus, offers, walk-in QR"),
    ("Agencies & designers", "Portfolio → authority posts"),
    ("Consultants & lawyers", "Case studies → consultation CTAs"),
    ("Service businesses", "Transformations & testimonials"),
)

OUTCOME_CAPABILITIES = (
    ("Finds opportunities", "Trends and angles in your market — surfaced in your morning brief, not a blank calendar."),
    ("Creates content", "Posts, reels, and carousels in your brand voice. One snap can become five assets."),
    ("Publishes everywhere", "Instagram, Facebook, LinkedIn, TikTok — native angles, not copy-paste."),
    ("Follows up with leads", "Comments and DMs with drafted replies. Hot leads flagged before they go cold."),
    ("Tracks sales", "M-Pesa, bookings, and walk-ins tied back to the post or offer that drove them."),
    ("Gets smarter daily", "What worked feeds the next batch — post #50 outperforms post #1."),
)


def marketing_voice_context() -> dict:
    """Copy bundle for public landing and marketing pages."""
    return {
        "marketing_badge": MARKETING_BADGE,
        "marketing_category": MARKETING_CATEGORY,
        "marketing_hero_subhead": MARKETING_HERO_SUBHEAD,
        "marketing_hero_body": MARKETING_HERO_BODY,
        "marketing_hero_strip": MARKETING_HERO_STRIP,
        "whatsapp_loop_steps": WHATSAPP_LOOP_STEPS,
        "built_for_types": BUILT_FOR_TYPES,
        "outcome_capabilities": OUTCOME_CAPABILITIES,
        "kova_north_star": NORTH_STAR,
        "kova_subhead": SUBHEAD,
    }

SEGMENT_COPY = {
    "product": {
        "today": "What needs your attention — leads, replies, and approvals in 5 minutes",
        "sell": "Photo + price → AI posts, shop link, and M-Pesa-ready offers",
        "catch": "Leads from DMs, links, and walk-ins — reply before they go cold",
        "close": "Track which posts and offers brought paying customers",
        "money": "Revenue tied to products and posts — not guesswork",
    },
    "service": {
        "today": "Bookings, hot leads, and posts to approve — your 5-minute morning",
        "sell": "List services → booking link on every post automatically",
        "catch": "Booking intents become hot leads with your calendar link ready",
        "close": "Consultations booked — see which content filled your calendar",
        "money": "Booking revenue and pipeline health in one place",
    },
    "professional": {
        "today": "Consultation leads, authority posts, and replies — approve in 5 minutes",
        "sell": "Portfolio & case studies → posts with consultation CTAs",
        "catch": "Consultation inquiries tagged and nurtured automatically",
        "close": "Booking-intent leads get your consultation link on WhatsApp",
        "money": "Top portfolio and case study driving pipeline this week",
    },
}


def segment_key(business_model: str) -> str:
    if business_model in SEGMENT_COPY:
        return business_model
    return "product"


def copy_for(business_model: str, surface: str, default: str = "") -> str:
    return SEGMENT_COPY.get(segment_key(business_model), {}).get(surface, default)


def kova_voice_for_user(user) -> dict:
    profile = getattr(user, "profile", None) if user and getattr(user, "is_authenticated", False) else None
    bm = getattr(profile, "business_model", "") if profile else ""
    sk = segment_key(bm)
    seg = SEGMENT_COPY[sk]
    return {
        "kova_headline": HEADLINE,
        "kova_subhead": SUBHEAD,
        "kova_north_star": NORTH_STAR,
        "kova_approve_first": APPROVE_FIRST,
        "kova_loop_steps": LOOP_STEPS,
        "business_model": bm,
        "kova_copy": seg,
        "kova_today_subtitle": seg["today"],
        "kova_sell_subtitle": seg["sell"],
        "kova_catch_subtitle": seg["catch"],
        "kova_close_subtitle": seg["close"],
        "kova_money_subtitle": seg["money"],
    }
