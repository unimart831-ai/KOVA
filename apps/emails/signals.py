import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="leads.Lead")
def sync_lead_to_subscriber(sender, instance, **kwargs):
    """Every lead with an email becomes an email subscriber automatically."""
    if not instance.email:
        return
    try:
        from apps.emails.subscriber_sync import sync_lead

        sync_lead(instance)
    except Exception:
        logger.exception("Failed to sync lead %s to email subscriber", instance.pk)
