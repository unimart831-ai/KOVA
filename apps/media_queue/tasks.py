"""
Celery tasks for the Media Queue.

Handles periodic queue processing — finds items due for publishing,
creates Post objects, and hands off to the existing publish pipeline.
"""

import logging

from celery import shared_task
from django.utils import timezone as dj_tz

logger = logging.getLogger(__name__)


@shared_task(name="media_queue.process_queues", soft_time_limit=120, time_limit=150)
def process_media_queues():
    """
    Periodic task: find all active queues with due items and publish them.

    Designed to run every 5 minutes via Celery Beat. For each queue, pops
    the next due item, creates a Post, and triggers the publish task.
    """
    from apps.content.models import Post, MediaAttachment
    from apps.content.tasks import publish_post
    from apps.notifications.models import Notification
    from apps.media_queue.models import MediaQueue, QueueItem
    from apps.media_queue.scheduling import recalculate_schedule

    now = dj_tz.now()

    due_items = (
        QueueItem.objects
        .filter(
            queue__is_active=True,
            status=QueueItem.Status.QUEUED,
            scheduled_for__lte=now,
        )
        .select_related("queue", "queue__user", "queue__social_account")
        .order_by("scheduled_for")
    )

    published_count = 0
    for item in due_items:
        queue = item.queue
        account = queue.social_account

        # ── Plan enforcement: check post limit before publishing ──────
        from apps.billing.enforcement import check_post_limit
        allowed, msg = check_post_limit(queue.user)
        if not allowed:
            logger.info("Media Queue skipping item %s: %s", item.pk, msg)
            continue

        # ── Emergency pause — halt all autonomous media publishing ────
        profile = getattr(queue.user, "profile", None)
        if profile and profile.emergency_pause:
            logger.info("EMERGENCY PAUSE: Media Queue skipping item %s for %s", item.pk, queue.user.email)
            continue

        try:
            item.status = QueueItem.Status.PUBLISHING
            item.save(update_fields=["status", "updated_at"])

            # AI caption generation — if user didn't write one
            caption = item.caption or ""
            if not caption.strip():
                caption = _generate_ai_caption(queue.user, account.platform, queue.name)

            # Create a Post so the existing publish pipeline handles it
            post = Post.objects.create(
                user=queue.user,
                social_account=account,
                platform=account.platform,
                content_text=caption,
                content_type="original",
                status=Post.Status.APPROVED,
                media_status=Post.MediaStatus.UPLOADED,
                generated_by_agent="media_queue",
            )

            # Attach the image as a MediaAttachment
            image_field = item.image_cropped if item.image_cropped else item.image
            attachment = MediaAttachment.objects.create(
                post=post,
                file=image_field,
                file_type="image",
                alt_text=item.caption[:500] if item.caption else "",
                order=0,
            )

            # publish_post reads attachment bytes from storage directly,
            # so we no longer need to set media_urls here.
            post.scheduled_at = now
            post.status = Post.Status.SCHEDULED
            post.save(update_fields=["scheduled_at", "status", "updated_at"])

            # Trigger publish
            publish_post.delay(str(post.pk))

            # Update queue item
            item.status = QueueItem.Status.PUBLISHED
            item.published_at = now
            item.post = post
            item.save(update_fields=["status", "published_at", "post", "updated_at"])

            published_count += 1
            logger.info(
                "Media Queue published item %s → post %s (%s/%s)",
                item.pk, post.pk, account.platform, account.username,
            )

        except Exception as exc:
            item.status = QueueItem.Status.FAILED
            item.error_message = str(exc)[:500]
            item.save(update_fields=["status", "error_message", "updated_at"])
            logger.error("Media Queue publish failed for item %s: %s", item.pk, exc, exc_info=True)

        # Check if queue is now low
        if queue.is_low:
            remaining = queue.queued_count
            try:
                Notification.create_for_user(
                    user=queue.user,
                    notification_type="system",
                    message=(
                        f"Your {account.get_platform_display()} photo queue is running low — "
                        f"only {remaining} photo{'s' if remaining != 1 else ''} left. "
                        f"Upload more to keep posting!"
                    ),
                )
            except Exception:
                pass  # best-effort

    # Recalculate schedules for any queue that had items published
    if published_count:
        affected_queues = MediaQueue.objects.filter(
            is_active=True,
            items__status=QueueItem.Status.QUEUED,
        ).distinct()
        for q in affected_queues:
            try:
                recalculate_schedule(q)
            except Exception as exc:
                logger.warning("Schedule recalc failed for queue %s: %s", q.pk, exc)

    logger.info("Media Queue processed: %d items published", published_count)
    return {"published": published_count}


def _generate_ai_caption(user, platform, queue_name=""):
    """
    Generate an AI caption for a media queue photo that has no user-written caption.
    Uses the user's brand voice + product context to write a platform-appropriate caption.
    Falls back to empty string on any error (never blocks publishing).
    """
    try:
        from apps.agents.llm import generate, get_model_for_task
        from apps.products.utils import get_product_context

        profile = getattr(user, "profile", None)
        brand_voice = getattr(profile, "brand_voice", "") if profile else ""
        company = getattr(profile, "company_name", "") if profile else ""
        product_ctx = get_product_context(user)

        platform_hints = {
            "instagram": "Use 2-4 relevant hashtags. Keep it casual and visual. Max 150 words.",
            "facebook": "Conversational tone. Ask a question to drive comments. Max 100 words.",
            "twitter": "Short and punchy. Max 280 characters total. 1-2 hashtags max.",
            "linkedin": "Professional tone. Add value or insight. Max 150 words.",
            "tiktok": "Trendy, casual, hook-first. Max 100 characters.",
        }

        prompt = (
            f"Write a social media caption for a photo being posted to {platform}.\n\n"
            f"Business: {company or 'a small business'}\n"
            f"Queue: {queue_name or 'General photos'}\n"
        )
        if brand_voice:
            prompt += f"Brand voice: {brand_voice[:300]}\n"
        if product_ctx:
            prompt += f"\n{product_ctx[:500]}\n"
        prompt += (
            f"\nPlatform guidelines: {platform_hints.get(platform, 'Keep it engaging and on-brand.')}\n\n"
            f"Write ONLY the caption text. No quotes, no labels, no explanation."
        )

        response = generate(
            prompt=prompt,
            system="You are a social media copywriter. Write captions that match the brand voice and drive engagement.",
            model=get_model_for_task("create.write", user=user),
            temperature=0.7,
            max_tokens=300,
        )

        caption = (response.content or "").strip().strip('"').strip("'")
        logger.info("AI caption generated for %s/%s (%d chars)", user.email, platform, len(caption))
        return caption

    except Exception as e:
        logger.warning("AI caption generation failed for %s: %s", user.email, e)
        return ""
