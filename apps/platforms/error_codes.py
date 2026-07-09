"""
Platform API error code translation.

Maps known platform error codes to:
  - user_message: plain-English explanation
  - fix: specific action the user should take
  - retryable: whether Kova should retry automatically

Usage:
    from apps.platforms.error_codes import translate_error
    info = translate_error("facebook", 190, raw_error_string)
    # info.user_message, info.fix, info.retryable
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorInfo:
    user_message: str
    fix: str
    retryable: bool = False
    is_auth: bool = False        # True → token dead, must reconnect
    is_rate_limit: bool = False  # True → back off, retry later
    is_outage: bool = False      # True → platform down, retry in hours


# ─────────────────────────────────────────────────────────────────────────────
# Facebook / Instagram
# ─────────────────────────────────────────────────────────────────────────────
_FACEBOOK = {
    190: ErrorInfo(
        "Your Facebook connection has expired or been revoked.",
        "Go to Settings → Platforms → Reconnect Facebook.",
        is_auth=True,
    ),
    102: ErrorInfo(
        "Facebook session expired.",
        "Go to Settings → Platforms → Reconnect Facebook.",
        is_auth=True,
    ),
    200: ErrorInfo(
        "Kova doesn't have permission to post to this Facebook Page.",
        "Disconnect and reconnect Facebook, approving all requested permissions.",
        is_auth=True,
    ),
    10: ErrorInfo(
        "Kova's Facebook app is missing a required permission.",
        "Contact Kova support — this requires an app configuration fix.",
    ),
    4: ErrorInfo(
        "Facebook's app-wide rate limit has been reached.",
        "Your post will be retried automatically in 30 minutes.",
        retryable=True, is_rate_limit=True,
    ),
    17: ErrorInfo(
        "Too many requests from this Facebook account right now.",
        "Your post will be retried automatically in 1 hour.",
        retryable=True, is_rate_limit=True,
    ),
    32: ErrorInfo(
        "Too many posts to this Facebook Page today.",
        "Your post will be retried tomorrow at the same time.",
        retryable=True, is_rate_limit=True,
    ),
    368: ErrorInfo(
        "Facebook has temporarily restricted this account.",
        "Check your Facebook Page for any policy warnings or restrictions, then try again.",
    ),
    12: ErrorInfo(
        "Facebook returned a deprecated API response for this post type.",
        "No action needed — Kova will skip comment sync for this post format.",
        retryable=False,
    ),
    100: ErrorInfo(
        "Facebook rejected this post — the content or media has an issue.",
        "Edit the post and try again. Check image format, caption length, and hashtags.",
        retryable=False,
    ),
    506: ErrorInfo(
        "Duplicate post — Facebook detected this content was recently posted.",
        "Edit the caption to make it unique before posting again.",
    ),
    2500: ErrorInfo(
        "Instagram requires a Professional account to post via API.",
        "In Instagram Settings → Account → Switch to Professional Account (Business or Creator).",
    ),
    24: ErrorInfo(
        "Instagram account is not connected to a Facebook Page.",
        "In Instagram Settings → Account → Linked Accounts → Connect Facebook.",
    ),
    36000: ErrorInfo(
        "Instagram caption is too long.",
        "Edit the post — Instagram allows a maximum of 2,200 characters.",
    ),
    9004: ErrorInfo(
        "Instagram requires a valid image URL.",
        "The image may not be accessible publicly. Try uploading the image directly.",
        retryable=True,
    ),
    500: ErrorInfo(
        "Facebook is experiencing issues right now.",
        "Your post is being held and will publish automatically when Facebook recovers.",
        retryable=True, is_outage=True,
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# LinkedIn
# ─────────────────────────────────────────────────────────────────────────────
_LINKEDIN = {
    401: ErrorInfo(
        "Your LinkedIn connection has expired.",
        "Go to Settings → Platforms → Reconnect LinkedIn.",
        is_auth=True,
    ),
    403: ErrorInfo(
        "Kova doesn't have the right permissions for LinkedIn.",
        "Disconnect and reconnect LinkedIn, approving all requested permissions.",
        is_auth=True,
    ),
    422: ErrorInfo(
        "LinkedIn rejected this post's content.",
        "Edit the caption — check for policy violations or unsupported characters.",
    ),
    429: ErrorInfo(
        "LinkedIn's daily rate limit has been reached.",
        "Your post will be retried tomorrow.",
        retryable=True, is_rate_limit=True,
    ),
    500: ErrorInfo(
        "LinkedIn is experiencing server issues.",
        "Your post is being held and will publish automatically when LinkedIn recovers.",
        retryable=True, is_outage=True,
    ),
    503: ErrorInfo(
        "LinkedIn is temporarily unavailable.",
        "Your post is being held and will publish automatically when LinkedIn recovers.",
        retryable=True, is_outage=True,
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# TikTok
# ─────────────────────────────────────────────────────────────────────────────
_TIKTOK = {
    10002: ErrorInfo(
        "Kova doesn't have permission to post videos to TikTok.",
        "Disconnect and reconnect TikTok, approving all requested permissions.",
        is_auth=True,
    ),
    10003: ErrorInfo(
        "Your TikTok connection has expired.",
        "Go to Settings → Platforms → Reconnect TikTok.",
        is_auth=True,
    ),
    10004: ErrorInfo(
        "TikTok account not found.",
        "Disconnect and reconnect your TikTok account.",
        is_auth=True,
    ),
    10005: ErrorInfo(
        "Your TikTok access token has been revoked.",
        "Go to Settings → Platforms → Reconnect TikTok.",
        is_auth=True,
    ),
    20001: ErrorInfo(
        "TikTok rejected this video for policy reasons.",
        "Check that the video doesn't violate TikTok Community Guidelines.",
    ),
    20002: ErrorInfo(
        "TikTok requires a video — this post format isn't supported for TikTok.",
        "Edit the post and attach a video file.",
    ),
    10016: ErrorInfo(
        "TikTok rate limit reached.",
        "Your post will be retried automatically.",
        retryable=True, is_rate_limit=True,
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# WhatsApp
# ─────────────────────────────────────────────────────────────────────────────
_WHATSAPP = {
    131030: ErrorInfo(
        "WhatsApp rate limit — too many messages sent recently.",
        "Your message will be retried automatically in 1 hour.",
        retryable=True, is_rate_limit=True,
    ),
    130472: ErrorInfo(
        "WhatsApp message template not approved.",
        "Go to Meta Business Manager and check your message template approval status.",
    ),
    131047: ErrorInfo(
        "This WhatsApp contact has not opted in to receive messages.",
        "You can only message contacts who have opted in via your WhatsApp Business flow.",
    ),
    131026: ErrorInfo(
        "WhatsApp recipient phone number is invalid or not registered.",
        "Check the contact's phone number is correct and registered on WhatsApp.",
    ),
    500: ErrorInfo(
        "WhatsApp API is experiencing issues.",
        "Your message will be retried automatically.",
        retryable=True, is_outage=True,
    ),
}

_REGISTRY: dict[str, dict[int, ErrorInfo]] = {
    "facebook": _FACEBOOK,
    "instagram": _FACEBOOK,  # shares FB error codes
    "linkedin": _LINKEDIN,
    "tiktok": _TIKTOK,
    "whatsapp": _WHATSAPP,
}

_UNKNOWN = ErrorInfo(
    "An unexpected error occurred while publishing.",
    "If this keeps happening, contact support with the error code below.",
    retryable=False,
)


def translate_error(platform: str, code: int | None, raw: str = "") -> ErrorInfo:
    """
    Return a human-readable ErrorInfo for a platform error code.

    Falls back to generic 5xx outage info for unmapped 5xx status codes,
    and _UNKNOWN for everything else.
    """
    codes = _REGISTRY.get(platform, {})
    if code and code in codes:
        return codes[code]

    # Generic 5xx → treated as outage
    if code and 500 <= code < 600:
        return ErrorInfo(
            f"{platform.title()} is experiencing server issues.",
            "Your post is being held and will publish automatically when the platform recovers.",
            retryable=True, is_outage=True,
        )

    # Generic 429 → rate limit
    if code == 429:
        return ErrorInfo(
            f"{platform.title()}'s rate limit has been reached.",
            "Your post will be retried automatically.",
            retryable=True, is_rate_limit=True,
        )

    # Auth-like strings in raw message (exclude deprecated-API noise)
    raw_lower = raw.lower()
    if "singular statuses" in raw_lower or "(#12)" in raw_lower:
        return codes.get(12, _UNKNOWN)
    if any(kw in raw_lower for kw in ("token", "expired", "invalid_token", "401", "unauthorized")):
        return ErrorInfo(
            f"Your {platform.title()} connection has expired or been revoked.",
            f"Go to Settings → Platforms → Reconnect {platform.title()}.",
            is_auth=True,
        )

    return _UNKNOWN
