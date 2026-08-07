"""Recover Facebook/Instagram tokens before deactivation or failed publishes."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

META_PLATFORMS = frozenset({"facebook", "instagram"})


def _apply_page_tokens(account, user_access_token: str) -> bool:
    """Refresh stored page tokens from a valid user access token."""
    from apps.core.platforms.providers.instagram_facebook import refresh_facebook_page_tokens

    pages = refresh_facebook_page_tokens(user_access_token)
    if not pages:
        return False

    meta = dict(account.metadata or {})
    if account.platform == "facebook":
        meta["pages"] = pages
        selected_id = meta.get("selected_page_id")
        if selected_id and not any(p["id"] == selected_id for p in pages):
            meta["selected_page_id"] = pages[0]["id"]
        elif not selected_id:
            meta["selected_page_id"] = pages[0]["id"]
    elif account.platform == "instagram":
        linked_page_id = meta.get("page_id", "")
        for page in pages:
            if page["id"] == linked_page_id:
                meta["page_access_token"] = page["access_token"]
                break
        else:
            meta["page_access_token"] = pages[0]["access_token"]
    account.metadata = meta
    return True


def try_recover_meta_token(account) -> bool:
    """
    Attempt to extend a Facebook/Instagram long-lived token and refresh page tokens.

    On success, clears strike counters and reactivates the account so a transient
    auth failure does not permanently show as "disconnected".
    """
    if account.platform not in META_PLATFORMS:
        return False
    if not account.access_token:
        return False

    from apps.core.platforms.providers.registry import get_provider

    provider = get_provider(account.platform)
    if not provider:
        return False

    try:
        new_tokens = provider.refresh_access_token(account.access_token)
    except Exception as exc:
        logger.warning(
            "Token recovery failed for %s account %s: %s",
            account.platform, account.pk, exc,
        )
        return False

    account.access_token = new_tokens["access_token"]
    if new_tokens.get("expires_at"):
        account.token_expires_at = new_tokens["expires_at"]
    elif new_tokens.get("expires_in"):
        account.token_expires_at = timezone.now() + timedelta(
            seconds=int(new_tokens["expires_in"])
        )

    if not _apply_page_tokens(account, new_tokens["access_token"]):
        logger.warning(
            "Token extended but page tokens missing for %s account %s",
            account.platform, account.pk,
        )
        return False

    meta = dict(account.metadata or {})
    meta["consecutive_errors"] = 0
    meta.pop("last_transient_error", None)
    account.metadata = meta
    account.is_active = True
    account.last_error = ""
    account.save(
        update_fields=[
            "access_token",
            "token_expires_at",
            "metadata",
            "is_active",
            "last_error",
            "updated_at",
        ]
    )
    logger.info(
        "Recovered %s account %s (@%s), active until %s",
        account.platform,
        account.pk,
        account.username,
        account.token_expires_at,
    )
    return True


def refresh_meta_page_tokens(account) -> bool:
    """Refresh page tokens using the current user token (no extension)."""
    if account.platform not in META_PLATFORMS or not account.access_token:
        return False
    if not _apply_page_tokens(account, account.access_token):
        return False
    account.save(update_fields=["metadata", "updated_at"])
    return True
