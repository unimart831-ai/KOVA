"""
Engage Agent — Community Intelligence & Response Engine.

Responsibilities:
  1. Fetch interactions (comments, mentions, DMs) from all connected platforms
  2. Analyze sentiment and priority of each interaction
  3. Generate contextual reply suggestions
  4. Auto-respond to high-confidence interactions (when enabled)
  5. Detect superfans (repeat engagers) and flag VIP interactions

Architecture:
  Platform APIs → fetch_interactions() → analyze + score → generate replies → Interaction objects
  Celery Beat runs fetch_all_interactions() periodically.
  High-priority items get flagged in the Daily Brief.
"""

import json
import logging
from datetime import timedelta

from django.utils import timezone

from apps.agents.llm import generate, get_model_for_task, parse_llm_json
from apps.agents.models import AgentAction, AgentConfig
from apps.engage.models import Interaction, Superfan
from apps.platforms.models import SocialAccount
from apps.platforms.providers.base import PlatformAuthError
from apps.platforms.providers.registry import get_provider

logger = logging.getLogger(__name__)


# ─── Reply Learning (feedback from user-edited replies) ──────────────────────

def _get_reply_edit_patterns(user):
    """
    Analyze past AI-suggested replies that the user edited before sending.
    Shows the agent what kinds of replies the user prefers so it can learn.
    """
    edited = Interaction.objects.filter(
        user=user,
        user_edited_reply=True,
        ai_suggested_reply__gt="",
        ai_reply_sent__gt="",
    ).order_by("-created_at")[:5]

    if not edited.exists():
        return ""

    total_replies = Interaction.objects.filter(
        user=user,
        ai_reply_sent__gt="",
    ).count()
    edit_count = edited.count()

    parts = ["## REPLY STYLE LEARNING (from your past corrections)"]
    parts.append(f"User edited {edit_count} of their last {total_replies} replies.\n")
    parts.append("Study these corrections to match their preferred reply style:")

    for i, intr in enumerate(edited[:3], 1):
        parts.append(f"\n### Correction #{i}:")
        parts.append(f"  Interaction: \"{intr.content[:100]}...\"")
        parts.append(f"  AI suggested: \"{intr.ai_suggested_reply[:100]}...\"")
        parts.append(f"  User rewrote to: \"{intr.ai_reply_sent[:100]}...\"")

    # Also show accepted replies (ones the user approved without changes)
    accepted = Interaction.objects.filter(
        user=user,
        user_edited_reply=False,
        ai_reply_sent__gt="",
    ).order_by("-created_at")[:3]

    if accepted:
        parts.append("\n### Replies the user sent WITHOUT editing (aim for this style):")
        for intr in accepted:
            parts.append(f"  - To \"{intr.content[:80]}...\" → \"{intr.ai_reply_sent[:100]}\"")

    parts.append("\nINSTRUCTION: Match the user's correction patterns. Write replies they would send as-is.\n")
    return "\n".join(parts)


# ─── Interaction Fetching ────────────────────────────────────────────────────

def fetch_interactions(user):
    """
    Pull new comments, mentions, and DMs from all connected platforms.
    Creates Interaction objects for anything we haven't seen before.

    Returns count of new interactions fetched.
    """
    config = AgentConfig.objects.filter(user=user, agent_type="engage").first()
    if config and not config.is_active:
        logger.info("Engage agent disabled for %s, skipping fetch", user.email)
        return 0

    accounts = SocialAccount.objects.filter(user=user, is_active=True)
    total_new = 0

    for account in accounts:
        provider = get_provider(account.platform)
        if not provider:
            continue

        # Fetch comments on recent posts
        total_new += _fetch_post_comments(user, account, provider)

        # Fetch mentions (only for platforms that implement it)
        if account.platform not in ("facebook", "instagram"):
            total_new += _fetch_mentions(user, account, provider)

    if total_new > 0:
        logger.info("Fetched %d new interactions for %s", total_new, user.email)

    return total_new


