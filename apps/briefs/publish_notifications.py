"""WhatsApp publish health alerts — success, failure, token issues."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def notify_publish_success(post) -> None:
    """Tell the owner on WhatsApp when a post goes live."""
    try:
        account = post.social_account
        platform = account.get_platform_display() if account else (post.platform or "social")
        fmt = getattr(post, "post_format", "") or "post"
        preview = (post.content_text or "")[:80].strip()
        when = ""
        if post.published_at:
            when = post.published_at.strftime("%I:%M %p").lstrip("0")
        body = (
            f"✅ *Live on {platform}*\n"
            f"{fmt.title()} · {when or 'just now'}\n"
        )
        if preview:
            body += f"\"{preview}{'…' if len(post.content_text or '') > 80 else ''}\"\n"
        if post.platform_post_url:
            body += f"\n{post.platform_post_url}"
        body += "\n\nReply RETRY if another post failed · WEEKLY for your scorecard."
        from apps.briefs.owner_alerts import queue_owner_alert

        queue_owner_alert(post.user, body)
    except Exception:
        logger.exception("WhatsApp publish success alert failed for post %s", getattr(post, "pk", ""))


def notify_publish_failure(post, *, reason: str = "", retry_hint: bool = True) -> None:
    """Tell the owner on WhatsApp when publish fails."""
    try:
        account = post.social_account
        platform = account.get_platform_display() if account else (post.platform or "social")
        err = (reason or post.publish_error or "Unknown error")[:200]
        body = (
            f"❌ *Publish failed — {platform}*\n"
            f"{err}\n"
        )
        if retry_hint:
            body += "\nReply *RETRY* to republish the latest failed post · POSTS to review queue."
        from apps.briefs.owner_alerts import queue_owner_alert

        queue_owner_alert(post.user, body)
    except Exception:
        logger.exception("WhatsApp publish failure alert failed for post %s", getattr(post, "pk", ""))


def notify_token_expiry_whatsapp(user, message: str) -> None:
    """Mirror in-app token warnings to owner WhatsApp."""
    if not message:
        return
    from apps.briefs.owner_alerts import queue_owner_alert

    queue_owner_alert(user, message[:4096])
