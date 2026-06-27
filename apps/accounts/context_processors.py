from django.core.cache import cache
from django.utils import timezone


def nav_badges(request):
    """
    Return badge counts for sidebar navigation items.
    Cached per user for 60 seconds to keep things lightweight.
    """
    if not request.user.is_authenticated:
        return {}

    cache_key = f"nav_badges:{request.user.pk}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    badges = {
        "nav_badge_queue": _count_pending_posts(request.user),
        "nav_badge_inbox": _count_unread_inbox(request.user),
        "nav_badge_leads": _count_new_leads(request.user),
        "nav_badge_whatsapp": _count_unread_whatsapp(request.user),
    }

    cache.set(cache_key, badges, 60)
    return badges


def _count_pending_posts(user):
    try:
        from apps.content.models import Post
        return Post.objects.filter(
            user=user, status=Post.Status.PENDING_APPROVAL
        ).count()
    except Exception:
        return 0


def _count_unread_inbox(user):
    try:
        from apps.engage.models import Interaction
        return Interaction.objects.filter(
            user=user, status=Interaction.Status.NEW
        ).count()
    except Exception:
        return 0


def _count_new_leads(user):
    try:
        from apps.leads.models import Lead
        since = timezone.now() - timezone.timedelta(hours=24)
        return Lead.objects.filter(
            user=user, status=Lead.Status.NEW, first_seen_at__gte=since
        ).count()
    except Exception:
        return 0


def _count_unread_whatsapp(user):
    try:
        from apps.whatsapp.models import WhatsAppConversation
        return WhatsAppConversation.objects.filter(
            social_account__user=user,
            status=WhatsAppConversation.Status.ESCALATED,
        ).count()
    except Exception:
        return 0


def kova_voice(request):
    """Product voice + north-star loop copy for authenticated app templates."""
    if not request.user.is_authenticated:
        return {}
    from apps.accounts.product_voice import kova_voice_for_user

    return kova_voice_for_user(request.user)


def platforms_summary(request):
    """Lightweight connected-platform state for nav nudges."""
    if not request.user.is_authenticated:
        return {}

    cache_key = f"platforms_summary:{request.user.pk}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from apps.platforms.models import SocialAccount

    accounts = SocialAccount.objects.filter(user=request.user).defer(
        "access_token", "refresh_token", "token_scope",
    )
    active_count = accounts.filter(is_active=True).count()
    needs_attention = 0
    for acc in accounts:
        if not acc.is_active:
            needs_attention += 1
        elif acc.needs_reauth:
            needs_attention += 1

    summary = {
        "connected_platform_count": active_count,
        "platforms_need_attention": needs_attention,
    }
    cache.set(cache_key, summary, 60)
    return summary
