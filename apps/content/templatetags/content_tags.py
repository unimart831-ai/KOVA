from django import template

register = template.Library()

PLATFORM_DOT_COLORS = {
    "instagram": "bg-pink-500",
    "facebook": "bg-blue-600",
    "twitter": "bg-sky-500",
    "linkedin": "bg-blue-800",
    "tiktok": "bg-gray-900 dark:bg-white",
    "youtube": "bg-red-600",
    "whatsapp": "bg-green-500",
    "pinterest": "bg-red-500",
    "threads": "bg-gray-800 dark:bg-gray-200",
    "bluesky": "bg-blue-500",
}

_CAROUSEL_ROLE_LABELS = {
    "hook": "Hook",
    "showcase": "Showcase",
    "benefit": "Benefit",
    "price": "Price",
    "cta": "Closing CTA",
    "closing_cta": "Closing CTA",
}

_REEL_TEMPLATE_LABELS = {
    "lifestyle_story": "Lifestyle story",
    "product_reveal": "Product reveal",
    "story_arc": "Story arc",
    "carousel_to_video": "From carousel",
    "slideshow": "Slideshow",
    "flash": "Flash cuts",
}


@register.simple_tag
def post_showcase_badge(post):
    """Return showcase label dict for post cards, or empty dict."""
    from apps.content.post_labels import post_showcase_label

    return post_showcase_label(post) or {}


@register.filter
def platform_dot_color(post):
    """Return Tailwind bg class for a post's platform dot."""
    platform = getattr(post, "platform", "") or ""
    if not platform and hasattr(post, "social_account") and post.social_account:
        platform = post.social_account.platform
    return PLATFORM_DOT_COLORS.get(platform, "bg-gray-400")


@register.simple_tag
def carousel_slide_role(slide, post, index):
    """Resolve arc role for a carousel slide (slide.role or visual_metadata)."""
    if isinstance(slide, dict):
        role = (slide.get("role") or slide.get("funnel_role") or "").strip()
        if role:
            return role
    roles = (getattr(post, "visual_metadata", None) or {}).get("carousel_slide_roles") or []
    try:
        return str(roles[int(index)] or "")
    except (IndexError, TypeError, ValueError):
        return ""


@register.filter
def carousel_role_label(role):
    key = (role or "").strip().lower()
    if not key:
        return ""
    return _CAROUSEL_ROLE_LABELS.get(key, key.replace("_", " ").title())


@register.filter
def reel_template_label(template_id):
    key = (template_id or "").strip().lower()
    if not key:
        return ""
    return _REEL_TEMPLATE_LABELS.get(key, key.replace("_", " ").title())
