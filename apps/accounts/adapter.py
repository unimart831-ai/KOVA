"""
Custom allauth adapter — sends all allauth emails (verification, password reset,
etc.) through Celery so they never block the HTTP request/response cycle.

Without this, allauth sends emails synchronously via SMTP during signup,
which can timeout the Gunicorn worker if SMTP is slow or blocked.
"""

from allauth.account.adapter import DefaultAccountAdapter


class AsyncEmailAccountAdapter(DefaultAccountAdapter):
    """
    Override allauth's default adapter to send emails via Celery.

    allauth calls adapter.send_mail() for verification, password reset,
    and password change emails. By default this calls msg.send() synchronously.
    We intercept and route through our Celery email task instead.
    """

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
