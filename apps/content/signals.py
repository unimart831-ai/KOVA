"""
Signals for the content app.

Handles cleanup of orphaned media files when attachments or posts are deleted.
"""

import logging

from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.content.models import MediaAttachment

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=MediaAttachment)
def delete_attachment_file(sender, instance, **kwargs):
    """Delete the actual file from storage when a MediaAttachment is deleted."""
    if instance.file:
        try:
            instance.file.delete(save=False)
        except Exception as exc:
            logger.warning("Failed to delete file for attachment %s: %s", instance.id, exc)
