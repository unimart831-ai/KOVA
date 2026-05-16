"""Booking intent detection for Engage Agent (Phase 2 W7-8).

Light-touch heuristic. Returns True when an incoming comment / DM
expresses booking intent — e.g. "can I book braids saturday?", "are
you open Thursday?", "what time is free?".

When detected and the user has at least one active BookingLink, the
replier appends the booking URL to the draft response.
"""
from __future__ import annotations

import re
from urllib.parse import urlencode


# Anchored patterns to keep matches intentional. Keep this list small
# and audited — false-positives spam booking links into unrelated replies.
_BOOKING_PATTERNS = [
    r"\bbook(?:ing|ed)?\b",
    r"\breserve\b",
    r"\bappointment\b",
    r"\bschedule\b",
    r"\bopen\b\s+(?:on\s+)?\w+(?:day)?",  # "open Saturday"
    r"\bavailable\b",
    r"\bwhat time\b",
    r"\bany slot",
    r"\bany time\b",
    r"\bcan i come\b",
    # Swahili
    r"\bbeza\b",        # informal "make/book"
    r"\bnataka\b",      # "I want"
    r"\bniko\b",        # "I'm here/available"
]


_COMPILED = [re.compile(p, re.IGNORECASE) for p in _BOOKING_PATTERNS]


def detect_booking_intent(message: str) -> bool:
    """Returns True when the message expresses booking intent."""
    if not message:
        return False
    return any(p.search(message) for p in _COMPILED)


def build_booking_suffix(user, source_channel: str = "engage_agent") -> str:
    """Return a short "Tap to book: …" suffix for replies, or "" if
    the user has no active BookingLink.

    Source channel is appended as ?src= so attribution survives the click.
    """
    try:
        from apps.bookings.models import BookingLink
    except Exception:
        return ""
    link = (
        BookingLink.objects
        .filter(user=user, is_active=True)
        .order_by("-created_at")
        .first()
    )
    if not link:
        return ""
    qs = urlencode({"src": source_channel})
    # We don't have the request here — construct a relative URL the
    # platform will see as plain text. SMEs paste their domain or kova.link
    # subdomain into the reply manually if they want a fully-qualified URL.
    base = getattr_setting("KOVA_PUBLIC_BASE_URL", "")
    path = f"/book/{link.slug}/?{qs}"
    full = f"{base.rstrip('/')}{path}" if base else path
    return f"\n\nTap to book: {full}"


def getattr_setting(name: str, default: str = "") -> str:
    try:
        from django.conf import settings
        return getattr(settings, name, default) or default
    except Exception:
        return default


def augment_reply_with_booking_link(reply: str, user, comment_text: str, source_channel: str = "engage_agent") -> str:
    """Convenience: if intent is detected, append the booking link.

    The replier calls this on its draft before scoring confidence.
    """
    if not detect_booking_intent(comment_text):
        return reply
    suffix = build_booking_suffix(user, source_channel)
    if not suffix:
        return reply
    return (reply or "").rstrip() + suffix
