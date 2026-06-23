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
