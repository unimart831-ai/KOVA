"""
Blueprint post-renderers — platform-native output from asset-centric blueprints.

Runs after LLM post dicts are parsed, before Post.objects.create.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_HASHTAG_RE = re.compile(r"(?:^|\s)(#\w+)", re.UNICODE)
_BOOKING_CTA_PLATFORMS = frozenset({"instagram", "facebook", "whatsapp", "tiktok", "linkedin"})


def _platform_spec(blueprint: dict, platform: str) -> dict | None:
    for spec in blueprint.get("platforms") or []:
        if spec.get("platform", "").lower() == platform.lower():
            return spec
    return None


def _booking_url_for_user(user) -> str:
    try:
        from apps.commerce.bookings.models import BookingLink
        from apps.commerce.bookings.service_setup import booking_public_url

        link = BookingLink.objects.filter(user=user, is_active=True).order_by("created_at").first()
        if link:
            return booking_public_url(link)
    except Exception:
        pass
    profile = getattr(user, "profile", None)
    if profile and profile.page_slug:
        from django.conf import settings

        site = getattr(settings, "SITE_URL", "").rstrip("/")
        return f"{site}/book/{profile.page_slug}/"
    return ""


def extract_slots_from_content(content_text: str, platform: str) -> dict[str, str]:
    """Heuristic slot extraction from a single LLM caption."""
    text = (content_text or "").strip()
    if not text:
        return {}

    hashtags = " ".join(_HASHTAG_RE.findall(text))
    body = _HASHTAG_RE.sub("", text).strip()
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]

    if platform == "instagram":
        hook = lines[0] if lines else ""
        caption = "\n".join(lines[1:]) if len(lines) > 1 else body
        return {
            "hook": hook,
            "caption": caption,
            "hashtags": hashtags,
            "cta": lines[-1] if lines and "book" in lines[-1].lower() else "",
        }
    if platform == "tiktok":
        return {
            "hook": lines[0] if lines else body[:80],
            "caption": body,
            "on_screen_text": (lines[0][:40] if lines else body[:40]),
            "cta": "",
        }
    if platform in ("facebook", "linkedin"):
        return {
            "headline": lines[0] if lines else "",
            "body": "\n".join(lines[1:]) if len(lines) > 1 else body,
            "cta": "",
        }
    if platform == "whatsapp":
        return {"message": body, "cta": ""}
    return {"body": body}


def compose_content_from_slots(slots: dict[str, str], platform: str) -> str:
    """Rebuild publish-ready content_text from filled slots."""
    if platform == "instagram":
        parts = [slots.get("hook", ""), slots.get("caption", ""), slots.get("cta", ""), slots.get("hashtags", "")]
        return "\n\n".join(p.strip() for p in parts if p and p.strip())
    if platform == "tiktok":
        parts = [slots.get("hook", ""), slots.get("caption", ""), slots.get("cta", "")]
        return "\n".join(p.strip() for p in parts if p and p.strip())
    if platform in ("facebook", "linkedin"):
        parts = [slots.get("headline", ""), slots.get("body", ""), slots.get("cta", "")]
        return "\n\n".join(p.strip() for p in parts if p and p.strip())
    if platform == "whatsapp":
        parts = [slots.get("message", ""), slots.get("cta", "")]
        return "\n".join(p.strip() for p in parts if p and p.strip())
    return slots.get("body", "") or slots.get("caption", "")


def _ensure_booking_cta(slots: dict[str, str], platform: str, booking_url: str) -> dict[str, str]:
    if not booking_url:
        return slots
    cta_key = "cta" if platform != "whatsapp" else "cta"
    existing = (slots.get(cta_key) or slots.get("message", "") or "").lower()
    if booking_url.lower() in existing or "book" in existing:
        return slots
    cta_line = f"Book here: {booking_url}"
    slots = dict(slots)
    if platform == "whatsapp":
        slots["cta"] = cta_line
    else:
        slots["cta"] = cta_line
    return slots


def _format_from_spec(spec: dict | None, asset_type: str) -> str:
    if not spec:
        return "text"
    fmt = spec.get("format", "feed")
    mapping = {
        "feed": "image",
        "carousel": "carousel",
        "reel": "reel",
        "status": "story",
    }
    return mapping.get(fmt, fmt if fmt in {"text", "image", "carousel", "story", "reel"} else "image")


def apply_blueprint_renderer(
    post_dict: dict,
    blueprint: dict,
    user,
) -> dict:
    """
    Merge blueprint spec into an LLM post dict.
    Returns updated post_dict (mutates copy).
    """
    if not blueprint:
        return post_dict

    platform = (post_dict.get("platform") or "").lower().strip()
    spec = _platform_spec(blueprint, platform)
    objective = blueprint.get("objective", "")
    asset_type = blueprint.get("asset_type", "")

    slots = extract_slots_from_content(post_dict.get("content_text", ""), platform)
    if spec and spec.get("slots"):
        for key in spec["slots"]:
            slots.setdefault(key, spec["slots"][key])

    if objective == "book" or asset_type == "service":
        booking_url = _booking_url_for_user(user)
        slots = _ensure_booking_cta(slots, platform, booking_url)

    meta = blueprint.get("metadata") or {}
    suggested_cta = meta.get("suggested_cta", "")
    if suggested_cta and not slots.get("cta"):
        slots["cta"] = suggested_cta

    post_dict = dict(post_dict)
    post_dict["content_text"] = compose_content_from_slots(slots, platform)

    if spec:
        post_dict["post_format"] = _format_from_spec(spec, asset_type)

    intent = meta.get("content_intent")
    if intent and not post_dict.get("content_intent"):
        post_dict["content_intent"] = intent

    post_dict["_blueprint_slots"] = slots
    return post_dict


def blueprint_quality_score(post_dict: dict, blueprint: dict) -> int:
    """
    Score 0-100: how well the post aligns with its blueprint spec.
    Used for logging and future retry logic.
    """
    if not blueprint:
        return 100

    platform = (post_dict.get("platform") or "").lower().strip()
    spec = _platform_spec(blueprint, platform)
    if not spec:
        return 70

    score = 50
    content = (post_dict.get("content_text") or "").strip()
    if len(content) >= 40:
        score += 15
    if len(content) >= 120:
        score += 10

    fmt = spec.get("format", "feed")
    post_format = (post_dict.get("post_format") or "text").lower()
    expected = _format_from_spec(spec, blueprint.get("asset_type", ""))
    if post_format == expected:
        score += 15

    objective = blueprint.get("objective", "")
    if objective == "book" and "book" in content.lower():
        score += 10
    if objective == "sell" and any(w in content.lower() for w in ("buy", "order", "shop", "kes", "price")):
        score += 10

    slots = post_dict.get("_blueprint_slots") or extract_slots_from_content(content, platform)
    filled = sum(1 for v in slots.values() if v and str(v).strip())
    score += min(10, filled * 2)

    return min(100, max(0, score))


def should_retry_low_quality(score: int, *, threshold: int = 55) -> bool:
    """Whether a post would benefit from regeneration (future auto-retry)."""
    return score < threshold
