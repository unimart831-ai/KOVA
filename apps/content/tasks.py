"""
Celery tasks for the content app.

Handles async content generation via the Create Agent,
auto-publishing at scheduled times, and metrics fetching.
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="content.generate_from_seed")
def generate_from_seed(seed_id: str):
    """
    Run the Create Agent on a ContentSeed.
    Called when user submits a new idea.
    """
    from apps.content.models import ContentSeed
    from apps.agents.create_agent import run_create_agent

    try:
        seed = ContentSeed.objects.select_related("user", "user__profile").get(pk=seed_id)
    except ContentSeed.DoesNotExist:
        logger.error("ContentSeed %s not found", seed_id)
        return {"error": "Seed not found"}

    posts = run_create_agent(seed)
    return {
        "seed_id": str(seed_id),
        "posts_created": len(posts),
        "post_ids": [str(p.id) for p in posts],
    }


@shared_task(name="content.publish_post", bind=True, max_retries=3)
def publish_post(self, post_id: str):
    """
    Publish a single post to its platform.
    Called when a post's scheduled_at time arrives, or on 'post_now' intent.
    Retries up to 3 times on transient failures.
    """
    from apps.content.models import Post
    from apps.platforms.providers import get_provider
    from apps.notifications.models import Notification

    try:
        post = Post.objects.select_related("social_account", "user").get(pk=post_id)
    except Post.DoesNotExist:
        logger.error("Post %s not found for publishing", post_id)
        return {"error": "Post not found"}

    # Guard: only publish approved/scheduled posts
    if post.status not in (Post.Status.APPROVED, Post.Status.SCHEDULED):
        logger.warning("Post %s has status %s, skipping publish", post_id, post.status)
        return {"error": f"Post status is {post.status}, not publishable"}

    # Mark as publishing
    post.status = Post.Status.PUBLISHING
    post.save(update_fields=["status", "updated_at"])

    account = post.social_account
    provider = get_provider(account.platform)

    if not provider:
        _fail_post(post, f"No provider found for platform: {account.platform}")
        Notification.create_for_user(
            post.user, "publish_failed",
            f"Failed to publish to {account.get_platform_display()}: unsupported platform",
            related_post=post,
        )
        return {"error": "No provider"}

    # Check token freshness
    if account.is_token_expired and account.refresh_token:
        try:
            tokens = provider.refresh_access_token(account.refresh_token)
            account.access_token = tokens["access_token"]
            if tokens.get("refresh_token"):
                account.refresh_token = tokens["refresh_token"]
            if tokens.get("expires_at"):
                account.token_expires_at = tokens["expires_at"]
            account.save(update_fields=["access_token", "refresh_token", "token_expires_at", "updated_at"])
        except Exception as e:
            _fail_post(post, f"Token refresh failed: {e}")
            account.mark_error(f"Token refresh failed: {e}")
            Notification.create_for_user(
                post.user, "publish_failed",
                f"Failed to publish to {account.get_platform_display()}: authentication expired. Please reconnect.",
                related_post=post,
            )
            return {"error": "Token refresh failed"}

    if account.needs_reauth:
        _fail_post(post, "Account needs re-authentication")
        Notification.create_for_user(
            post.user, "publish_failed",
            f"{account.get_platform_display()} needs to be reconnected.",
            related_post=post,
        )
        return {"error": "Needs reauth"}

    # Publish
    try:
        result = provider.publish_post(
            access_token=account.access_token,
            content=post.content_text,
            media_urls=post.media_urls or None,
        )
    except Exception as exc:
        logger.exception("Publishing post %s raised an exception", post_id)
        # Retry on transient errors
        try:
            self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            _fail_post(post, f"Max retries exceeded: {exc}")
            Notification.create_for_user(
                post.user, "publish_failed",
                f"Failed to publish to {account.get_platform_display()} after multiple attempts.",
                related_post=post,
            )
            return {"error": "Max retries exceeded"}

    if result.success:
        post.status = Post.Status.PUBLISHED
        post.published_at = timezone.now()
        post.platform_post_id = result.platform_post_id
        post.platform_post_url = result.url
        post.save(update_fields=[
            "status", "published_at", "platform_post_id",
            "platform_post_url", "updated_at",
        ])
        account.mark_synced()
        Notification.create_for_user(
            post.user, "post_published",
            f"Published to {account.get_platform_display()}: {post.content_text[:80]}...",
            related_post=post,
        )
        # Schedule metrics fetch in 1 hour
        fetch_post_metrics.apply_async(args=[str(post.id)], countdown=3600)
        logger.info("Post %s published successfully to %s", post_id, account.platform)
        return {"success": True, "platform_post_id": result.platform_post_id}
    else:
        _fail_post(post, result.error)
        Notification.create_for_user(
            post.user, "publish_failed",
            f"Failed to publish to {account.get_platform_display()}: {result.error[:100]}",
            related_post=post,
        )
        return {"error": result.error}


def _fail_post(post, error_message: str):
    """Mark a post as failed with an error message."""
    post.status = post.Status.FAILED
    post.ai_reasoning = f"Publish error: {error_message}"
    post.save(update_fields=["status", "ai_reasoning", "updated_at"])
    logger.error("Post %s failed: %s", post.pk, error_message)


@shared_task(name="content.check_and_publish_due_posts")
def check_and_publish_due_posts():
    """
    Periodic task: find all posts due for publishing and fire publish tasks.
    Should be called by Celery Beat every minute.
    """
    from apps.content.models import Post

    now = timezone.now()
    due_posts = Post.objects.filter(
        status__in=[Post.Status.APPROVED, Post.Status.SCHEDULED],
        scheduled_at__lte=now,
    ).values_list("id", flat=True)

    count = 0
    for post_id in due_posts:
        publish_post.delay(str(post_id))
        count += 1

    if count:
        logger.info("Dispatched %d posts for publishing", count)
    return {"dispatched": count}


@shared_task(name="content.fetch_post_metrics")
def fetch_post_metrics(post_id: str):
    """
    Fetch engagement metrics for a published post from its platform.
    """
    from apps.analytics.models import PostMetric
    from apps.content.models import Post
    from apps.platforms.providers import get_provider

    try:
        post = Post.objects.select_related("social_account").get(pk=post_id)
    except Post.DoesNotExist:
        logger.error("Post %s not found for metrics fetch", post_id)
        return {"error": "Post not found"}

    if post.status != Post.Status.PUBLISHED or not post.platform_post_id:
        return {"error": "Post not published or no platform_post_id"}

    account = post.social_account
    provider = get_provider(account.platform)
    if not provider:
        return {"error": f"No provider for {account.platform}"}

    try:
        metrics_data = provider.get_post_metrics(
            access_token=account.access_token,
            platform_post_id=post.platform_post_id,
        )
    except Exception as e:
        logger.warning("Failed to fetch metrics for post %s: %s", post_id, e)
        return {"error": str(e)}

    metric, _created = PostMetric.objects.update_or_create(
        post=post,
        defaults={
            "impressions": metrics_data.impressions,
            "reach": metrics_data.reach,
            "likes": metrics_data.likes,
            "comments": metrics_data.comments,
            "shares": metrics_data.shares,
            "saves": metrics_data.saves,
            "clicks": metrics_data.clicks,
            "engagement_rate": _calc_engagement_rate(metrics_data),
        },
    )
    logger.info("Metrics updated for post %s", post_id)
    return {"success": True, "post_id": post_id}


def _calc_engagement_rate(metrics):
    """Calculate engagement rate from metrics."""
    total_engagement = metrics.likes + metrics.comments + metrics.shares + metrics.saves
    if metrics.impressions > 0:
        return round((total_engagement / metrics.impressions) * 100, 2)
    return 0.0


@shared_task(name="content.fetch_all_recent_metrics")
def fetch_all_recent_metrics():
    """
    Periodic task: fetch metrics for all posts published in the last 7 days.
    Should be called by Celery Beat every 6 hours.
    """
    from datetime import timedelta

    from apps.content.models import Post

    cutoff = timezone.now() - timedelta(days=7)
    recent_posts = Post.objects.filter(
        status=Post.Status.PUBLISHED,
        published_at__gte=cutoff,
        platform_post_id__gt="",
    ).values_list("id", flat=True)

    count = 0
    for post_id in recent_posts:
        fetch_post_metrics.delay(str(post_id))
        count += 1

    logger.info("Queued metrics fetch for %d recent posts", count)
    return {"queued": count}
