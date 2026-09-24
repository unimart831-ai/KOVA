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
        "nav_badge_shares": _count_share_attention(request.user),
        "nav_badge_inbox": _count_unread_inbox(request.user),
        "nav_badge_leads": _count_new_leads(request.user),
        "nav_badge_whatsapp": _count_unread_whatsapp(request.user),
    }

    cache.set(cache_key, badges, 60)
    return badges


def _count_pending_posts(user):
    try:
        from apps.create.content.models import Post
        from apps.create.content.share_bundle import exclude_share_bundle_posts
        from apps.core.accounts.access import get_teammate_ids

        qs = Post.objects.filter(
            user_id__in=get_teammate_ids(user),
            status=Post.Status.PENDING_APPROVAL,
        )
        return exclude_share_bundle_posts(qs, get_teammate_ids(user)).count()
    except Exception:
        return 0


def _count_share_attention(user):
    """Quick Share bundles with pending review or failed posts."""
    try:
        from apps.create.content.models import ContentSeed, Post
        from apps.core.accounts.access import get_teammate_ids

        visible = get_teammate_ids(user)
        seed_ids = list(
            ContentSeed.objects.filter(
                user_id__in=visible,
                blueprint__share_bundle=True,
            ).values_list("id", flat=True)
        )
        if not seed_ids:
            return 0
        return Post.objects.filter(
            seed_id__in=seed_ids,
            status__in=(
                Post.Status.PENDING_APPROVAL,
                Post.Status.DRAFT,
                Post.Status.FAILED,
                Post.Status.BLOCKED,
            ),
        ).values("seed_id").distinct().count()
    except Exception:
        return 0


def _count_unread_inbox(user):
    return 0


def _count_new_leads(user):
    try:
        from apps.commerce.leads.models import Lead
        since = timezone.now() - timezone.timedelta(hours=24)
        return Lead.objects.filter(
            user=user, status=Lead.Status.NEW, first_seen_at__gte=since
        ).count()
    except Exception:
        return 0


def _count_unread_whatsapp(user):
    try:
        from apps.messaging.whatsapp.models import WhatsAppConversation
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
    from apps.core.accounts.product_voice import kova_voice_for_user

    return kova_voice_for_user(request.user)


def platforms_summary(request):
    """Lightweight connected-platform state for nav nudges."""
    if not request.user.is_authenticated:
        return {}

    cache_key = f"platforms_summary:{request.user.pk}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from apps.core.platforms.models import SocialAccount

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
