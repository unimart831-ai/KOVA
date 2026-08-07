"""
Unified DM Inbox — Phase 5.

Consolidates direct messages from Facebook, Instagram, and WhatsApp into a
single fetch/display pipeline. Messages are stored as Interaction objects
with type=DM so they appear in the existing engage inbox alongside comments
and mentions.

Architecture:
  Celery Beat → fetch_all_dms() → per-account provider.get_messages()
  → Interaction(type=DM) → displayed in engage inbox with DM filter

WhatsApp messages are bridged from the existing WhatsApp bot's incoming
webhook rather than polled, so they only need the display adapter.
"""

import logging
from datetime import timedelta

from django.utils import timezone

from apps.messaging.engage.models import Interaction
from apps.core.platforms.models import SocialAccount
from apps.core.platforms.providers.registry import get_provider

logger = logging.getLogger(__name__)

DM_CAPABLE_PLATFORMS = ("facebook", "instagram")


def fetch_dms_for_user(user) -> int:
    """
    Fetch new DMs from all DM-capable connected accounts.
    Returns count of new DM interactions created.
    """
    from django.conf import settings
    if not getattr(settings, "ENGAGE_DM_INBOX_ENABLED", True):
        return 0

    accounts = SocialAccount.objects.filter(
        user=user,
        is_active=True,
        platform__in=DM_CAPABLE_PLATFORMS,
    )

    total_new = 0
    for account in accounts:
        provider = get_provider(account.platform)
        if not provider:
            continue

        token = account.access_token
        if account.platform in ("facebook", "instagram"):
            meta = account.metadata or {}
            pages = meta.get("pages", [])
            if pages:
                selected_id = meta.get("selected_page_id")
                selected_page = (
                    next((p for p in pages if p["id"] == selected_id), None)
                    if selected_id else None
                ) or pages[0]
                token = selected_page.get("access_token", account.access_token)

        try:
            messages = provider.get_messages(access_token=token)
            for msg in messages:
                ext_id = str(msg.get("id", ""))
                if not ext_id:
                    continue

                if Interaction.objects.filter(
                    social_account=account,
                    platform_interaction_id=ext_id,
                ).exists():
                    continue

                Interaction.objects.create(
                    user=user,
                    social_account=account,
                    platform=account.platform,
                    interaction_type=Interaction.InteractionType.DM,
                    author_name=msg.get("sender_name", "Unknown"),
                    author_username=msg.get("sender_id", ""),
                    content=msg.get("text", ""),
                    platform_interaction_id=ext_id,
                )
                total_new += 1

            if messages:
                account.clear_errors()

        except Exception as e:
            logger.warning(
                "Failed to fetch DMs for %s on %s: %s",
                account.username, account.platform, e,
            )

    if total_new > 0:
        logger.info("Fetched %d new DMs for %s", total_new, user.email)

    return total_new


def bridge_whatsapp_message_to_inbox(user, sender_phone: str, sender_name: str,
                                     message_text: str, message_id: str):
    """
    Bridge an incoming WhatsApp message into the unified DM inbox.
    Called from the WhatsApp webhook handler after processing.
    """
    whatsapp_account = SocialAccount.objects.filter(
        user=user, platform="whatsapp", is_active=True,
    ).first()

    if not whatsapp_account:
        return None

    if Interaction.objects.filter(
        social_account=whatsapp_account,
        platform_interaction_id=message_id,
    ).exists():
        return None

    interaction = Interaction.objects.create(
        user=user,
        social_account=whatsapp_account,
        platform="whatsapp",
        interaction_type=Interaction.InteractionType.DM,
        author_name=sender_name or sender_phone,
        author_username=sender_phone,
        content=message_text[:2000],
        platform_interaction_id=message_id,
    )

    logger.debug("Bridged WhatsApp message %s to unified inbox", message_id)
    return interaction


def bridge_messenger_message_to_inbox(
    social_account,
    sender_id: str,
    sender_name: str,
    message_text: str,
    message_id: str,
):
    """
    Bridge a real-time Facebook Messenger DM into the unified inbox.
    Called from the Page webhook handler; polling remains as fallback.
    """
    user = social_account.user

    if Interaction.objects.filter(
        social_account=social_account,
        platform_interaction_id=message_id,
    ).exists():
        return None

    interaction = Interaction.objects.create(
        user=user,
        social_account=social_account,
        platform="facebook",
        interaction_type=Interaction.InteractionType.DM,
        author_name=sender_name or sender_id,
        author_username=sender_id,
        content=(message_text or "")[:2000],
        platform_interaction_id=message_id,
    )

    try:
        from apps.messaging.notifications.realtime import notify_engage_new

        notify_engage_new(interaction)
    except Exception:
        logger.debug("Messenger engage_new notify failed", exc_info=True)

    logger.info(
        "Messenger inbound: %s → page %s [%s]",
        sender_id,
        social_account.username,
        message_id[:12],
    )
    return interaction


def get_dm_threads(user, platform=None, limit=30):
    """
    Get DM threads grouped by sender for the unified inbox view.
    Returns list of thread summaries with latest message and unread count.
    """
    qs = Interaction.objects.filter(
        user=user,
        interaction_type=Interaction.InteractionType.DM,
    ).select_related("social_account")

    if platform:
        qs = qs.filter(platform=platform)

    from django.db.models import Count, Max, Q

    threads = (
        qs.values("author_username", "platform")
        .annotate(
            message_count=Count("id"),
            last_message_at=Max("created_at"),
            unread_count=Count("id", filter=Q(status=Interaction.Status.NEW)),
        )
        .order_by("-last_message_at")[:limit]
    )

    result = []
    for thread in threads:
        latest = qs.filter(
            author_username=thread["author_username"],
            platform=thread["platform"],
        ).first()

        result.append({
            "sender_username": thread["author_username"],
            "sender_name": latest.author_name if latest else "",
            "platform": thread["platform"],
            "last_message": latest.content[:100] if latest else "",
            "last_message_at": thread["last_message_at"],
            "message_count": thread["message_count"],
            "unread_count": thread["unread_count"],
            "platform_icon": _platform_icon(thread["platform"]),
        })

    return result


def _platform_icon(platform: str) -> str:
    icons = {
        "facebook": "fb",
        "instagram": "ig",
        "whatsapp": "wa",
        "twitter": "tw",
    }
    return icons.get(platform, platform[:2])
