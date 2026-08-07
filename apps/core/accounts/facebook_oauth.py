"""
Facebook signup/login via platform OAuth (full publishing scopes).

Signup and login skip django-allauth's intermediate Facebook page and use the
same OAuth flow as Connected Platforms (`FB_LOGIN_CONFIG_ID` / page scopes).

Meta redirect URIs to whitelist (trailing slash required):
  {SITE_URL}/platforms/callback/facebook/
  {SITE_URL}/platforms/callback/instagram/
  {SITE_URL}/accounts/facebook/login/callback/  — legacy allauth only

Facebook Graph rarely returns a phone number on the User object (standard
``email`` + ``public_profile`` permissions). When email is missing we create
``fb_{facebook_id}@kova.page`` (same pattern as WhatsApp ``wa_{id}@kova.page``)
and send the user to phone capture when Graph did not supply a number.
"""

from __future__ import annotations

import logging
import secrets
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.shortcuts import redirect
from django.urls import reverse

from apps.core.platforms.models import SocialAccount
from apps.core.platforms.providers.registry import get_provider

logger = logging.getLogger(__name__)

FACEBOOK_OAUTH_MODES = frozenset({"signup", "login"})
_FB_OAUTH_SIGNER = TimestampSigner(salt="kova.facebook.oauth.v1")
_FB_OAUTH_STATE_MAX_AGE = 900  # 15 minutes


class FacebookOAuthError(Exception):
    """User-facing Facebook OAuth failure."""


def make_facebook_oauth_state(mode: str) -> tuple[str, str]:
    """Return (session_nonce, signed_state) for Meta OAuth."""
    nonce = secrets.token_urlsafe(32)
    return nonce, sign_facebook_oauth_state(nonce, mode)


def sign_facebook_oauth_state(nonce: str, mode: str) -> str:
    """Build the state query param sent to Meta."""
    return _FB_OAUTH_SIGNER.sign(f"{nonce}:{mode}")


