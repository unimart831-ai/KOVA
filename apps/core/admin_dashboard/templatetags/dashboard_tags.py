from django import template

register = template.Library()


@register.filter
def format_number(value):
    """Format large numbers: 1234 → 1.2K, 1234567 → 1.2M."""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return value or 0
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


@register.filter
def percentage(value, total):
    """Calculate percentage: {{ part|percentage:whole }}."""
    try:
        return f"{(int(value) / int(total)) * 100:.1f}"
    except (TypeError, ValueError, ZeroDivisionError):
        return "0"


@register.filter
def status_color(status):
    """Map status strings to Tailwind color classes."""
    colors = {
        # Post statuses
        "draft": "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
        "pending_approval": "bg-gold-100 text-gold-700 dark:bg-gold-900/30 dark:text-gold-400",
        "approved": "bg-kova-100 text-kova-700 dark:bg-kova-900/30 dark:text-kova-400",
        "scheduled": "bg-kova-100 text-kova-700 dark:bg-kova-900/30 dark:text-kova-400",
        "publishing": "bg-gold-100 text-gold-700 dark:bg-gold-900/30 dark:text-gold-400",
        "published": "bg-growth-100 text-growth-700 dark:bg-growth-900/30 dark:text-growth-400",
        "failed": "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
        "rejected": "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
        # Agent action statuses
        "started": "bg-kova-100 text-kova-700 dark:bg-kova-900/30 dark:text-kova-400",
        "completed": "bg-growth-100 text-growth-700 dark:bg-growth-900/30 dark:text-growth-400",
        "needs_approval": "bg-gold-100 text-gold-700 dark:bg-gold-900/30 dark:text-gold-400",
        # Seed statuses
        "new": "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
        "processing": "bg-kova-100 text-kova-700 dark:bg-kova-900/30 dark:text-kova-400",
        # Subscription
        "active": "bg-growth-100 text-growth-700 dark:bg-growth-900/30 dark:text-growth-400",
        "trialing": "bg-kova-100 text-kova-700 dark:bg-kova-900/30 dark:text-kova-400",
        "past_due": "bg-gold-100 text-gold-700 dark:bg-gold-900/30 dark:text-gold-400",
        "canceled": "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
        "none": "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
        # M-Pesa
        "pending": "bg-gold-100 text-gold-700 dark:bg-gold-900/30 dark:text-gold-400",
        "expired": "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
    }
    return colors.get(status, "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300")


@register.filter
def platform_icon(platform):
    """Return SVG icon name for a platform."""
    icons = {
        "twitter": "𝕏",
        "instagram": "📷",
        "facebook": "f",
        "linkedin": "in",
        "tiktok": "♪",
        "youtube": "▶",
        "pinterest": "📌",
        "threads": "@",
        "bluesky": "🦋",
        "whatsapp": "💬",
    }
    return icons.get(platform, "●")


@register.filter
def duration_display(ms):
    """Convert milliseconds to human-readable: 1234 → 1.2s, 65432 → 1m 5s."""
    try:
        ms = int(ms)
    except (TypeError, ValueError):
        return "—"
    if ms < 1000:
        return f"{ms}ms"
    seconds = ms / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    remaining = int(seconds % 60)
    return f"{minutes}m {remaining}s"


@register.filter
def mask_phone(phone):
    """Mask phone number: 254712345678 → 254***5678."""
    if not phone or len(str(phone)) < 8:
        return phone or "—"
    phone = str(phone)
    return f"{phone[:3]}***{phone[-4:]}"


@register.filter
def trend_arrow(current, previous):
    """Return ↑ or ↓ based on comparison."""
    try:
        current, previous = float(current), float(previous)
    except (TypeError, ValueError):
        return ""
    if current > previous:
        return "↑"
    elif current < previous:
        return "↓"
    return "→"


@register.filter
def split_tabs(value):
    """Split 'id:label,id:label' into list of (id, label) tuples for tab nav."""
    return [item.split(":") for item in value.split(",")]
