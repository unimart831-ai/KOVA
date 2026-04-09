"""
Celery tasks for the platforms app.

Handles automatic token refresh for connected social accounts,
including Facebook/Instagram long-lived token extension.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="platforms.refresh_expiring_tokens")
def refresh_expiring_tokens():
    """
    Refresh OAuth tokens that will expire within the next 30 minutes.
    Also extends Facebook/Instagram long-lived tokens 14 days before expiry.
    Runs on a schedule via Celery Beat.
    """
    from apps.platforms.models import SocialAccount
    from apps.platforms.providers.registry import get_provider

    threshold = timezone.now() + timedelta(minutes=30)

    # ── Standard refresh (platforms with refresh tokens) ─────────────────
    accounts = SocialAccount.objects.filter(
        is_active=True,
        token_expires_at__isnull=False,
        token_expires_at__lte=threshold,
        refresh_token__gt="",  # must have a refresh token
    )

    refreshed, failed = 0, 0
    for account in accounts:
        provider = get_provider(account.platform)
        if not provider:
            logger.warning("No provider registered for %s", account.platform)
            continue

        try:
            new_tokens = provider.refresh_access_token(account.refresh_token)
            account.access_token = new_tokens["access_token"]
            if new_tokens.get("refresh_token"):
                account.refresh_token = new_tokens["refresh_token"]
            if new_tokens.get("expires_in"):
                account.token_expires_at = timezone.now() + timedelta(
                    seconds=new_tokens["expires_in"]
                )
            account.last_error = ""
            account.save(
                update_fields=[
                    "access_token", "refresh_token",
                    "token_expires_at", "last_error", "updated_at",
                ]
            )
            refreshed += 1
            logger.info("Refreshed token for %s (%s)", account, account.platform)
        except Exception as exc:
            failed += 1
            account.mark_error(f"Token refresh failed: {exc}")
            logger.error("Token refresh failed for %s: %s", account, exc)

    # ── Facebook/Instagram token extension ───────────────────────────────
    # FB long-lived tokens last ~60 days with no refresh token.
    # Extend them 14 days before expiry by exchanging for a new 60-day token.
    fb_threshold = timezone.now() + timedelta(days=14)
    fb_accounts = SocialAccount.objects.filter(
        is_active=True,
        platform__in=["facebook", "instagram"],
        token_expires_at__isnull=False,
        token_expires_at__lte=fb_threshold,
    ).exclude(refresh_token__gt="")  # FB accounts have empty refresh_token

    for account in fb_accounts:
        provider = get_provider(account.platform)
        if not provider:
            continue

        try:
            # Pass the current access_token as the "refresh_token" —
            # Facebook's extend flow uses the live token itself.
            new_tokens = provider.refresh_access_token(account.access_token)
            account.access_token = new_tokens["access_token"]
            if new_tokens.get("expires_in"):
                account.token_expires_at = timezone.now() + timedelta(
                    seconds=new_tokens["expires_in"]
                )
            # Re-fetch page tokens (they inherit from the new user token)
            _refresh_page_tokens(account, new_tokens["access_token"])
            account.last_error = ""
            account.save(
                update_fields=[
                    "access_token", "token_expires_at",
                    "last_error", "metadata", "updated_at",
                ]
            )
            refreshed += 1
            logger.info(
                "Extended FB/IG token for %s (%s), new expiry: %s",
                account, account.platform, account.token_expires_at,
            )
        except Exception as exc:
            failed += 1
            logger.error("FB token extension failed for %s: %s", account, exc)
            # Don't mark_error here — the token may still be valid.
            # Instead, notify the user to reconnect if expiry is imminent.
            _notify_token_expiring(account, exc)

    if refreshed or failed:
        logger.info(
            "Token refresh complete: %d refreshed, %d failed",
            refreshed, failed,
        )
    return {"refreshed": refreshed, "failed": failed}


def _refresh_page_tokens(account, user_access_token):
    """Re-fetch Facebook Page tokens after extending the user token."""
    import httpx

    FB_API_BASE = f"https://graph.facebook.com/v25.0"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(f"{FB_API_BASE}/me/accounts", params={
                "fields": "id,name,access_token,picture",
                "access_token": user_access_token,
            })
            resp.raise_for_status()
            pages = resp.json().get("data", [])
            if pages:
                metadata = account.metadata or {}
                metadata["pages"] = [
                    {
                        "id": p["id"],
                        "name": p["name"],
                        "access_token": p["access_token"],
                        "picture_url": p.get("picture", {}).get("data", {}).get("url", ""),
                    }
                    for p in pages
                ]
                account.metadata = metadata
                logger.info("Refreshed %d page tokens for %s", len(pages), account)
    except Exception as exc:
        logger.warning("Could not refresh page tokens for %s: %s", account, exc)


def _notify_token_expiring(account, error):
    """Create a notification warning the user their token is about to expire."""
    try:
        from apps.notifications.models import Notification

        days_left = 0
        if account.token_expires_at:
            delta = account.token_expires_at - timezone.now()
            days_left = max(0, delta.days)

        platform_name = account.get_platform_display()
        Notification.create_for_user(
            user=account.user,
            notification_type=Notification.NotificationType.SYSTEM,
            message=(
                f"⚠️ Your {platform_name} account (@{account.username}) token "
                f"expires in {days_left} days. Please reconnect to avoid disruption. "
                f"Go to Platforms → Reconnect."
            ),
        )
    except Exception:
        logger.warning("Could not create token expiry notification for %s", account)