def _fetch_post_comments(user, account, provider):
    """Fetch comments on the user's recent published posts."""
    from apps.content.models import Post

    new_count = 0
    recent_posts = Post.objects.filter(
        user=user,
        social_account=account,
        status=Post.Status.PUBLISHED,
        platform_post_id__gt="",
        published_at__gte=timezone.now() - timedelta(days=7),
    ).order_by("-published_at")[:10]

    # For Facebook/Instagram, use page token instead of user token
    token = account.access_token
    if account.platform in ("facebook", "instagram"):
        pages = (account.metadata or {}).get("pages", [])
        if pages:
            token = pages[0].get("access_token", account.access_token)

    for post in recent_posts:
        try:
            comments = provider.get_comments(
                access_token=token,
                post_id=post.platform_post_id,
            )

            for comment in comments:
                ext_id = str(comment.get("id", ""))
                if not ext_id:
                    continue

                # Skip if already tracked
                if Interaction.objects.filter(
                    social_account=account,
                    platform_interaction_id=ext_id,
                ).exists():
                    continue

                Interaction.objects.create(
                    user=user,
                    social_account=account,
                    post=post,
                    interaction_type=Interaction.InteractionType.COMMENT,
                    author_name=comment.get("author_name", "Unknown"),
                    author_username=comment.get("author_id", ""),
                    content=comment.get("text", ""),
                    platform_interaction_id=ext_id,
                )
                new_count += 1

        except PlatformAuthError as e:
            # Token expired or permissions missing — mark account and stop all retries
            logger.error(
                "Auth error for %s account %s — marking for reauth: %s",
                account.platform, account.id, e,
            )
            account.mark_error(str(e))
            break  # stop trying other posts on this account

        except Exception as e:
            logger.warning(
                "Failed to fetch comments for post %s on %s: %s",
                post.platform_post_id, account.platform, e,
            )

    return new_count


def _fetch_mentions(user, account, provider):
    """Fetch recent mentions/tags for this account."""
    new_count = 0

    try:
        mentions = provider.get_mentions(
            access_token=account.access_token,
        )

        for mention in mentions:
            ext_id = str(mention.get("id", ""))
            if not ext_id:
                continue

            if Interaction.objects.filter(
                social_account=account,
                platform_interaction_id=ext_id,
            ).exists():
                continue

            Interaction.objects.create(
                user=user,
                social_account=account,
                interaction_type=Interaction.InteractionType.MENTION,
                author_name=mention.get("author", "Unknown"),
                author_username=mention.get("author_id", ""),
                content=mention.get("text", ""),
                platform_interaction_id=ext_id,
            )
            new_count += 1

    except Exception as e:
        logger.warning(
            "Failed to fetch mentions for %s on %s: %s",
            account.username, account.platform, e,
        )

    return new_count


# ─── Superfan Tracking ───────────────────────────────────────────────────────

def _update_superfans(user, superfan_usernames, interactions):
    """
    Persist superfan records for repeat engagers.
    Called after interaction analysis with the set of usernames
    that have 3+ interactions in the last 30 days.
    """
    for interaction in interactions:
        username = interaction.author_username
        if not username or username not in superfan_usernames:
            continue

        platform = (
            interaction.social_account.platform
            if interaction.social_account else ""
        )

        fan, created = Superfan.objects.get_or_create(
            user=user,
            author_username=username,
            defaults={
                "author_name": interaction.author_name,
                "platforms": [platform] if platform else [],
                "interaction_count": 1,
                "last_sentiment": interaction.sentiment or "",
                "last_interaction_at": interaction.created_at,
            },
        )

        if not created:
            fan.interaction_count = Interaction.objects.filter(
                user=user,
                author_username=username,
            ).count()
            fan.last_sentiment = interaction.sentiment or fan.last_sentiment
            fan.last_interaction_at = interaction.created_at
            fan.author_name = interaction.author_name or fan.author_name

            # Add platform if new
            if platform and platform not in fan.platforms:
                fan.platforms = fan.platforms + [platform]

            fan.update_tier()
            fan.save()