def peek_facebook_oauth_mode(state_param: str) -> str | None:
    """Read signup/login mode from a signed state without consuming the session."""
    if not state_param:
        return None
    try:
        payload = _FB_OAUTH_SIGNER.unsign(state_param, max_age=_FB_OAUTH_STATE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    parts = payload.split(":", 1)
    if len(parts) == 2 and parts[1] in FACEBOOK_OAUTH_MODES:
        return parts[1]
    return None


def validate_facebook_callback_state(request, received_state: str) -> tuple[str | None, str | None]:
    """
    Validate Facebook OAuth state on callback.

    Returns (facebook_auth_mode, error_message). error_message is user-facing.
    Supports signed state (signup/login) and legacy plain state (platform connect).
    """
    if not received_state:
        return None, "Invalid OAuth state. Please try again."

    try:
        payload = _FB_OAUTH_SIGNER.unsign(received_state, max_age=_FB_OAUTH_STATE_MAX_AGE)
        nonce, mode = payload.split(":", 1)
        if mode not in FACEBOOK_OAUTH_MODES:
            return None, "Invalid OAuth state. Please try again."
        expected_nonce = request.session.pop("oauth_state_facebook", None)
        if expected_nonce and expected_nonce != nonce:
            logger.warning(
                "Facebook OAuth state nonce mismatch (session=%s, signed=%s)",
                bool(expected_nonce),
                True,
            )
            return None, "Invalid OAuth state. Please try again."
        request.session.pop("oauth_facebook_mode", None)
        return mode, None
    except SignatureExpired:
        return None, "Facebook sign-in timed out. Please try again."
    except BadSignature:
        pass

    expected_state = request.session.pop("oauth_state_facebook", None)
    if expected_state and expected_state == received_state:
        return request.session.pop("oauth_facebook_mode", None), None
    return None, "Invalid OAuth state. Please try again."


def redirect_facebook_oauth_failure(request, mode: str | None):
    """Redirect to signup or login with django messages preserved."""
    if mode == "login":
        return redirect("account_login")
    if mode == "signup":
        return redirect("account_signup")
    return redirect("account_login")


def log_facebook_oauth_callback(
    *,
    mode: str | None,
    success: bool,
    user_id: int | None = None,
    email_present: bool | None = None,
    accounts_connected: int | None = None,
    error: str | None = None,
):
    """Structured callback logging — no tokens or secrets."""
    extra = {
        "mode": mode or "",
        "success": success,
        "user_id": user_id,
        "email_present": email_present,
        "accounts_connected": accounts_connected,
    }
    msg = "Facebook OAuth callback"
    if error:
        extra["error"] = error[:200]
    if success:
        logger.info("%s: %s", msg, extra)
    else:
        logger.error("%s: %s", msg, extra)


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

    nonce, state = make_facebook_oauth_state(mode)
    request.session["oauth_state_facebook"] = nonce
    request.session["oauth_platform"] = "facebook"
    request.session["oauth_facebook_mode"] = mode
    request.session.modified = True

    redirect_uri = request.build_absolute_uri(
        reverse("platforms:oauth_callback", kwargs={"platform": "facebook"})
    )
    auth_url = provider.get_auth_url(
        state=state,
        redirect_uri=redirect_uri,
        for_user_identity=True,
    )
    return redirect(auth_url)


def facebook_synthetic_email(facebook_id: str) -> str:
    """Placeholder email when Facebook does not share an address (cf. wa_{id}@kova.page)."""
    clean = "".join(ch for ch in str(facebook_id) if ch.isalnum()) or str(facebook_id)
    return f"fb_{clean}@kova.page"


def is_facebook_synthetic_email(email: str) -> bool:
    email = (email or "").strip().lower()
    return email.startswith("fb_") and email.endswith("@kova.page")


def find_user_by_facebook_id(facebook_id: str):
    """Match an existing user by Facebook user id (SocialAccount or synthetic email)."""
    if not facebook_id:
        return None

    User = get_user_model()
    account = (
        SocialAccount.objects.filter(
            platform="facebook",
            platform_user_id=facebook_id,
        )
        .select_related("user")
        .order_by("-is_active", "-updated_at")
        .first()
    )
    if account:
        return account.user
    return User.objects.filter(
        email__iexact=facebook_synthetic_email(facebook_id),
    ).first()


def _extract_facebook_phone(result) -> str:
    """Normalize phone from OAuth metadata (not from Graph /me)."""
    from apps.core.accounts.phone_utils import is_valid_phone, normalize_phone

    metadata = result.metadata or {}
    raw = (metadata.get("phone") or metadata.get("mobile_phone") or "").strip()
    if not raw:
        return ""
    phone = normalize_phone(raw)
    return phone if is_valid_phone(phone) else ""


def _sync_verified_email_address(user, email: str):
    """Create/update allauth EmailAddress for real (non-synthetic) emails."""
    if not email or is_facebook_synthetic_email(email):
        return
    from allauth.account.models import EmailAddress

    EmailAddress.objects.update_or_create(
        user=user,
        email=email,
        defaults={"verified": True, "primary": True},
    )


def _apply_facebook_profile_updates(user, result, *, email: str, phone: str):
    """Refresh name, email record, and phone from a Facebook OAuth result."""
    from apps.core.accounts.phone_utils import apply_phone_to_user

    updates = []
    if result.display_name and not (user.full_name or "").strip():
        user.full_name = result.display_name
        updates.append("full_name")
    if updates:
        user.save(update_fields=updates)
    if email:
        _sync_verified_email_address(user, email)
    if phone and not (getattr(user, "phone_number", "") or "").strip():
        apply_phone_to_user(user, phone)


def _store_facebook_id_on_profile(user, facebook_id: str):
    """Persist facebook_user_id on UserProfile onboarding metadata for support/debug."""
    profile = getattr(user, "profile", None)
    if profile is None or not facebook_id:
        return
    steps = dict(profile.onboarding_step_timestamps or {})
    if steps.get("facebook_user_id") == facebook_id:
        return
    steps["facebook_user_id"] = facebook_id
    profile.onboarding_step_timestamps = steps
    profile.save(update_fields=["onboarding_step_timestamps", "updated_at"])


def resolve_user_from_facebook_result(result, mode: str):
    """
    Find or create a User from a Facebook platform OAuth result.

    Signup: create when new; link + log in when email or facebook_id matches.
    Login: match by facebook_id (SocialAccount / synthetic email) or email.
    No email: synthetic ``fb_{id}@kova.page``; phone from Graph when present,
    otherwise caller redirects to phone capture after OAuth succeeds.
    """
    from allauth.account.models import EmailAddress

    facebook_id = str(result.platform_user_id or "").strip()
    if not facebook_id:
        raise FacebookOAuthError(
            "Could not identify your Facebook account. Please try again."
        )

    metadata = result.metadata or {}
    email = (metadata.get("email") or "").strip().lower()
    phone = _extract_facebook_phone(result)

    User = get_user_model()
    user = None
    if email:
        user = User.objects.filter(email__iexact=email).first()
    if not user:
        user = find_user_by_facebook_id(facebook_id)

    if user:
        _apply_facebook_profile_updates(user, result, email=email, phone=phone)
        _store_facebook_id_on_profile(user, facebook_id)
        return user, False

    if mode == "login":
        raise FacebookOAuthError(
            "No Kova account found for this Facebook account. "
            "Please start a free trial first."
        )

    create_email = email or facebook_synthetic_email(facebook_id)
    user = User.objects.create_user(
        username=uuid.uuid4().hex[:30],
        email=create_email,
        password=User.objects.make_random_password(length=32),
        full_name=result.display_name or "",
    )
    if email:
        EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    if phone:
        from apps.core.accounts.phone_utils import apply_phone_to_user

        apply_phone_to_user(user, phone)
    _store_facebook_id_on_profile(user, facebook_id)
    return user, True


def login_user_from_facebook_oauth(request, user):
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")


def connect_instagram_from_facebook_pages(user, pages, user_access_token, token_expires_at):
    """Link the first Instagram Business account found on the user's Facebook Pages."""
    import httpx

    from apps.core.platforms.providers.instagram_facebook import FB_API_BASE, HTTP_TIMEOUT

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
    if result.platform_user_id:
        metadata["facebook_user_id"] = str(result.platform_user_id)
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
    connected = SocialAccount.objects.filter(
        user=user, platform__in=("facebook", "instagram"), is_active=True,
    ).count()
    logger.info(
        "Facebook OAuth persist: user_id=%s email_present=%s accounts_connected=%s created=%s",
        user.pk,
        bool((result.metadata or {}).get("email")),
        connected,
        created,
    )
    return account, created
