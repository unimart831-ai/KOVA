"""
Custom allauth adapter — sends all allauth emails (verification, password reset,
etc.) through Celery so they never block the HTTP request/response cycle.

Without this, allauth sends emails synchronously via SMTP during signup,
which can timeout the Gunicorn worker if SMTP is slow or blocked.
"""

import uuid

from allauth.account.adapter import DefaultAccountAdapter


class AsyncEmailAccountAdapter(DefaultAccountAdapter):
    """
    Override allauth's default adapter to send emails via Celery.

    allauth calls adapter.send_mail() for verification, password reset,
    and password change emails. By default this calls msg.send() synchronously.
    We intercept and route through our Celery email task instead.
    """

    def populate_username(self, request, user):
        """Generate a unique username since we use email-only login."""
        user.username = uuid.uuid4().hex[:30]

    def save_user(self, request, user, form, commit=True):
        """Free the email constraint for any soft-deleted users before saving.

        If a previous user was soft-deleted via queryset.delete() (e.g. Django
        admin's 'Delete selected' action), the email may not have been mangled.
        This causes a DB-level UniqueViolation when allauth tries to INSERT the
        new user. We fix this by mangling those orphaned emails first.
        """
        from django.utils import timezone as tz
        from apps.accounts.models import User

        email = form.cleaned_data.get("email", "")
        if email:
            stale = User.all_objects.filter(email__iexact=email, is_deleted=True)
            for u in stale:
                stamp = int(tz.now().timestamp())
                u.email = f"deleted_{stamp}_{u.pk}@deleted.local"
                u.username = f"deleted_{stamp}_{u.pk}"
                u.save(update_fields=["email", "username"])
        return super().save_user(request, user, form, commit)

    def is_email_verified(self, request, email):
        """Skip verification gate when email verification is disabled."""
        from django.conf import settings

        if getattr(settings, "ACCOUNT_EMAIL_VERIFICATION", "mandatory") == "none":
            return True

        from apps.accounts.models import User

        try:
            user = User.objects.get(email=email)
            if user.is_superuser:
                return True
        except User.DoesNotExist:
            pass
        return super().is_email_verified(request, email)

    def send_mail(self, template_prefix, email, context):
        """
        Send allauth emails asynchronously via Celery.

        Args:
            template_prefix: e.g. "account/email/email_confirmation"
            email: recipient email address
            context: template context dict from allauth
        """
        from apps.emails.tasks import send_allauth_email

        # Extract only serializable context (User objects can't go through Celery)
        safe_context = {}
        for key, value in context.items():
            if key == "user":
                safe_context["user_email"] = str(value.email)
                safe_context["user_first_name"] = value.first_name or ""
            elif key == "current_site":
                safe_context["current_site_name"] = str(value.name)
                safe_context["current_site_domain"] = str(value.domain)
            elif isinstance(value, (str, int, float, bool, type(None))):
                safe_context[key] = value
            else:
                # Convert non-serializable objects to strings
                safe_context[key] = str(value)

        send_allauth_email.delay(template_prefix, email, safe_context)


