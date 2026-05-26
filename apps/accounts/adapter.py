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
        """Auto-verify superuser emails so they skip the verification flow."""
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
    """Send new Google signups into the onboarding funnel."""

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
