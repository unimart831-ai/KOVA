"""
Celery tasks for the content app.

Handles async content generation via the Create Agent,
auto-publishing at scheduled times, and metrics fetching.
"""

import logging
import re
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── UTM Tracking ─────────────────────────────────────────────────────────
# Appends UTM parameters to URLs in post content so we can attribute
# website traffic back to specific posts, platforms, and campaigns.

_URL_RE = re.compile(r'(https?://[^\s<>"\']+)')


def _add_utm_to_url(url: str, platform: str, post_id: str) -> str:
    """Add UTM parameters to a single URL, preserving existing query params."""
    parsed = urlparse(url)
    existing = parse_qs(parsed.query)
    # Don't overwrite if UTM already present
    if any(k.startswith("utm_") for k in existing):
        return url
    utm = {
        "utm_source": platform,
        "utm_medium": "social",
        "utm_campaign": f"kova_{post_id[:8]}",
    }
    separator = "&" if parsed.query else ""
    new_query = f"{parsed.query}{separator}{urlencode(utm)}"
    return urlunparse(parsed._replace(query=new_query))


def add_utm_tracking(content: str, platform: str, post_id: str) -> str:
    """
    Find all URLs in post content and append UTM parameters.
    Returns the content with UTM-tagged URLs.
    """
    def replace_url(match):
        return _add_utm_to_url(match.group(0), platform, str(post_id))
    return _URL_RE.sub(replace_url, content)


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

    # Tag all new posts with Content DNA and engagement prediction (batched = 2 LLM calls instead of 2N)
    from apps.agents.analyst_agent import batch_extract_content_dna, batch_predict_engagement

    try:
        batch_extract_content_dna(posts)
    except Exception as e:
        logger.warning("Batch DNA extraction failed for seed %s: %s", seed_id, e)

    try:
        batch_predict_engagement(posts)
    except Exception as e:
        logger.warning("Batch engagement prediction failed for seed %s: %s", seed_id, e)

    # Auto-schedule if Adapt Agent is active and user has auto_approve on
    from apps.agents.adapt_agent import auto_schedule_post

    profile = getattr(seed.user, "profile", None)
    if profile and profile.auto_approve_posts:
        for post in posts:
            try:
                auto_schedule_post(post)
            except Exception as e:
                logger.warning("Auto-schedule failed for post %s: %s", post.id, e)

    return {
        "seed_id": str(seed_id),
        "posts_created": len(posts),
        "post_ids": [str(p.id) for p in posts],
    }


@shared_task(name="content.regenerate_post_async")
def regenerate_post_async(post_id: str):
    """
    Regenerate a single post asynchronously via the Create Agent.
    Updates the post in-place and sends a notification on completion or failure.
    """
    from apps.content.models import Post
    from apps.agents.create_agent import regenerate_single_post
    from apps.notifications.models import Notification

    try:
        post = Post.objects.select_related("social_account", "user", "seed").get(pk=post_id)
    except Post.DoesNotExist:
        logger.error("Post %s not found for regeneration", post_id)
        return {"error": "Post not found"}

    try:
        post = regenerate_single_post(post)
        # Save version snapshot
        from apps.content.models import PostVersion
        last_ver = post.versions.order_by("-version_number").values_list("version_number", flat=True).first()
        PostVersion.objects.create(
            post=post,
            version_number=(last_ver or 0) + 1,
            content_text=post.content_text,
            source="regeneration",
        )
        Notification.create_for_user(
            post.user, "agent_action",
            f"Post regenerated for {post.platform or 'unknown'}: {post.content_text[:80]}…",
            related_post=post,
        )
        return {"success": True, "post_id": str(post.id)}
    except Exception as exc:
        logger.exception("Regeneration failed for post %s", post_id)
        Notification.create_for_user(
            post.user, "system",
            f"Regeneration failed for your {post.platform or 'unknown'} post. The original content was kept.",
            related_post=post,
        )
        return {"error": str(exc)}


