"""Public social/contact links for commerce shop pages."""

from __future__ import annotations

import re
from urllib.parse import quote

from apps.platforms.models import SocialAccount

# Platforms shown on public shop nav (order matters for mobile bar).
SHOP_NAV_PLATFORMS: tuple[str, ...] = (
    "whatsapp",
    "instagram",
    "facebook",
    "tiktok",
    "youtube",
    "twitter",
    "threads",
    "linkedin",
)

_PLATFORM_LABELS: dict[str, str] = {
    "whatsapp": "WhatsApp",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "tiktok": "TikTok",
    "youtube": "YouTube",
    "twitter": "X",
    "threads": "Threads",
    "linkedin": "LinkedIn",
}

_NON_DIGIT_RE = re.compile(r"\D")


def normalize_whatsapp_number(raw: str) -> str:
    """Digits-only international format for wa.me links."""
    if not raw:
        return ""
    cleaned = (raw or "").strip()
    if cleaned.startswith("+"):
        digits = _NON_DIGIT_RE.sub("", cleaned[1:])
        return digits if digits else ""
    digits = _NON_DIGIT_RE.sub("", cleaned)
    if digits.startswith("0") and len(digits) == 10:
        return f"254{digits[1:]}"
    return digits


def resolve_shop_whatsapp(profile, user=None) -> str:
    """
    WhatsApp number for shop CTAs.

    Priority: profile.cta_whatsapp → active booking link → connected WA platform.
    """
    number = normalize_whatsapp_number(profile.cta_whatsapp or "")
    if number:
        return number

    if user is not None:
        bl = user.booking_links.filter(is_active=True).first()
        if bl and bl.owner_whatsapp:
            number = normalize_whatsapp_number(bl.owner_whatsapp)
            if number:
                return number

        wa_account = (
            SocialAccount.objects.filter(
                user=user,
                platform=SocialAccount.Platform.WHATSAPP,
                is_active=True,
            )
            .order_by("-connected_at")
            .first()
        )
        if wa_account:
            meta_phone = (wa_account.metadata or {}).get("display_phone_number", "")
            number = normalize_whatsapp_number(wa_account.username or meta_phone)
            if number:
                return number

    return ""


def _clean_username(username: str) -> str:
    return (username or "").strip().lstrip("@")


def platform_public_url(platform: str, username: str, metadata: dict | None = None) -> str:
    """Build a buyer-facing profile URL from a connected account."""
    meta = metadata or {}
    handle = _clean_username(username)
    if not handle and not meta:
        return ""

    if platform == "instagram":
        return f"https://www.instagram.com/{handle}/" if handle else ""
    if platform == "facebook":
        if meta.get("page_username"):
            return f"https://www.facebook.com/{_clean_username(meta['page_username'])}/"
        return f"https://www.facebook.com/{handle}/" if handle else ""
    if platform == "tiktok":
        return f"https://www.tiktok.com/@{handle}" if handle else ""
    if platform == "youtube":
        if handle.startswith("UC") or handle.startswith("channel/"):
            path = handle if handle.startswith("channel/") else f"channel/{handle}"
            return f"https://www.youtube.com/{path}"
        return f"https://www.youtube.com/@{handle}" if handle else ""
    if platform == "twitter":
        return f"https://x.com/{handle}" if handle else ""
    if platform == "threads":
        return f"https://www.threads.net/@{handle}" if handle else ""
    if platform == "linkedin":
        if handle.startswith("http"):
            return handle
        if "/" in handle:
            return f"https://www.linkedin.com/{handle}"
        return f"https://www.linkedin.com/in/{handle}/" if handle else ""
    if platform == "whatsapp":
        number = normalize_whatsapp_number(handle or meta.get("display_phone_number", ""))
        return f"https://wa.me/{number}" if number else ""

    profile_url = meta.get("profile_url") or meta.get("public_profile_url") or ""
    return profile_url if isinstance(profile_url, str) else ""


def get_public_social_links(
    user,
    profile,
    *,
    wa_text: str = "",
    include_whatsapp: bool = True,
) -> list[dict]:
    """
    Social/contact links for public shop nav.

    Returns list of dicts: {platform, url, label, icon, primary}.
    Only includes platforms the seller has connected (plus WhatsApp when configured).
    """
    links: list[dict] = []
    seen_platforms: set[str] = set()

    if include_whatsapp:
        wa_number = resolve_shop_whatsapp(profile, user)
        if wa_number:
            url = f"https://wa.me/{wa_number}"
            if wa_text:
                url = f"{url}?text={quote(wa_text)}"
            links.append({
                "platform": "whatsapp",
                "url": url,
                "label": _PLATFORM_LABELS["whatsapp"],
                "icon": "whatsapp",
                "primary": True,
            })
            seen_platforms.add("whatsapp")

    accounts = (
        SocialAccount.objects.filter(user=user, is_active=True)
        .exclude(platform=SocialAccount.Platform.WHATSAPP)
        .order_by("platform", "-connected_at")
    )
    for account in accounts:
        platform = account.platform
        if platform not in SHOP_NAV_PLATFORMS or platform in seen_platforms:
            continue
        url = platform_public_url(platform, account.username, account.metadata)
        if not url:
            continue
        links.append({
            "platform": platform,
            "url": url,
            "label": account.display_name or _PLATFORM_LABELS.get(platform, platform.title()),
            "icon": platform,
            "primary": False,
        })
        seen_platforms.add(platform)

    # Stable nav order: WhatsApp first, then SHOP_NAV_PLATFORMS order.
    order = {p: i for i, p in enumerate(SHOP_NAV_PLATFORMS)}
    links.sort(key=lambda item: order.get(item["platform"], 99))
    return links
