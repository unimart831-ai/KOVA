"""Auto-fill consultation CTAs on professional / authority posts."""

from __future__ import annotations

import hashlib

PROFESSIONAL_PLATFORMS = frozenset({"linkedin", "facebook"})

_CONSULTATION_FC_LINKEDIN = [
    "If you'd like to talk this through — book a free consultation here:\n{url}",
    "Happy to dive deeper in a call. Grab a slot here:\n{url}",
    "Questions welcome in comments — or book a consultation:\n{url}",
    "For a tailored conversation on this, book here:\n{url}",
]

_CONSULTATION_FC_FACEBOOK = [
    "Want to talk this through? Book a free consultation 👇\n{url}",
    "Tap to book a call — we'll walk through your situation:\n{url}",
    "Ready when you are — consultation booking:\n{url}",
    "Book a free consult if this resonates:\n{url}",
]


def _fc_bucket(post_id: str) -> int:
    if not post_id:
        return 0
    return int(hashlib.md5(post_id.encode("utf-8")).hexdigest()[:8], 16)


def compose_professional_first_comment(platform: str, post, *, cta_text: str = "", url: str = "") -> str:
    """Link-in-comments first comment for consultation CTAs on FB / LinkedIn."""
    if platform not in PROFESSIONAL_PLATFORMS:
        return ""
    link = (url or getattr(post, "cta_url", "") or "").strip()
    if not link:
        return ""
    templates = _CONSULTATION_FC_LINKEDIN if platform == "linkedin" else _CONSULTATION_FC_FACEBOOK
    template = templates[_fc_bucket(str(getattr(post, "id", ""))) % len(templates)]
    return template.format(url=link).strip()


def consultation_url_for_user(user) -> str:
    """Best URL for a consultation/booking CTA."""
    try:
        from apps.bookings.models import BookingLink
        from apps.bookings.service_setup import booking_public_url

        link = BookingLink.objects.filter(user=user, is_active=True).order_by("created_at").first()
        if link:
            return booking_public_url(link)
    except Exception:
        pass

    profile = getattr(user, "profile", None)
    if profile:
        from apps.products.commerce_canonical import canonical_business_url

        url = canonical_business_url(user, profile)
        if url:
            return url

    return ""


def should_apply_professional_cta(user, seed, platform: str) -> bool:
    if platform not in PROFESSIONAL_PLATFORMS:
        return False
    profile = getattr(user, "profile", None)
    blueprint = getattr(seed, "blueprint", None) or {} if seed else {}
    asset_type = blueprint.get("asset_type", "")
    if profile and getattr(profile, "business_model", "") == "professional":
        return True
    return asset_type in ("portfolio", "case_study", "testimonial")


def apply_professional_cta_to_post(post, user, seed=None) -> bool:
    """Set link CTA on LinkedIn/Facebook posts for professional businesses."""
    platform = post.platform or (post.social_account.platform if post.social_account else "")
    if not should_apply_professional_cta(user, seed, platform):
        return False

    url = consultation_url_for_user(user)
    if not url:
        return False

    blueprint = getattr(seed, "blueprint", None) or {} if seed else {}
    meta = blueprint.get("metadata") or {}
    cta_text = (meta.get("suggested_cta") or "Book a free consultation →")[:255]

    post.cta_type = "link"
    post.cta_text = cta_text
    post.cta_url = url[:500]
    update_fields = ["cta_type", "cta_text", "cta_url", "updated_at"]

    fc = compose_professional_first_comment(platform, post, cta_text=cta_text, url=url)
    if fc:
        post.first_comment = fc
        update_fields.append("first_comment")

    post.save(update_fields=update_fields)
    return True
