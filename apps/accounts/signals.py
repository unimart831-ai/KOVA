from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify

from apps.accounts.models import User, UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create a UserProfile when a new User is created."""
    if created:
        slug = _unique_page_slug(instance.username)
        UserProfile.objects.create(user=instance, page_slug=slug)
        # NOTE: Welcome email is sent after onboarding completes (in views.py),
        # not here, so the user has their brand set up when they receive it.


def _unique_page_slug(base: str) -> str:
    """Return a unique page_slug derived from a username."""
    slug = slugify(base)[:60] or "page"
    candidate = slug
    n = 1
    while UserProfile.objects.filter(page_slug=candidate).exists():
        candidate = f"{slug}-{n}"
        n += 1
    return candidate