# ─── Sentiment Analysis + Priority Scoring ───────────────────────────────────

def analyze_interactions(user, batch_size=20):
    """
    Analyze unprocessed interactions: sentiment classification, priority
    scoring, and superfan detection. Runs in batches for efficiency.

    Returns count of interactions analyzed.
    """
    config = AgentConfig.objects.filter(user=user, agent_type="engage").first()
    if config and not config.is_active:
        return 0

    # Get interactions that need analysis (no sentiment yet, still "new")
    unanalyzed = Interaction.objects.filter(
        user=user,
        status=Interaction.Status.NEW,
        sentiment="",
    ).order_by("-created_at")[:batch_size]

    if not unanalyzed.exists():
        return 0

    action = AgentAction.objects.create(
        user=user,
        agent_type="engage",
        action_type="analyze_interactions",
        description=f"Analyzing {unanalyzed.count()} new interactions",
    )

    try:
        # Build batch for LLM analysis
        items = []
        for interaction in unanalyzed:
            items.append({
                "id": str(interaction.id),
                "type": interaction.interaction_type,
                "platform": interaction.social_account.platform if interaction.social_account else "",
                "author": interaction.author_name,
                "content": interaction.content[:300],
            })

        # Check for superfans (repeat engagers)
        author_counts = {}
        all_authors = Interaction.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timedelta(days=30),
        ).values_list("author_username", flat=True)

        for author in all_authors:
            if author:
                author_counts[author] = author_counts.get(author, 0) + 1

        superfans = {a for a, c in author_counts.items() if c >= 3}

        system_prompt = (
            "You are an engagement analyst for a social media brand. "
            "Analyze each interaction and classify it.\n\n"
            "For each interaction, determine:\n"
            "1. **sentiment**: 'positive', 'neutral', or 'negative'\n"
            "2. **priority**: 'high', 'medium', or 'low'\n"
            "   - HIGH: customer complaints, purchase intent, influencer mentions, negative sentiment\n"
            "   - MEDIUM: genuine questions, detailed feedback, conversation starters\n"
            "   - LOW: generic compliments, emoji-only, spam\n"
            "3. **is_spam**: true/false — is this spam or bot content?\n\n"
            "Respond in JSON: {\"analyses\": [{\"id\": \"...\", \"sentiment\": \"...\", "
            "\"priority\": \"...\", \"is_spam\": false}]}"
        )

        prompt = (
            f"Analyze these {len(items)} interactions:\n\n"
            f"{json.dumps(items, indent=2)}\n\n"
            "Classify each one with sentiment, priority, and spam detection."
        )

        response = generate(
            prompt=prompt,
            system=system_prompt,
            model=get_model_for_task("engage.analyze"),
            json_mode=True,
            temperature=0.1,
            max_tokens=1500,
        )

        try:
            result = parse_llm_json(response.content)
            analyses = {a["id"]: a for a in result.get("analyses", [])}
        except (json.JSONDecodeError, KeyError, ValueError):
            analyses = {}

        analyzed = 0
        for interaction in unanalyzed:
            analysis = analyses.get(str(interaction.id), {})
            interaction.sentiment = analysis.get("sentiment", "neutral")

            # Mark spam as ignored
            if analysis.get("is_spam"):
                interaction.status = Interaction.Status.IGNORED
            # Flag high-priority for attention
            elif analysis.get("priority") == "high":
                interaction.status = Interaction.Status.FLAGGED

            interaction.save(update_fields=["sentiment", "status"])
            analyzed += 1

        # Persist superfan records
        _update_superfans(user, superfans, unanalyzed)

        action.status = AgentAction.ActionStatus.COMPLETED
        action.output_data = {
            "analyzed": analyzed,
            "superfans_detected": len(superfans),
        }
        action.tokens_used = response.total_tokens
        action.input_tokens = response.input_tokens
        action.output_tokens = response.output_tokens
        action.model_used = response.model
        action.completed_at = timezone.now()
        action.save(update_fields=["status", "output_data", "tokens_used", "input_tokens", "output_tokens", "model_used", "completed_at"])

        return analyzed

    except Exception as e:
        logger.exception("Interaction analysis failed: %s", e)
        action.status = AgentAction.ActionStatus.FAILED
        action.error_message = str(e)
        action.save(update_fields=["status", "error_message"])
        return 0