from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class KovaSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Send social signups into the onboarding funnel and auto-connect platforms."""

    def get_signup_redirect_url(self, request, sociallogin):
        user = sociallogin.user
        if user and not (getattr(user, "phone_number", "") or "").strip():
            return "/accounts/onboarding/phone/"
        return "/accounts/onboarding/start/"

    def get_login_redirect_url(self, request):
        user = request.user
        if user.is_authenticated and not user.onboarding_completed:
            if not (getattr(user, "phone_number", "") or "").strip():
                return "/accounts/onboarding/phone/"
            return "/accounts/onboarding/start/"
        return super().get_login_redirect_url(request)

    def pre_social_login(self, request, sociallogin):
        """Auto-connect publishing accounts when user logs in via Facebook."""
        super().pre_social_login(request, sociallogin)
        # For returning users (already have a pk), run auto-connect immediately.
        # For new sign-ups, we use the social_account_added signal instead.
        if (
            sociallogin.account.provider == "facebook"
            and sociallogin.user
            and sociallogin.user.pk
        ):
            _auto_connect_facebook_platforms(sociallogin)


def _auto_connect_facebook_platforms(sociallogin):
    """
    Create platforms.SocialAccount entries for Facebook Page and Instagram
    from the allauth Facebook social login token.

    This gives users immediate publishing capability without a second OAuth flow.
    """
    import logging
    import httpx
    from datetime import datetime, timedelta, timezone

    from apps.platforms.models import SocialAccount

    logger = logging.getLogger(__name__)
    user = sociallogin.user
    if not user or not user.pk:
        return

    token_obj = sociallogin.token
    if not token_obj or not token_obj.token:
        return

    access_token = token_obj.token
    FB_API_BASE = "https://graph.facebook.com/v25.0"

    try:
        with httpx.Client(timeout=30.0) as client:
            # Extend to long-lived token
            from django.conf import settings
            ll_resp = client.get(f"{FB_API_BASE}/oauth/access_token", params={
                "grant_type": "fb_exchange_token",
                "client_id": settings.FACEBOOK_APP_ID,
                "client_secret": settings.FACEBOOK_APP_SECRET,
                "fb_exchange_token": access_token,
            })
            if ll_resp.status_code == 200:
                ll_data = ll_resp.json()
                access_token = ll_data.get("access_token", access_token)
                expires_in = ll_data.get("expires_in", 5184000)
            else:
                expires_in = 5184000

            token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            # Fetch user's Pages
            pages_resp = client.get(f"{FB_API_BASE}/me/accounts", params={
                "fields": "id,name,access_token,picture",
                "access_token": access_token,
            })
            if pages_resp.status_code != 200:
                logger.warning("Facebook auto-connect: /me/accounts failed: %s", pages_resp.text[:200])
                return

            pages = pages_resp.json().get("data", [])
            if not pages:
                logger.info("Facebook auto-connect: user %s has no Pages", user.email)
                return

            # Connect Facebook Page
            fb_pages_meta = [
                {"id": p["id"], "name": p["name"], "access_token": p["access_token"]}
                for p in pages
            ]
            SocialAccount.objects.update_or_create(
                user=user,
                platform="facebook",
                platform_user_id=sociallogin.account.uid,
                defaults={
                    "username": sociallogin.account.extra_data.get("name", ""),
                    "display_name": sociallogin.account.extra_data.get("name", ""),
                    "avatar_url": (
                        sociallogin.account.extra_data.get("picture", {}).get("data", {}).get("url", "")
                        if isinstance(sociallogin.account.extra_data.get("picture"), dict)
                        else ""
                    ),
                    "access_token": access_token,
                    "refresh_token": "",
                    "token_expires_at": token_expires_at,
                    "token_scope": "pages_manage_posts,pages_read_engagement",
                    "is_active": True,
                    "last_error": "",
                    "account_type": "page",
                    "metadata": {
                        "pages": fb_pages_meta,
                        "selected_page_id": pages[0]["id"],
                        "auto_connected": True,
                    },
                },
            )
            logger.info("Facebook auto-connect: created FB Page account for %s", user.email)

            # Find Instagram Business Account linked to a Page
            for page in pages:
                ig_resp = client.get(f"{FB_API_BASE}/{page['id']}", params={
                    "fields": "instagram_business_account",
                    "access_token": page["access_token"],
                })
                if ig_resp.status_code != 200:
                    continue
                ig_data = ig_resp.json().get("instagram_business_account")
                if not ig_data:
                    continue

                ig_id = ig_data["id"]
                page_token = page["access_token"]

                # Fetch IG profile
                ig_profile_resp = client.get(f"{FB_API_BASE}/{ig_id}", params={
                    "fields": "id,username,name,profile_picture_url,followers_count,media_count",
                    "access_token": page_token,
                })
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
                        "token_scope": "instagram_content_publish,instagram_manage_insights,instagram_manage_comments",
                        "is_active": True,
                        "last_error": "",
                        "account_type": "business",
                        "metadata": {
                            "ig_business_id": ig_id,
                            "page_id": page["id"],
                            "page_access_token": page_token,
                            "user_access_token": access_token,
                            "followers_count": profile.get("followers_count", 0),
                            "media_count": profile.get("media_count", 0),
                            "auto_connected": True,
                        },
                    },
                )
                logger.info(
                    "Facebook auto-connect: created IG account @%s for %s",
                    profile.get("username"), user.email,
                )
                break  # Only connect the first IG account found

    except Exception as exc:
        logger.warning("Facebook auto-connect failed for %s: %s", user.email, exc)
