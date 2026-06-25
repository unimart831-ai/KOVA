from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import User, UserProfile
from apps.accounts.profile_utils import _unique_page_slug


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create a UserProfile when a new User is created."""
    if created:
        slug = _unique_page_slug(instance.username or instance.email or "user")
        UserProfile.objects.create(user=instance, page_slug=slug)
        # NOTE: Welcome email is sent after onboarding completes (in views.py),
        # not here, so the user has their brand set up when they receive it.


# ─── Social sign-up: auto-connect publishing accounts ────────────────────────
from allauth.socialaccount.signals import social_account_added, social_account_updated


@receiver(social_account_added)
def auto_connect_on_social_signup(sender, request, sociallogin, **kwargs):
    """When a new Facebook social account is added, auto-connect publishing platforms."""
    if sociallogin.account.provider == "facebook":
        from apps.accounts.adapter import _auto_connect_facebook_platforms
        _auto_connect_facebook_platforms(sociallogin)


@receiver(social_account_updated)
def auto_connect_on_social_update(sender, request, sociallogin, **kwargs):
    """When a Facebook social token is refreshed, sync to publishing platforms."""
    if sociallogin.account.provider == "facebook":
        from apps.accounts.adapter import _auto_connect_facebook_platforms
        _auto_connect_facebook_platforms(sociallogin)