@shared_task(name="content.retry_image_generation")
def retry_image_generation(post_id: str):
    """Retry AI image generation for a post using its stored media_prompt."""
    from apps.content.models import Post
    try:
        post = Post.objects.select_related("user", "social_account").get(id=post_id)
    except Post.DoesNotExist:
        return {"error": "Post not found"}

    prompt = post.media_prompt or ""
    if not prompt.strip():
        post.media_status = "failed"
        post.save(update_fields=["media_status", "updated_at"])
        return {"error": "No image prompt to retry"}

    try:
        from apps.agents.visual_strategy import apply_visual_strategy
        result = apply_visual_strategy(post, {
            "strategy": "ai_photo",
            "image_prompt": prompt,
        })
        if result:
            return {"status": "success", "url": result}
        return {"status": "failed"}
    except Exception as exc:
        logger.exception("Retry image generation failed for post %s: %s", post_id, exc)
        post.media_status = "failed"
        post.save(update_fields=["media_status", "updated_at"])
        return {"error": str(exc)}


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
        # For Facebook/Instagram, pass page_id and page_access_token from stored metadata
        publish_kwargs = {}
        if account.platform in ("facebook", "instagram"):
            pages = (account.metadata or {}).get("pages", [])
            if pages:
                publish_kwargs["page_id"] = pages[0]["id"]
                publish_kwargs["page_access_token"] = pages[0].get("access_token", account.access_token)

        # Add UTM tracking to any URLs in the content
        publish_content = add_utm_tracking(post.content_text, account.platform, str(post.id))

        # Safety: block publishing to platforms that require media if none attached
        if post.needs_media:
            _fail_post(post, f"{account.get_platform_display()} requires an image but none is attached.")
            Notification.create_for_user(
                post.user, "publish_failed",
                f"{account.get_platform_display()} requires an image. Upload one and retry.",
                related_post=post,
            )
            return {"error": "Media required"}

        # Collect all media URLs: AI-generated (media_urls) + user uploads (attachments).
        # Platform APIs need absolute URLs; FileField.url may be relative.
        absolute_media_urls = None
        raw_urls = list(post.media_urls or [])
        # Append user-uploaded attachments (take priority if they exist)
        attachment_urls = list(
            post.attachments.order_by("order").values_list("file", flat=True)
        )
        if attachment_urls:
            from django.conf import settings as _s
            storage_url = getattr(_s, "MEDIA_URL", "/media/")
            raw_urls = [
                f"{storage_url}{f}" if not f.startswith(("http://", "https://")) else f
                for f in attachment_urls
            ] + raw_urls  # uploaded first, then AI-generated
        if raw_urls:
            from django.conf import settings
            site_url = getattr(settings, "SITE_URL", "http://localhost:8000").rstrip("/")
            absolute_media_urls = []
            for url in raw_urls:
                if url.startswith(("http://", "https://")):
                    absolute_media_urls.append(url)
                else:
                    absolute_media_urls.append(f"{site_url}{url}")

        result = provider.publish_post(
            access_token=account.access_token,
            content=publish_content,
            media_urls=absolute_media_urls,
            **publish_kwargs,
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
        # For Facebook/Instagram, use page token
        token = account.access_token
        if account.platform in ("facebook", "instagram"):
            pages = (account.metadata or {}).get("pages", [])
            if pages:
                token = pages[0].get("access_token", account.access_token)

        metrics_data = provider.get_post_metrics(
            access_token=token,
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

    # Intelligence: validate engagement prediction against actual metrics
    from apps.agents.memory import validate_prediction
    validate_prediction(post)

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


# ── A/B Testing Tasks ────────────────────────────────────────────────────────

@shared_task(name="content.generate_ab_test_variants")
def generate_ab_test_variants(ab_test_id: str):
    """
    Run the Create Agent to generate variants for an A/B test.
    Called when user creates a new A/B test.
    """
    from apps.content.models import ABTest
    from apps.agents.create_agent import generate_ab_variants
    from apps.agents.analyst_agent import extract_content_dna, predict_engagement

    try:
        ab_test = ABTest.objects.select_related(
            "user", "user__profile", "social_account", "seed",
        ).get(pk=ab_test_id)
    except ABTest.DoesNotExist:
        logger.error("ABTest %s not found", ab_test_id)
        return {"error": "ABTest not found"}

    posts = generate_ab_variants(ab_test)

    # Tag each variant with Content DNA and engagement prediction
    for post in posts:
        try:
            extract_content_dna(post)
        except Exception as e:
            logger.warning("Content DNA extraction failed for variant %s: %s", post.id, e)
        try:
            predict_engagement(post)
        except Exception as e:
            logger.warning("Engagement prediction failed for variant %s: %s", post.id, e)

    return {
        "ab_test_id": str(ab_test_id),
        "variants_created": len(posts),
        "post_ids": [str(p.id) for p in posts],
    }


@shared_task(name="content.evaluate_ab_tests")
def evaluate_ab_tests():
    """
    Periodic task: find running A/B tests past their duration and evaluate them.
    Should be called by Celery Beat every hour.
    """
    from datetime import timedelta
    from apps.content.models import ABTest
    from apps.agents.analyst_agent import evaluate_ab_test

    now = timezone.now()
    overdue_tests = ABTest.objects.filter(
        status=ABTest.Status.RUNNING,
        started_at__isnull=False,
    ).select_related("user", "social_account")

    evaluated = 0
    for test in overdue_tests:
        if now > test.started_at + timedelta(hours=test.test_duration_hours):
            try:
                evaluate_ab_test(test)
                evaluated += 1
            except Exception as e:
                logger.error("Failed to evaluate A/B test %s: %s", test.id, e)

    if evaluated:
        logger.info("Auto-evaluated %d A/B tests", evaluated)
    return {"evaluated": evaluated}
