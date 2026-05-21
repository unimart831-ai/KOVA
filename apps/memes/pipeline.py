"""Meme → Studio pipeline helpers (shared by views and Celery tasks)."""

import logging

logger = logging.getLogger(__name__)


def create_posts_from_adaptation(adaptation):
    """
    Convert an approved MemeAdaptation into Post row(s).
    Returns (created_posts, skipped_platforms).
    """
    from apps.content.models import Post
    from apps.platforms.models import SocialAccount

    content_text = adaptation.adapted_text
    if adaptation.adapted_caption and adaptation.adapted_caption.strip() not in content_text:
        content_text = f"{content_text}\n\n{adaptation.adapted_caption}".strip()

    targets = list(adaptation.platform_targets or [])
    if not targets:
        first_account = SocialAccount.objects.filter(
            user=adaptation.user, is_active=True,
        ).first()
        if first_account:
            targets = [first_account.platform]
        else:
            return [], []

    accounts_by_platform = {
        sa.platform: sa
        for sa in SocialAccount.objects.filter(user=adaptation.user, is_active=True)
    }

    created_posts = []
    skipped = []
    image_prompt = (adaptation.image_prompt or "").strip()

    for plat in targets:
        sa = accounts_by_platform.get(plat)
        if not sa:
            skipped.append(plat)
            continue

        post_format = Post.PostFormat.TEXT
        aspect_ratio = Post.AspectRatio.SQUARE
        if image_prompt:
            if plat == "whatsapp":
                post_format = Post.PostFormat.STORY
                aspect_ratio = Post.AspectRatio.STORY
            elif plat in ("instagram", "facebook"):
                post_format = Post.PostFormat.IMAGE
                aspect_ratio = Post.AspectRatio.SQUARE

        post = Post.objects.create(
            user=adaptation.user,
            social_account=sa,
            platform=plat,
            content_text=content_text,
            content_type="original",
            status=Post.Status.PENDING_APPROVAL,
            generated_by_agent="meme_engine",
            ai_angle=f"Meme adaptation: {adaptation.trending_meme.title}"[:255],
            ai_reasoning=(adaptation.ai_reasoning or "")[:5000],
            post_format=post_format,
            aspect_ratio=aspect_ratio,
            media_prompt=image_prompt,
        )
        created_posts.append(post)

        if image_prompt and post_format != Post.PostFormat.TEXT:
            try:
                from apps.content.tasks import async_generate_image
                async_generate_image.delay(str(post.id), image_prompt, None)
            except Exception as e:
                logger.warning("Meme image gen queue failed for post %s: %s", post.id, e)

    if created_posts and not adaptation.post:
        adaptation.post = created_posts[0]
        adaptation.save(update_fields=["post", "updated_at"])

    return created_posts, skipped


def auto_queue_adaptation(adaptation, prefs):
    """If auto_queue enabled and scores are strong, approve and push to Studio."""
    from apps.memes.models import MemeAdaptation

    if not prefs or not prefs.auto_queue:
        return None
    if adaptation.status != MemeAdaptation.Status.DRAFT:
        return None
    if adaptation.brand_relevance_score < 65:
        return None

    adaptation.status = MemeAdaptation.Status.APPROVED
    adaptation.save(update_fields=["status", "updated_at"])
    posts, _skipped = create_posts_from_adaptation(adaptation)
    return posts
