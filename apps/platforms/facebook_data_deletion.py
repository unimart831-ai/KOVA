"""
Meta (Facebook) user data deletion — signed_request callback and data purge.

https://developers.facebook.com/docs/development/create-an-app/app-dashboard/data-deletion-callback
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from apps.accounts.facebook_oauth import find_user_by_facebook_id
from apps.platforms.models import SocialAccount

logger = logging.getLogger(__name__)

CACHE_PREFIX = "fb_data_deletion:"
CACHE_TTL_SECONDS = 90 * 24 * 3600  # 90 days — matches privacy retention note


class SignedRequestError(ValueError):
    """Invalid or unverifiable Meta signed_request payload."""


def _base64_url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def parse_signed_request(signed_request: str, app_secret: str) -> dict[str, Any]:
    """Verify and decode Meta's signed_request (Facebook Login data deletion)."""
    if not signed_request or not app_secret:
        raise SignedRequestError("Missing signed_request or app secret")

    try:
        encoded_sig, payload = signed_request.split(".", 1)
    except ValueError as exc:
        raise SignedRequestError("Malformed signed_request") from exc

    sig = _base64_url_decode(encoded_sig)
    expected_sig = hmac.new(
        app_secret.encode("utf-8"),
        payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(sig, expected_sig):
        raise SignedRequestError("Invalid signed_request signature")

    try:
        data = json.loads(_base64_url_decode(payload))
    except (json.JSONDecodeError, ValueError) as exc:
        raise SignedRequestError("Invalid signed_request payload") from exc

    if not isinstance(data, dict):
        raise SignedRequestError("signed_request payload must be an object")
    return data


def _scrub_account_pii(account: SocialAccount) -> None:
    """Clear OAuth secrets and identifiable metadata; keep record for linked content."""
    meta = dict(account.metadata or {})
    for key in (
        "email",
        "phone",
        "facebook_user_id",
        "pages",
        "page_access_token",
        "user_access_token",
        "selected_page_id",
    ):
        meta.pop(key, None)
    meta["meta_data_deletion_at"] = timezone.now().isoformat()
    account.access_token = ""
    account.refresh_token = ""
    account.token_expires_at = None
    account.token_scope = ""
    account.avatar_url = ""
    account.is_active = False
    account.last_error = "Removed per Meta data deletion request"
    account.metadata = meta
    account.save(
        update_fields=[
            "access_token",
            "refresh_token",
            "token_expires_at",
            "token_scope",
            "avatar_url",
            "is_active",
            "last_error",
            "metadata",
            "updated_at",
        ]
    )


def _clear_profile_facebook_id(user, facebook_user_id: str) -> None:
    profile = getattr(user, "profile", None)
    if not profile:
        return
    steps = dict(profile.onboarding_step_timestamps or {})
    if steps.get("facebook_user_id") != facebook_user_id:
        return
    steps.pop("facebook_user_id", None)
    profile.onboarding_step_timestamps = steps
    profile.save(update_fields=["onboarding_step_timestamps", "updated_at"])


def _delete_allauth_facebook_link(facebook_user_id: str) -> int:
    try:
        from allauth.socialaccount.models import SocialAccount as AllauthSocialAccount
    except ImportError:
        return 0
    deleted, _ = AllauthSocialAccount.objects.filter(
        provider="facebook",
        uid=facebook_user_id,
    ).delete()
    return deleted


def delete_facebook_user_data(facebook_user_id: str) -> dict[str, int]:
    """
    Remove Facebook-sourced data for a Meta user id.

    Does not delete the Kova user account — only platform tokens, Graph metadata,
    and Facebook login links. Full account erasure remains via support@kovaagent.com.
    """
    facebook_user_id = str(facebook_user_id or "").strip()
    if not facebook_user_id:
        return {"facebook_accounts": 0, "instagram_accounts": 0, "users_touched": 0, "allauth_removed": 0}

    facebook_qs = SocialAccount.objects.filter(
        Q(platform="facebook", platform_user_id=facebook_user_id)
        | Q(platform="facebook", metadata__facebook_user_id=facebook_user_id)
    )
    user_ids = set(facebook_qs.values_list("user_id", flat=True))

    user = find_user_by_facebook_id(facebook_user_id)
    if user:
        user_ids.add(user.pk)

    counts = {
        "facebook_accounts": 0,
        "instagram_accounts": 0,
        "users_touched": len(user_ids),
        "allauth_removed": _delete_allauth_facebook_link(facebook_user_id),
    }

    for account in facebook_qs:
        _scrub_account_pii(account)
        counts["facebook_accounts"] += 1

    if user_ids:
        ig_qs = SocialAccount.objects.filter(
            user_id__in=user_ids,
            platform="instagram",
            is_active=True,
        )
        for account in ig_qs:
            _scrub_account_pii(account)
            counts["instagram_accounts"] += 1

    if user:
        _clear_profile_facebook_id(user, facebook_user_id)

    logger.info(
        "Meta data deletion completed facebook_user_id=%s counts=%s",
        facebook_user_id,
        counts,
    )
    return counts


def make_confirmation_code() -> str:
    return secrets.token_urlsafe(24)[:32]


def store_deletion_status(
    confirmation_code: str,
    *,
    facebook_user_id: str,
    counts: dict[str, int],
) -> None:
    cache.set(
        f"{CACHE_PREFIX}{confirmation_code}",
        {
            "facebook_user_id": facebook_user_id,
            "status": "completed",
            "completed_at": timezone.now().isoformat(),
            "counts": counts,
        },
        CACHE_TTL_SECONDS,
    )


def get_deletion_status(confirmation_code: str) -> dict[str, Any] | None:
    return cache.get(f"{CACHE_PREFIX}{confirmation_code}")


def status_page_url(confirmation_code: str) -> str:
    base = getattr(settings, "SITE_URL", "http://localhost:8000").rstrip("/")
    return f"{base}/legal/facebook-data-deletion/status/{confirmation_code}/"
