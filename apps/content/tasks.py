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


# ── Media URL helpers ────────────────────────────────────────────────────

def _public_url_for_file(file_name: str):
    """
    Generate a publicly accessible URL for a file in storage.

    Prefers the public URL from default_storage (uses AWS_S3_CUSTOM_DOMAIN
    when configured, giving a clean URL that any platform API can download).
    Falls back to constructing the URL from R2 env vars directly (handles
    cases where the Celery worker's default_storage differs from web).
    Returns None if no public URL can be constructed.
    """
    import os
    from django.core.files.storage import default_storage
    from django.conf import settings

    try:
        # Prefer the public URL (uses custom domain like pub-xxx.r2.dev)
        url = default_storage.url(file_name)
        if url.startswith(("http://", "https://")):
            return url

        # S3/R2 fallback: generate a pre-signed URL (1 hour expiry)
        try:
            from storages.backends.s3boto3 import S3Boto3Storage
            if isinstance(default_storage, S3Boto3Storage):
                key = default_storage._normalize_name(
                    default_storage._clean_name(file_name)
                )
                return default_storage.connection.meta.client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": default_storage.bucket_name, "Key": key},
                    ExpiresIn=3600,
                )
        except ImportError:
            pass

        # R2 fallback: construct URL from env vars directly (works even
        # when default_storage is FileSystemStorage but R2 is configured)
        custom_domain = (
            getattr(settings, "AWS_S3_CUSTOM_DOMAIN", "")
            or os.environ.get("AWS_S3_CUSTOM_DOMAIN", "")
        )
        if custom_domain:
            location = (
                getattr(settings, "AWS_LOCATION", "")
                or os.environ.get("AWS_LOCATION", "media")
            )
            prefix = f"{location}/" if location else ""
            return f"https://{custom_domain}/{prefix}{file_name}"

        # Last resort: SITE_URL + relative path
        site_url = getattr(settings, "SITE_URL", "").rstrip("/")
        if site_url and "localhost" not in site_url:
            return f"{site_url}{url}"
    except Exception as e:
        logger.warning("Could not generate public URL for %s: %s", file_name, e)
    return None


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
        "utm_content": post_id[:8],
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


@shared_task(name="content.post_generate_analytics", soft_time_limit=120, time_limit=150)
def post_generate_analytics(post_ids: list[str]):
    """
    Run Content DNA extraction + engagement prediction AFTER posts are created.
    Runs as a background task so the user sees posts immediately.
    """
    from apps.content.models import Post
    from apps.agents.analyst_agent import batch_extract_content_dna, batch_predict_engagement

    posts = list(Post.objects.filter(pk__in=post_ids).select_related("social_account", "user"))
    if not posts:
        return

    try:
        batch_extract_content_dna(posts)
    except Exception as e:
        logger.warning("Async batch DNA extraction failed: %s", e)

    try:
        batch_predict_engagement(posts)
    except Exception as e:
        logger.warning("Async batch engagement prediction failed: %s", e)

    return {"analyzed": len(posts)}


@shared_task(name="content.async_generate_image", soft_time_limit=60, time_limit=90)
def async_generate_image(post_id: str, image_prompt: str, visual_strategy_data: dict | None = None):
    """
    Generate an AI image for a post in the background.
    Fires after post creation so the user sees text content immediately.
    """
    from apps.content.models import Post
    from apps.agents.media import generate_post_image

    try:
        post = Post.objects.get(pk=post_id)
    except Post.DoesNotExist:
        logger.warning("Post %s not found for async image gen", post_id)
        return

    if visual_strategy_data and visual_strategy_data.get("strategy"):
        from apps.agents.visual_strategy import apply_visual_strategy
        if not visual_strategy_data.get("image_prompt") and image_prompt:
            visual_strategy_data["image_prompt"] = image_prompt
        apply_visual_strategy(post, visual_strategy_data)
    else:
        from apps.agents.visual_strategy import infer_visual_strategy, apply_visual_strategy
        strategy = infer_visual_strategy(
            post.content_text,
            post.social_account.platform if post.social_account else "twitter",
        )
        if strategy == "ai_photo":
            generate_post_image(post, image_prompt)
        else:
            apply_visual_strategy(post, {
                "strategy": strategy,
                "image_prompt": image_prompt,
                "text": post.content_text[:300],
                "headline": post.content_text.split("\n")[0][:120],
            })

    return {"post_id": str(post_id), "status": post.media_status}


