"""
Signals for the content app.

Handles cleanup of orphaned media files when attachments or posts are deleted.
Also triggers AI image generation for new posts that require visual content.
"""

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.content.models import MediaAttachment, Post

logger = logging.getLogger(__name__)

@receiver(post_delete, sender=MediaAttachment)
def delete_attachment_file(sender, instance, **kwargs):
    """Delete the actual file from storage when a MediaAttachment is deleted."""
    if instance.file:
        try:
            instance.file.delete(save=False)
        except Exception as exc:
            logger.warning("Failed to delete file for attachment %s: %s", instance.id, exc)


@receiver(post_save, sender=Post)
def trigger_carousel_image_generation(sender, instance, created, **kwargs):
    """
    Fire generate_post_images for new carousel posts that have slide-level image prompts.

    Only handles CAROUSEL format — image/story/reel generation is handled by the
    existing async_generate_image path in the Create Agent. Carousel is a new
    format with per-slide prompts that the old path doesn't cover.
    """
    if not created:
        return
    if instance.post_format != Post.PostFormat.CAROUSEL:
        return
    if instance.media_status != Post.MediaStatus.NONE:
        return

    from apps.content.product_visuals import (
        product_has_usable_gallery,
        try_apply_product_polished_media,
    )

    if getattr(instance, "product_id", None) and product_has_usable_gallery(instance.product):
        try_apply_product_polished_media(instance)
        return

    has_slide_prompts = any(
        s.get("image_prompt") for s in (instance.carousel_slides or []) if isinstance(s, dict)
    )
    if not has_slide_prompts:
        return

    try:
        from apps.content.tasks import generate_post_images
        from apps.utils import fire_task
        fire_task(generate_post_images, str(instance.pk))
        logger.info(
            "trigger_carousel_image_generation: queued image gen for carousel post %s",
            instance.pk,
        )
    except Exception as exc:
        logger.warning(
            "trigger_carousel_image_generation: could not queue task for post %s: %s", instance.pk, exc,
        )
