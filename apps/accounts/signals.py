from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import User, UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create a UserProfile when a new User is created."""
    if created:
        UserProfile.objects.create(user=instance)
        # NOTE: Welcome email is sent after onboarding completes (in views.py),
        # not here, so the user has their brand set up when they receive it.