@shared_task(name="content.generate_from_seed", soft_time_limit=120, time_limit=150)
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

    try:
        posts = run_create_agent(seed)
    except Exception as exc:
        logger.error("generate_from_seed failed for seed %s: %s", seed_id, exc, exc_info=True)
        seed.refresh_from_db()
        if seed.status not in (ContentSeed.SeedStatus.COMPLETED, ContentSeed.SeedStatus.FAILED):
            seed.status = ContentSeed.SeedStatus.FAILED
            seed.error_message = f"Generation failed: {exc}"
            seed.save(update_fields=["status", "error_message", "updated_at"])
        return {"error": str(exc)}

    # Fire off Content DNA + engagement prediction as separate async tasks
    # so they don't block the user from seeing their generated posts.
    post_ids = [str(p.id) for p in posts]
    try:
        post_generate_analytics.delay(post_ids)
    except Exception as e:
        logger.warning("Failed to queue post analytics for seed %s: %s", seed_id, e)

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

    # ── Emergency pause — halt all autonomous publishing ──────────────
    profile = getattr(post.user, "profile", None)
    if profile and profile.emergency_pause:
        logger.info("EMERGENCY PAUSE: skipping publish for post %s (user %s)", post_id, post.user.email)
        return {"error": "Publishing paused — emergency pause is active"}

    # ── Content safety gate — last line of defense before going live ──
    from apps.content.safety import check_content_safety
    safety = check_content_safety(post.content_text, user=post.user)
    if safety.blocked:
        # Hard block: content is dangerous, revert to pending approval
        post.status = Post.Status.PENDING_APPROVAL
        post.ai_reasoning = f"SAFETY BLOCKED: {safety.summary}"
        post.save(update_fields=["status", "ai_reasoning", "updated_at"])
        Notification.create_for_user(
            post.user, "system",
            f"⚠️ Post blocked by safety check: {safety.summary[:150]}. Please review and edit.",
            related_post=post,
        )
        logger.warning("SAFETY BLOCKED post %s: %s", post_id, safety.summary)
        return {"error": f"Content blocked: {safety.summary}"}
    elif not safety.is_safe:
        # Soft block: risky content, send back for human review
        post.status = Post.Status.PENDING_APPROVAL
        post.ai_reasoning = f"SAFETY REVIEW (score={safety.risk_score}): {safety.summary}"
        post.save(update_fields=["status", "ai_reasoning", "updated_at"])
        Notification.create_for_user(
            post.user, "system",
            f"⚠️ Post needs review (risk score {safety.risk_score}): {safety.summary[:150]}",
            related_post=post,
        )
        logger.info("SAFETY REVIEW post %s (score=%d): %s", post_id, safety.risk_score, safety.summary)
        return {"error": f"Content flagged for review: {safety.summary}"}

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
        publish_kwargs = {"account": account}
        if account.platform in ("facebook", "instagram"):
            pages = (account.metadata or {}).get("pages", [])
            if pages:
                publish_kwargs["page_id"] = pages[0]["id"]
                publish_kwargs["page_access_token"] = pages[0].get("access_token", account.access_token)

        # Add UTM tracking to any URLs in the content
        publish_content = add_utm_tracking(post.content_text, account.platform, str(post.id))

        # ── Diagnostic: content audit at publish time ─────────────────
        _db_len = len(post.content_text) if post.content_text else 0
        _pub_len = len(publish_content) if publish_content else 0
        logger.info(
            "AUDIT [%s] post=%s db=%d pub=%d nl=%d",
            account.platform, post.id, _db_len, _pub_len,
            (publish_content or "").count("\n"),
        )
        logger.info("AUDIT first100=%s", (publish_content or "")[:100])
        logger.info("AUDIT last80=%s", (publish_content or "")[-80:])

        # Safety: block publishing to platforms that require media if none attached
        if post.needs_media:
            _fail_post(post, f"{account.get_platform_display()} requires an image but none is attached.")
            Notification.create_for_user(
                post.user, "publish_failed",
                f"{account.get_platform_display()} requires an image. Upload one and retry.",
                related_post=post,
            )
            return {"error": "Media required"}

        # ── Collect media for publishing ──────────────────────────────
        # Two forms:
        #   media_files  – raw bytes read from storage (preferred: works
        #                  with any backend, no public URL needed)
        #   media_urls   – absolute URLs (AI-generated images or pre-signed
        #                  storage URLs, used by APIs that *require* a URL,
        #                  e.g. Instagram Container API)
        import mimetypes
        from django.core.files.storage import default_storage

        media_files = []   # [(filename, bytes, content_type), ...]
        media_urls_list = list(post.media_urls or [])  # AI-generated (already public)

        for attachment in post.attachments.order_by("order"):
            if not attachment.file:
                continue
            # Build the public URL first (needed for URL-based fallback)
            url = _public_url_for_file(attachment.file.name)

            # Read the file bytes from storage (works with S3, R2, local FS)
            try:
                with default_storage.open(attachment.file.name, "rb") as fh:
                    data = fh.read()
                fname = attachment.file.name.rsplit("/", 1)[-1]
                ctype = mimetypes.guess_type(fname)[0] or "image/jpeg"
                media_files.append((fname, data, ctype))
            except Exception as e:
                logger.warning("Could not read attachment %s from storage: %s", attachment.pk, e)
                # Fallback: download from the public R2 URL
                if url:
                    try:
                        import httpx
                        dl_resp = httpx.get(url, timeout=30, follow_redirects=True)
                        dl_resp.raise_for_status()
                        fname = attachment.file.name.rsplit("/", 1)[-1]
                        ctype = (
                            dl_resp.headers.get("content-type", "").split(";")[0]
                            or mimetypes.guess_type(fname)[0]
                            or "image/jpeg"
                        )
                        media_files.append((fname, dl_resp.content, ctype))
                        logger.info("Downloaded attachment %s via public URL (%d bytes)", attachment.pk, len(dl_resp.content))
                    except Exception as dl_err:
                        logger.warning("Could not download attachment %s from %s: %s", attachment.pk, url, dl_err)

            if url:
                media_urls_list.insert(0, url)

        absolute_media_urls = (
            [u for u in media_urls_list if u.startswith(("http://", "https://"))]
            or None
        )

        # Safety net: detect and fix encrypted tokens not decrypted by ORM
        token = account.access_token
        if token and token.startswith("gAAAAA"):
            from apps.platforms.encryption import decrypt_token
            logger.warning(
                "Token for %s still encrypted after ORM load (len=%d). "
                "Attempting explicit decrypt.",
                account.platform, len(token),
            )
            token = decrypt_token(token)
            if token.startswith("gAAAAA"):
                logger.error(
                    "Explicit decrypt ALSO failed for %s. Token is unrecoverable — "
                    "user must reconnect.",
                    account.platform,
                )

        result = provider.publish_post(
            access_token=token,
            content=publish_content,
            media_urls=absolute_media_urls,
            media_files=media_files or None,
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

        logger.info(
            "PUBLISH SUCCESS [%s] post=%s: platform_id=%s, "
            "content_len=%d chars sent, url=%s",
            account.platform, post.id,
            result.platform_post_id,
            len(publish_content or ""),
            result.url,
        )

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
    Also auto-schedules approved posts that are missing a scheduled_at time.
    Runs every 5 minutes via Celery Beat.
    """
    from apps.agents.adapt_agent import auto_schedule_post
    from apps.content.models import Post

    now = timezone.now()

    # ── Step 1: Auto-schedule approved posts missing scheduled_at ─────
    # These are posts the user approved (or Strategist created) but never
    # got a time assigned — e.g. auto_approve was just enabled, or the
    # user approved from the dashboard without picking a time.
    unscheduled = Post.objects.filter(
        status=Post.Status.APPROVED,
        scheduled_at__isnull=True,
    ).select_related("social_account", "user", "user__profile")[:20]  # cap per cycle

    auto_scheduled = 0
    for post in unscheduled:
        try:
            result = auto_schedule_post(post)
            if result:
                auto_scheduled += 1
        except Exception as e:
            logger.warning("Auto-schedule failed for post %s: %s", post.pk, e)

    if auto_scheduled:
        logger.info("Auto-scheduled %d approved posts that were missing scheduled_at", auto_scheduled)

    # ── Step 2: Dispatch posts whose scheduled_at has arrived ─────────
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
    else:
        # Diagnostic: log pipeline state so we can see why nothing publishes
        total_approved = Post.objects.filter(status=Post.Status.APPROVED).count()
        total_scheduled = Post.objects.filter(status=Post.Status.SCHEDULED).count()
        no_schedule = Post.objects.filter(
            status__in=[Post.Status.APPROVED, Post.Status.SCHEDULED],
            scheduled_at__isnull=True,
        ).count()
        future = Post.objects.filter(
            status__in=[Post.Status.APPROVED, Post.Status.SCHEDULED],
            scheduled_at__gt=now,
        ).count()
        if total_approved or total_scheduled or no_schedule:
            logger.info(
                "Publish check: 0 due. %d approved, %d scheduled, "
                "%d missing scheduled_at, %d scheduled for future.",
                total_approved, total_scheduled, no_schedule, future,
            )
    return {"dispatched": count, "auto_scheduled": auto_scheduled}


@shared_task(name="content.fetch_post_metrics")
def fetch_post_metrics(post_id: str):
    """
    Fetch engagement metrics for a published post from its platform.
    Includes circuit-breaker: skips accounts that recently failed with
    permission errors to avoid hammering the API with known-bad tokens.
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

    # ── Circuit breaker: skip accounts with recent permission failures ────
    # If this account's metadata has a metrics_permission_error timestamp
    # within the last 6 hours, skip the API call entirely.
    import datetime as _dt
    meta = account.metadata or {}
    perm_error_at = meta.get("metrics_permission_error_at")
    if perm_error_at:
        try:
            error_time = _dt.datetime.fromisoformat(perm_error_at)
            if timezone.now() - error_time < _dt.timedelta(hours=6):
                return {
                    "skipped": True,
                    "reason": "Account has recent permission error — circuit breaker active",
                    "post_id": post_id,
                }
        except (ValueError, TypeError):
            pass  # Invalid timestamp, proceed normally

    try:
        # For Facebook/Instagram, use page token — the user-level token
        # does NOT have pages_read_engagement permission.
        token = account.access_token
        if account.platform in ("facebook", "instagram"):
            pages = (account.metadata or {}).get("pages", [])
            page_token = pages[0].get("access_token") if pages else None
            if not page_token:
                logger.warning(
                    "No page access token for %s account %s (user %s) — "
                    "skipping metrics fetch. User needs to reconnect.",
                    account.platform, account.id, account.user_id,
                )
                return {
                    "error": f"No page token for {account.platform} — reconnect required",
                    "post_id": post_id,
                }
            token = page_token

        metrics_data = provider.get_post_metrics(
            access_token=token,
            platform_post_id=post.platform_post_id,
        )
    except Exception as e:
        error_str = str(e)
        # Detect permission errors and activate circuit breaker
        if "pages_read_engagement" in error_str or "OAuthException" in error_str:
            meta = account.metadata or {}
            meta["metrics_permission_error_at"] = timezone.now().isoformat()
            account.metadata = meta
            account.save(update_fields=["metadata", "updated_at"])
            logger.warning(
                "Circuit breaker activated for %s account %s — "
                "permission error, will skip metrics for 6 hours. "
                "User needs to reconnect with pages_read_engagement.",
                account.platform, account.id,
            )
        else:
            logger.warning("Failed to fetch metrics for post %s: %s", post_id, e)
        return {"error": error_str}

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

    if count:
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


# ── Content Recycling Engine ─────────────────────────────────────────────────

@shared_task(name="content.recycle_top_content")
def recycle_top_content():
    """
    Find high-performing published posts (30+ days old) and create
    ContentSeeds to repurpose them on different platforms or with fresh angles.
    Runs daily. Max 1 recycle-seed per user per day.
    """
    from datetime import timedelta

    from django.contrib.auth import get_user_model
    from django.db.models import F, Q

    from apps.analytics.models import PostMetric
    from apps.content.models import ContentSeed, Post
    from apps.platforms.models import SocialAccount

    User = get_user_model()
    cutoff = timezone.now() - timedelta(days=30)
    recycled = 0

    for user in User.objects.filter(is_active=True):
        # Skip if already recycled recently
        recent_recycle = ContentSeed.objects.filter(
            user=user,
            notes__startswith="[Recycle]",
            created_at__gte=timezone.now() - timedelta(hours=24),
        ).exists()
        if recent_recycle:
            continue

        platforms = list(
            SocialAccount.objects.filter(user=user, is_active=True)
            .values_list("platform", flat=True)
        )
        if not platforms:
            continue

        # Find top-performing posts: published 30+ days ago, with good engagement
        top_posts = (
            Post.objects.filter(
                user=user,
                status=Post.Status.PUBLISHED,
                published_at__lte=cutoff,
                published_at__isnull=False,
                metrics__isnull=False,
            )
            .select_related("metrics")
            .order_by("-metrics__engagement_rate")[:10]
        )

        for post in top_posts:
            metrics = post.metrics
            # Require meaningful engagement
            total_engagement = (
                metrics.likes + metrics.comments + metrics.shares + metrics.saves
            )
            if total_engagement < 5:
                continue

            # Don't recycle the same post twice
            already_recycled = ContentSeed.objects.filter(
                user=user,
                notes__contains=str(post.id),
            ).exists()
            if already_recycled:
                continue

            # Pick different platforms for cross-posting
            other_platforms = [p for p in platforms if p != post.platform]
            target = other_platforms[:2] if other_platforms else [post.platform]

            ContentSeed.objects.create(
                user=user,
                idea=(
                    f"Repurpose top-performing content:\n\n"
                    f"Original ({post.platform}): {post.content_text[:300]}\n\n"
                    f"Performance: {total_engagement} engagements, "
                    f"{metrics.engagement_rate or 0:.1f}% rate\n\n"
                    f"Give it a fresh angle for {', '.join(target)}."
                ),
                notes=f"[Recycle] From post {post.id} ({post.platform})",
                target_platforms=target,
            )
            recycled += 1
            break  # Max 1 per user

    logger.info("Content recycling: created %d seeds", recycled)
    return {"recycled": recycled}
