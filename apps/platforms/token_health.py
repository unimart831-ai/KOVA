"""Platform token health — Stage 2 resilience for approve/publish gates."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.platforms.models import SocialAccount


def account_token_expiring_within(account: SocialAccount, *, hours: int = 24) -> bool:
    if not account or not account.is_active:
        return False
    if not account.token_expires_at:
        return False
    if account.is_token_expired:
        return True
    return account.token_expires_at <= timezone.now() + timedelta(hours=hours)


def get_post_token_block(post) -> dict | None:
    """Return block info if post's platform token expires within 24h."""
    account = getattr(post, "social_account", None)
    if not account or account.platform == "whatsapp":
        return None
    if not account_token_expiring_within(account, hours=24):
        return None
    platform_name = account.get_platform_display()
    return {
        "platform": account.platform,
        "platform_name": platform_name,
        "username": account.username,
        "expires_at": account.token_expires_at,
        "message": (
            f"Your {platform_name} connection (@{account.username}) expires soon. "
            "Reconnect before approving new posts."
        ),
        "reconnect_url_name": "platforms:list",
    }


def get_user_expiring_accounts(user, *, hours: int = 24) -> list[SocialAccount]:
    threshold = timezone.now() + timedelta(hours=hours)
    return list(
        SocialAccount.objects.filter(
            user=user,
            is_active=True,
            token_expires_at__isnull=False,
            token_expires_at__lte=threshold,
        ).order_by("token_expires_at")
    )
