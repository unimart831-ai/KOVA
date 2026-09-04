"""Kova product voice — single source for in-app copy aligned with brand docs."""

from __future__ import annotations

HEADLINE = "Your AI team handles social media."
SUBHEAD = "You approve in 5 minutes."
NORTH_STAR = "The system that chases money for your business while you run the shop."

LOOP_STEPS = (
    ("Snap", "Send a photo or showcase piece"),
    ("Create", "Kova drafts full marketing campaigns"),
    ("Approve", "You review in Studio — ~5 minutes"),
    ("Publish", "Posts go live on your channels"),
    ("Leads", "Inquiries land in your inbox"),
    ("Reply", "Kova drafts responses; you send"),
    ("Close", "Booking or M-Pesa payment"),
    ("Money", "See what drove revenue"),
)

APPROVE_FIRST = "Nothing publishes until you approve — you're the strategist, Kova is the team."

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
