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

        try:
            item.status = QueueItem.Status.PUBLISHING
            item.save(update_fields=["status", "updated_at"])

            # Create a Post so the existing publish pipeline handles it
            post = Post.objects.create(
                user=queue.user,
                social_account=account,
                platform=account.platform,
                content_text=item.caption or "",
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
