"""Subscription access — trial eligibility and paywall checks."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone


def has_completed_payment(user) -> bool:
    """True if the user has ever completed a subscription payment."""
    profile = getattr(user, "profile", None)
    if not profile:
        return False
    if profile.stripe_subscription_id:
        return True
    from apps.core.billing.models import MpesaPayment

    return MpesaPayment.objects.filter(
        user=user, status=MpesaPayment.Status.COMPLETED,
    ).exists()


def can_start_free_trial(user) -> bool:
    """Free trial is available until the first successful subscription payment."""
    return not has_completed_payment(user)


def subscription_allows_app_access(user) -> tuple[bool, str]:
    """
    Return whether the user may use paid app features (agents, content creation).

    Starter-tier access after downgrade is still allowed — this blocks expired
    trials and lapsed paid periods until renewal.
    """
    if not getattr(user, "is_authenticated", False):
        return True, ""

    if getattr(user, "is_staff", False):
        return True, ""

    profile = getattr(user, "profile", None)
    if not profile:
        return True, ""

    now = timezone.now()
    status = profile.subscription_status

    if status == "active":
        if profile.current_period_end and profile.current_period_end < now:
            return False, "Your subscription period has ended. Renew to continue using Kova."
        return True, ""

    if status == "trialing":
        end = profile.trial_ends_at or profile.current_period_end
        if end and end < now:
            return False, "Your free trial has ended. Choose a plan to continue."
        return True, ""

    if status == "past_due":
        if profile.current_period_end and profile.current_period_end < now - timedelta(days=3):
            return False, "Your subscription has expired. Renew to continue."
        return True, ""

    return True, ""


def is_subscription_exempt_url(full_name: str) -> bool:
    """URLs that remain reachable when subscription access is blocked."""
    if not full_name:
        return False
    # django-allauth auth routes (no `accounts:` namespace)
    allauth_exact = {
        "account_logout",
        "account_login",
        "account_signup",
        "account_email",
        "account_confirm_email",
        "account_reset_password",
        "account_reset_password_done",
        "account_reset_password_from_key",
        "account_reset_password_from_key_done",
        "account_change_password",
        "account_set_password",
        "account_inactive",
        "account_reauthenticate",
    }
    if full_name in allauth_exact:
        return True
    exempt_prefixes = (
        "billing:",
        "accounts:",  # app settings, onboarding, phone capture, etc.
        "help:",
    )
    return full_name.startswith(exempt_prefixes)
