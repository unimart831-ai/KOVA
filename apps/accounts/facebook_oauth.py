"""
Facebook signup/login via platform OAuth (full publishing scopes).

Signup and login skip django-allauth's intermediate Facebook page and use the
same OAuth flow as Connected Platforms (`FB_LOGIN_CONFIG_ID` / page scopes).

Meta redirect URIs to whitelist (trailing slash required):
  {SITE_URL}/platforms/callback/facebook/
  {SITE_URL}/platforms/callback/instagram/
  {SITE_URL}/accounts/facebook/login/callback/  — legacy allauth only
"""

from __future__ import annotations

import logging
import secrets
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.shortcuts import redirect
from django.urls import reverse

from apps.platforms.models import SocialAccount
from apps.platforms.providers.registry import get_provider

logger = logging.getLogger(__name__)

FACEBOOK_OAUTH_MODES = frozenset({"signup", "login"})


class FacebookOAuthError(Exception):
    """User-facing Facebook OAuth failure."""


def facebook_oauth_enabled() -> bool:
    return bool(getattr(settings, "FACEBOOK_APP_ID", "") and getattr(settings, "FACEBOOK_APP_SECRET", ""))


def start_facebook_platform_oauth(request, mode: str):
    """Redirect to Meta OAuth with platform publishing scopes."""
    if mode not in FACEBOOK_OAUTH_MODES:
        raise ValueError(f"Invalid Facebook OAuth mode: {mode}")
    if not facebook_oauth_enabled():
        messages.error(request, "Facebook sign-in is not configured yet.")
        return redirect("account_signup" if mode == "signup" else "account_login")

    provider = get_provider("facebook")
    if not provider:
        messages.error(request, "Facebook connection is temporarily unavailable.")
        return redirect("account_signup" if mode == "signup" else "account_login")

    state = secrets.token_urlsafe(32)
    request.session["oauth_state_facebook"] = state
    request.session["oauth_platform"] = "facebook"
    request.session["oauth_facebook_mode"] = mode

    redirect_uri = request.build_absolute_uri(
        reverse("platforms:oauth_callback", kwargs={"platform": "facebook"})
    )
    auth_url = provider.get_auth_url(state=state, redirect_uri=redirect_uri)
    return redirect(auth_url)


def resolve_user_from_facebook_result(result, mode: str):
    """
    Find or create a User from a Facebook platform OAuth result.

    Signup: create user when email is new; link + log in when email exists.
    Login: require an existing account.
    """
    from allauth.account.models import EmailAddress

    email = (result.metadata.get("email") or "").strip().lower()
    if not email:
        raise FacebookOAuthError(
            "Facebook did not share your email address. "
            "Grant the email permission or create an account with email instead."
        )

    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if user:
        if result.display_name and not (user.full_name or "").strip():
            user.full_name = result.display_name
            user.save(update_fields=["full_name"])
        EmailAddress.objects.update_or_create(
            user=user,
            email=email,
            defaults={"verified": True, "primary": True},
        )
        return user, False

    if mode == "login":
        raise FacebookOAuthError(
            "No Kova account found for this Facebook email. "
            "Please start a free trial first."
        )

    user = User.objects.create_user(
        username=uuid.uuid4().hex[:30],
        email=email,
        password=User.objects.make_random_password(length=32),
        full_name=result.display_name or "",
    )
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    return user, True


def login_user_from_facebook_oauth(request, user):
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")


def connect_instagram_from_facebook_pages(user, pages, user_access_token, token_expires_at):
    """Link the first Instagram Business account found on the user's Facebook Pages."""
    import httpx

    from apps.platforms.providers.instagram_facebook import FB_API_BASE, HTTP_TIMEOUT

    if not pages:
        return

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            for page in pages:
                ig_resp = client.get(
                    f"{FB_API_BASE}/{page['id']}",
                    params={
                        "fields": "instagram_business_account",
                        "access_token": page["access_token"],
                    },
                )
                if ig_resp.status_code != 200:
                    continue
                ig_data = ig_resp.json().get("instagram_business_account")
                if not ig_data:
                    continue

                ig_id = ig_data["id"]
                page_token = page["access_token"]

                ig_profile_resp = client.get(
                    f"{FB_API_BASE}/{ig_id}",
                    params={
                        "fields": "id,username,name,profile_picture_url,followers_count,media_count",
                        "access_token": page_token,
                    },
                )
                if ig_profile_resp.status_code != 200:
                    continue
                profile = ig_profile_resp.json()

                SocialAccount.objects.update_or_create(
                    user=user,
                    platform="instagram",
                    platform_user_id=ig_id,
                    defaults={
                        "username": profile.get("username", ""),
                        "display_name": profile.get("name", profile.get("username", "")),
                        "avatar_url": profile.get("profile_picture_url", ""),
                        "access_token": page_token,
                        "refresh_token": "",
                        "token_expires_at": token_expires_at,
                        "token_scope": (
                            "instagram_content_publish,instagram_manage_insights,"
                            "instagram_manage_comments"
                        ),
                        "is_active": True,
                        "last_error": "",
                        "account_type": "business",
                        "metadata": {
                            "ig_business_id": ig_id,
                            "page_id": page["id"],
                            "page_access_token": page_token,
                            "user_access_token": user_access_token,
                            "followers_count": profile.get("followers_count", 0),
                            "media_count": profile.get("media_count", 0),
                            "auto_connected": True,
                        },
                    },
                )
                logger.info(
                    "Facebook OAuth: linked Instagram @%s for %s",
                    profile.get("username"),
                    user.email,
                )
                break
    except Exception as exc:
        logger.warning("Instagram auto-connect failed for %s: %s", user.email, exc)


def persist_facebook_platform_account(user, result, *, auto_connected: bool = False):
    """Store Facebook Page publishing credentials on platforms.SocialAccount."""
    metadata = dict(result.metadata or {})
    if auto_connected:
        metadata["auto_connected"] = True

    account, created = SocialAccount.objects.update_or_create(
        user=user,
        platform="facebook",
        platform_user_id=result.platform_user_id,
        defaults={
            "username": result.username,
            "display_name": result.display_name,
            "avatar_url": result.avatar_url,
            "access_token": result.access_token,
            "refresh_token": result.refresh_token,
            "token_expires_at": result.token_expires_at,
            "token_scope": result.token_scope,
            "is_active": True,
            "last_error": "",
            "account_type": "page",
            "metadata": metadata,
        },
    )
    connect_instagram_from_facebook_pages(
        user,
        metadata.get("pages") or [],
        result.access_token,
        result.token_expires_at,
    )
    return account, created