# ─── Reply Generation ────────────────────────────────────────────────────────

def generate_replies(user, batch_size=10):
    """
    Generate AI reply suggestions for interactions that need responses.
    Considers brand voice, conversation context, and sentiment.

    Returns count of replies generated.
    """
    config = AgentConfig.objects.filter(user=user, agent_type="engage").first()
    if config and not config.is_active:
        return 0

    # Get interactions that need replies
    # Prioritize: flagged first, then new with sentiment, skip spam/ignored
    needs_reply = (
        Interaction.objects.filter(
            user=user,
            ai_suggested_reply="",
        )
        .exclude(status__in=[Interaction.Status.IGNORED, Interaction.Status.AI_REPLIED, Interaction.Status.USER_REPLIED])
        .exclude(sentiment="")
        .select_related("social_account", "post")
        .order_by(
            # Flagged items first, then by recency
            models_case_when_priority(),
            "-created_at",
        )[:batch_size]
    )

    if not needs_reply.exists():
        return 0

    action = AgentAction.objects.create(
        user=user,
        agent_type="engage",
        action_type="generate_replies",
        description=f"Generating reply suggestions for {needs_reply.count()} interactions",
    )

    profile = user.profile
    brand_voice = profile.brand_voice or "Professional yet approachable. Helpful and genuine."
    company = profile.company_name or "the brand"

    try:
        total_generated = 0

        for interaction in needs_reply:
            try:
                reply = _generate_single_reply(interaction, brand_voice, company)
                if reply:
                    interaction.ai_suggested_reply = reply
                    interaction.save(update_fields=["ai_suggested_reply"])
                    total_generated += 1
            except Exception as e:
                logger.warning("Reply gen failed for interaction %s: %s", interaction.id, e)

        action.status = AgentAction.ActionStatus.COMPLETED
        action.output_data = {"replies_generated": total_generated}
        action.completed_at = timezone.now()
        action.save(update_fields=["status", "output_data", "completed_at"])

        return total_generated

    except Exception as e:
        logger.exception("Reply generation batch failed: %s", e)
        action.status = AgentAction.ActionStatus.FAILED
        action.error_message = str(e)
        action.save(update_fields=["status", "error_message"])
        return 0


def models_case_when_priority():
    """SQL ordering: flagged first, then new, then rest."""
    from django.db.models import Case, Value, When, IntegerField
    return Case(
        When(status=Interaction.Status.FLAGGED, then=Value(0)),
        When(status=Interaction.Status.NEW, then=Value(1)),
        default=Value(2),
        output_field=IntegerField(),
    )


