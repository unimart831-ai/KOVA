"""
Celery tasks for the platforms app.

Handles automatic token refresh for connected social accounts.
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
    Runs on a schedule via Celery Beat.
    """
    from apps.platforms.models import SocialAccount
    from apps.platforms.providers.registry import get_provider

    threshold = timezone.now() + timedelta(minutes=30)
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

    if refreshed or failed:
        logger.info(
            "Token refresh complete: %d refreshed, %d failed",
            refreshed, failed,
        )
    return {"refreshed": refreshed, "failed": failed}