def _generate_single_reply(interaction, brand_voice, company):
    """Generate a reply for a single interaction."""
    platform = interaction.social_account.platform if interaction.social_account else "social media"
    post_context = ""
    if interaction.post:
        post_context = f"\nOriginal post they're responding to:\n\"{interaction.post.content_text[:200]}...\""

    # Intelligence: learn from past reply edits
    reply_learning = _get_reply_edit_patterns(interaction.user)

    system_prompt = (
        f"You are the community manager for {company}. "
        f"Your brand voice: {brand_voice}\n\n"
        "RULES:\n"
        "- Be genuine, not corporate. Sound human.\n"
        "- Match the energy — if they're excited, be warm. If they're frustrated, be empathetic.\n"
        "- Keep replies concise — this is social media, not email.\n"
        f"- Write in the style native to {platform}.\n"
        "- If it's a question, answer it directly. If it's praise, acknowledge specifically.\n"
        "- If it's a complaint, empathize first, then offer help.\n"
        "- NEVER be defensive or dismissive.\n"
        "- Don't use corporate phrases like 'We appreciate your feedback' or 'Thanks for reaching out'.\n\n"
        "Respond with ONLY the reply text. No JSON, no explanation — just the reply ready to send."
    )

    prompt = (
        f"Platform: {platform}\n"
        f"Interaction type: {interaction.interaction_type}\n"
        f"Sentiment: {interaction.sentiment}\n"
        f"From: {interaction.author_name}"
        f"{f' (@{interaction.author_username})' if interaction.author_username else ''}\n"
        f"Their message:\n\"{interaction.content}\""
        f"{post_context}\n"
    )

    if reply_learning:
        prompt += f"\n{reply_learning}\n"

    prompt += "\nWrite a reply."

    response = generate(
        prompt=prompt,
        system=system_prompt,
        model=get_model_for_task("engage.reply"),
        json_mode=False,
        temperature=0.6,
        max_tokens=300,
    )

    reply = response.content.strip()
    # Remove quotes if LLM wrapped the reply
    if reply.startswith('"') and reply.endswith('"'):
        reply = reply[1:-1]
    return reply


# ─── Auto-Respond ────────────────────────────────────────────────────────────

def auto_respond(user):
    """
    Auto-send replies for high-confidence positive interactions.
    Only active when user has auto_engage=True on their profile.

    Criteria for auto-sending:
      - Sentiment is positive
      - Interaction is a comment or reply (not DM — too personal)
      - Reply has been generated
      - Interaction is still in NEW or FLAGGED status (not already replied)

    Returns count of auto-sent replies.
    """
    profile = user.profile
    if not profile.auto_engage:
        return 0

    config = AgentConfig.objects.filter(user=user, agent_type="engage").first()
    if config and not config.is_active:
        return 0

    # Only auto-reply to positive comments (safest)
    candidates = Interaction.objects.filter(
        user=user,
        sentiment="positive",
        interaction_type__in=["comment", "reply"],
        status=Interaction.Status.NEW,
    ).exclude(
        ai_suggested_reply="",
    ).select_related("social_account")[:5]  # Cap at 5 per cycle

    sent = 0
    for interaction in candidates:
        account = interaction.social_account
        provider = get_provider(account.platform)
        if not provider:
            continue

        try:
            # For Facebook/Instagram, use page token
            token = account.access_token
            if account.platform in ("facebook", "instagram"):
                pages = (account.metadata or {}).get("pages", [])
                if pages:
                    token = pages[0].get("access_token", account.access_token)

            if interaction.interaction_type in ("comment", "reply"):
                provider.reply_to_comment(
                    access_token=token,
                    comment_id=interaction.platform_interaction_id,
                    message=interaction.ai_suggested_reply,
                )

            interaction.ai_reply_sent = interaction.ai_suggested_reply
            interaction.status = Interaction.Status.AI_REPLIED
            interaction.save(update_fields=["ai_reply_sent", "status"])
            sent += 1

            logger.info(
                "Auto-replied to %s comment from %s on %s",
                interaction.sentiment, interaction.author_name, account.platform,
            )

        except Exception as e:
            logger.warning(
                "Auto-reply failed for interaction %s: %s", interaction.id, e,
            )

    if sent:
        logger.info("Auto-responded to %d interactions for %s", sent, user.email)

    return sent


# ─── Orchestrator: Full Engage Cycle ─────────────────────────────────────────

def run_engage_cycle(user):
    """
    Run the full engagement cycle for a user:
      1. Fetch new interactions from all platforms
      2. Analyze sentiment + priority
      3. Generate reply suggestions
      4. Auto-respond (if enabled)

    Called by the periodic Celery task.
    Returns a summary dict.
    """
    fetched = fetch_interactions(user)
    analyzed = analyze_interactions(user)
    replies = generate_replies(user)
    auto_sent = auto_respond(user)

    return {
        "fetched": fetched,
        "analyzed": analyzed,
        "replies_generated": replies,
        "auto_sent": auto_sent,
    }
