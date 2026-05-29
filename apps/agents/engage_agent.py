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

def _recent_corrections_for_brand(user, limit=5):
    """Recent user-provided corrections, formatted as few-shot examples.

    These are pulled from EngageReply rows where the user said
    "I would have replied differently." We surface them to the Engage
    Agent's system prompt so the next reply learns from real corrections
    instead of the original AI's untouched output.

    Returns a string ready to drop into the prompt, or "" if no
    corrections exist yet. Bounded at `limit` so the prompt doesn't
    bloat past the model's effective context.
    """
    from apps.engage.models import EngageReply

    recent = (
        EngageReply.objects
        .filter(interaction__user=user, corrected_at__isnull=False)
        .exclude(correction_text="")
        .order_by("-corrected_at")
        [:limit]
    )
    if not recent:
        return ""
    lines = [
        "PAST CORRECTIONS — the user has previously rewritten these AI replies. "
        "Match the user's style, not the original AI's:",
    ]
    for r in recent:
        reason = f" ({r.get_correction_reason_display()})" if r.correction_reason else ""
        lines.append(
            f"- AI sent: \"{r.sent_text[:200]}\"\n"
            f"  User would have said: \"{r.correction_text[:200]}\"{reason}"
        )
    return "\n".join(lines)


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

    if not accounts.exists():
        logger.info("Engage fetch: %s has no active social accounts", user.email)
        return 0

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
    else:
        logger.info("Engage fetch: 0 new interactions for %s (all already tracked or no comments)", user.email)

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
        published_at__gte=timezone.now() - timedelta(days=14),
    ).order_by("-published_at")[:15]

    if not recent_posts.exists():
        # Count to diagnose WHY no posts qualify for comment fetching
        all_published = Post.objects.filter(
            user=user, social_account=account, status=Post.Status.PUBLISHED,
        ).count()
        no_post_id = Post.objects.filter(
            user=user, social_account=account, status=Post.Status.PUBLISHED,
            platform_post_id="",
        ).count()
        logger.info(
            "Engage fetch: no recent published posts for %s on %s/%s "
            "(%d published total, %d missing platform_post_id)",
            user.email, account.platform, account.username,
            all_published, no_post_id,
        )
        return 0

    # For Facebook/Instagram, use the selected Page's token instead of user token
    token = account.access_token
    if account.platform in ("facebook", "instagram"):
        meta = account.metadata or {}
        pages = meta.get("pages", [])
        if pages:
            selected_id = meta.get("selected_page_id")
            selected_page = (
                next((p for p in pages if p["id"] == selected_id), None)
                if selected_id else None
            ) or pages[0]
            token = selected_page.get("access_token", account.access_token)

    for post in recent_posts:
        try:
            comments = provider.get_comments(
                access_token=token,
                post_id=post.platform_post_id,
            )
            logger.info(
                "Engage fetch: %d comments on post %s (%s)",
                len(comments), post.platform_post_id, account.platform,
            )
            # Successful API call — clear any previous error counter
            account.clear_errors()

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
            # Token expired or permissions missing — permanent auth failure
            logger.error(
                "Auth error for %s account %s — strike %d: %s",
                account.platform, account.id,
                (account.metadata or {}).get("consecutive_errors", 0) + 1, e,
            )
            account.mark_error(str(e), status_code=401)
            if not account.is_active:
                _notify_account_deactivated(user, account, str(e))
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
            "   - HIGH: customer complaints, purchase intent, influencer mentions, negative sentiment, direct questions\n"
            "   - MEDIUM: genuine questions, detailed feedback, conversation starters, requests for info\n"
            "   - LOW: generic compliments, emoji-only reactions\n"
            "3. **is_spam**: true/false — is this automated spam or bot content?\n"
            "   IMPORTANT: Short messages are NOT spam. Questions like 'How?', 'Share the link', "
            "'Tell me more', 'I want this' are genuine engagement — mark them is_spam=false. "
            "Only mark as spam: promotional links, bot-generated gibberish, or clearly automated messages.\n\n"
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
            model=get_model_for_task("engage.analyze", user=user),
            json_mode=True,
            temperature=0.1,
            max_tokens=1500,
        )

        try:
            result = parse_llm_json(response.content)
            analyses = {a["id"]: a for a in result.get("analyses", [])}
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Failed to parse interaction analysis for user %s: %s", user.email, e)
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
    # Priority: 1) comments on fresh posts (<1hr, algorithm velocity boost),
    #           2) flagged, 3) new with sentiment, skip spam/ignored
    needs_reply = (
        Interaction.objects.filter(
            user=user,
            ai_suggested_reply="",
        )
        .exclude(status__in=[Interaction.Status.IGNORED, Interaction.Status.AI_REPLIED, Interaction.Status.USER_REPLIED])
        .exclude(sentiment="")
        .select_related("social_account", "post")
        .order_by(
            # Fresh-post comments first (algorithm velocity), then flagged, then recency
            _reply_priority_ordering(),
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
        batch_interactions = list(needs_reply)

        # Batch generate replies in a single LLM call instead of N individual calls.
        # Returns structured payloads now (Engage v2) — persist confidence,
        # intent, and safety_flags onto the Interaction so the engage_routing
        # layer can decide auto-send vs draft.
        payloads = _generate_replies_batch(batch_interactions, brand_voice, company)

        # Lazy import to keep this module free of routing logic during pure
        # generation. Routing decisions belong in auto_respond / engage tasks.
        from apps.agents.engage_routing import safety_check, SafetyContext

        for interaction, payload in zip(batch_interactions, payloads):
            reply_text = payload.get("reply") or ""
            if not reply_text:
                continue

            ctx = SafetyContext(
                reply_text=reply_text,
                intent=payload.get("intent", "other"),
                post_has_cta_url=bool(
                    interaction.post and (interaction.post.cta_url or "").strip()
                ),
            )
            flags = safety_check(ctx)

            interaction.ai_suggested_reply = reply_text
            interaction.ai_confidence = payload.get("confidence", 0.0)
            interaction.ai_intent = payload.get("intent", "other")
            interaction.safety_flags = flags
            interaction.save(update_fields=[
                "ai_suggested_reply", "ai_confidence", "ai_intent", "safety_flags",
            ])
            total_generated += 1

            # Create lead from purchase-intent interactions
            try:
                from apps.leads.bridges import create_lead_from_engage_intent
                create_lead_from_engage_intent(interaction)
            except Exception:
                logger.debug("Lead bridge skipped for interaction %s", interaction.pk)

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


def _reply_priority_ordering():
    """
    SQL ordering that prioritizes algorithm-critical replies:
    0 = comment on a post published < 1 hour ago (creator reply velocity = algorithm boost)
    1 = flagged interactions
    2 = new interactions
    3 = everything else
    """
    from django.db.models import Case, Value, When, IntegerField, Q
    one_hour_ago = timezone.now() - timedelta(hours=1)
    return Case(
        When(
            Q(post__published_at__gte=one_hour_ago) & Q(status=Interaction.Status.NEW),
            then=Value(0),
        ),
        When(status=Interaction.Status.FLAGGED, then=Value(1)),
        When(status=Interaction.Status.NEW, then=Value(2)),
        default=Value(3),
        output_field=IntegerField(),
    )


def _generate_replies_batch(interactions, brand_voice, company):
    """Generate replies for multiple interactions in a single LLM call.

    Returns a list of payload dicts (same order as interactions). Each
    payload has the shape returned by `_generate_single_reply` —
    {reply, confidence, intent, action, reasoning} (Engage v2, Phase 1 W2).

    Falls back to per-interaction generation on parse failure.
    """
    if not interactions:
        return []
    if len(interactions) == 1:
        try:
            return [_generate_single_reply(interactions[0], brand_voice, company)]
        except Exception as e:
            logger.warning("Single reply gen failed: %s", e)
            return [_empty_payload()]

    reply_learning = _get_reply_edit_patterns(interactions[0].user)

    # Product catalog awareness for replies
    from apps.products.utils import get_product_context
    product_ctx = get_product_context(interactions[0].user)
    product_instruction = ""
    if product_ctx:
        product_instruction = (
            "\n\nPRODUCT AWARENESS:\n"
            "When someone asks about products, prices, or availability, use this catalog:\n"
            f"{product_ctx}\n"
            "If a product is out of stock, suggest in-stock alternatives. "
            "Never confirm availability for out-of-stock items.\n"
        )

    system_prompt = (
        f"You are the community manager for {company}. "
        f"Your brand voice: {brand_voice}\n\n"
        "RULES:\n"
        "- Be genuine, not corporate. Sound human.\n"
        "- Match the energy of each message.\n"
        "- Keep replies concise — this is social media.\n"
        "- If it's a question, answer directly. If praise, acknowledge.\n"
        "- NEVER be defensive or dismissive.\n\n"
        f"{product_instruction}"
        "Generate a reply for EACH interaction below. Respond with a JSON "
        "array of objects, one per interaction in the same order:\n"
        "[\n"
        "  {\n"
        '    "reply":      "<the actual reply text>",\n'
        '    "confidence": <float 0.0-1.0>,\n'
        '    "intent":     "<hours | booking | pricing | complaint | praise | spam | other>",\n'
        '    "action":     "<reply | escalate | no_reply>",\n'
        '    "reasoning":  "<one sentence>"\n'
        "  },\n"
        "  ...\n"
        "]\n\n"
        "Confidence calibration:\n"
        "- 0.90+: factual question with clear answer (hours, location)\n"
        "- 0.70-0.89: clear praise/booking you can answer in brand voice\n"
        "- 0.50-0.69: ambiguous — recommend draft\n"
        "- <0.50: complex / sensitive — escalate"
    )

    interaction_descriptions = []
    for i, interaction in enumerate(interactions):
        platform = interaction.social_account.platform if interaction.social_account else "social media"
        post_ctx = ""
        if interaction.post:
            post_ctx = f"\nOriginal post: \"{interaction.post.content_text[:150]}...\""
        interaction_descriptions.append(
            f"--- Interaction {i + 1} ({platform}) ---\n"
            f"Type: {interaction.interaction_type} | Sentiment: {interaction.sentiment}\n"
            f"From: {interaction.author_name}\n"
            f"Message: \"{interaction.content}\""
            f"{post_ctx}"
        )

    prompt = "\n\n".join(interaction_descriptions)
    if reply_learning:
        prompt += f"\n\n{reply_learning}"
    prompt += "\n\nGenerate a reply for each interaction."

    try:
        response = generate(
            prompt=prompt, system=system_prompt,
            model=get_model_for_task("engage.reply", user=interactions[0].user),
            json_mode=True, temperature=0.6,
            max_tokens=250 * len(interactions),
        )
        results = parse_llm_json(response.content)

        if isinstance(results, list) and len(results) == len(interactions):
            payloads = []
            for r in results:
                if not isinstance(r, dict):
                    # Older models may have returned a bare string per item.
                    payloads.append({
                        "reply": str(r).strip(),
                        "confidence": 0.3,
                        "intent": "other",
                        "action": "reply",
                        "reasoning": "Non-dict element in batch response",
                    })
                    continue
                reply = (r.get("reply") or "").strip()
                if reply.startswith('"') and reply.endswith('"'):
                    reply = reply[1:-1]
                try:
                    confidence = max(0.0, min(1.0, float(r.get("confidence", 0.5))))
                except (TypeError, ValueError):
                    confidence = 0.5
                intent = (r.get("intent") or "other").lower().strip()
                if intent not in {"hours", "booking", "pricing", "complaint", "praise", "spam", "other"}:
                    intent = "other"
                action = (r.get("action") or "reply").lower().strip()
                if action not in {"reply", "escalate", "no_reply"}:
                    action = "reply"
                payloads.append({
                    "reply": reply,
                    "confidence": confidence,
                    "intent": intent,
                    "action": action,
                    "reasoning": (r.get("reasoning") or "").strip(),
                })
            return payloads

        logger.warning("Batch replies returned %d for %d interactions, falling back",
                       len(results) if isinstance(results, list) else 0, len(interactions))
    except Exception as e:
        logger.warning("Batch reply generation failed: %s, falling back to per-interaction", e)

    # Fallback: per-interaction
    payloads = []
    for interaction in interactions:
        try:
            payloads.append(_generate_single_reply(interaction, brand_voice, company))
        except Exception as e:
            logger.warning("Reply gen failed for interaction %s: %s", interaction.id, e)
            payloads.append(_empty_payload())
    return payloads


def _generate_single_reply(interaction, brand_voice, company):
    """Generate a reply for a single interaction.

    Returns dict {reply, confidence, intent, action, reasoning} (Engage v2,
    Phase 1 W2 May 2026). Callers that previously expected a plain string
    should pass the result through `reply_payload_to_text()` for backwards
    compat, or read `result["reply"]` directly.

    The structured response feeds `engage_routing.route_reply` to decide
    whether the reply auto-sends, queues as a draft, or escalates.
    """
    platform = interaction.social_account.platform if interaction.social_account else "social media"
    post_context = ""
    if interaction.post:
        post_context = f"\nOriginal post they're responding to:\n\"{interaction.post.content_text[:200]}...\""

    # Intelligence: learn from past reply edits
    reply_learning = _get_reply_edit_patterns(interaction.user)
    # Intelligence: learn from past auto-send corrections (W2 May 2026)
    corrections = _recent_corrections_for_brand(interaction.user)

    # Product catalog awareness
    from apps.products.utils import get_product_context
    product_ctx = get_product_context(interaction.user)
    product_instruction = ""
    if product_ctx:
        product_instruction = (
            "\n\nPRODUCT AWARENESS:\n"
            "If someone asks about products/prices/availability, reference this catalog:\n"
            f"{product_ctx}\n"
        )

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
        f"{product_instruction}"
        f"{corrections + chr(10) + chr(10) if corrections else ''}"
        "Respond with valid JSON only — no markdown, no preamble:\n"
        "{\n"
        '  "reply":      "<the actual reply text ready to send>",\n'
        '  "confidence": <float 0.0-1.0 — how sure are you this reply is correct?>,\n'
        '  "intent":     "<one of: hours, booking, pricing, complaint, praise, spam, other>",\n'
        '  "action":     "<one of: reply, escalate, no_reply>",\n'
        '  "reasoning":  "<one sentence explaining your confidence>"\n'
        "}\n\n"
        "Confidence calibration:\n"
        "- 0.90+: factual question with clear answer in brand profile (hours, location)\n"
        "- 0.70-0.89: clear praise/booking request you can answer in brand voice\n"
        "- 0.50-0.69: ambiguous but salvageable — recommend draft\n"
        "- <0.50: complex / sensitive / off-topic — escalate to human"
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
        model=get_model_for_task("engage.reply", user=interaction.user),
        json_mode=True,
        temperature=0.6,
        max_tokens=400,
    )

    return _parse_reply_payload(response.content)


def _parse_reply_payload(raw):
    """Defensively parse the LLM JSON. Always returns a usable dict.

    If the LLM didn't return valid JSON (rare with json_mode=True but happens
    on degraded models), fall back to treating the whole content as the reply
    text with low confidence so the routing escalates it.
    """
    import json

    if not raw:
        return _empty_payload()

    text = raw.strip()
    # Some models still wrap JSON in ```json ... ``` fences — strip them.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # Not JSON — assume the whole thing is the reply, low confidence
        return {
            "reply": text[:400],
            "confidence": 0.3,
            "intent": "other",
            "action": "reply",
            "reasoning": "LLM returned non-JSON; routed as low-confidence draft",
        }

    reply = (parsed.get("reply") or "").strip()
    if reply.startswith('"') and reply.endswith('"'):
        reply = reply[1:-1]

    try:
        confidence = float(parsed.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    intent = (parsed.get("intent") or "other").lower().strip()
    if intent not in {"hours", "booking", "pricing", "complaint", "praise", "spam", "other"}:
        intent = "other"

    action = (parsed.get("action") or "reply").lower().strip()
    if action not in {"reply", "escalate", "no_reply"}:
        action = "reply"

    return {
        "reply": reply,
        "confidence": confidence,
        "intent": intent,
        "action": action,
        "reasoning": (parsed.get("reasoning") or "").strip(),
    }


def _empty_payload():
    return {
        "reply": "",
        "confidence": 0.0,
        "intent": "other",
        "action": "no_reply",
        "reasoning": "Empty LLM response",
    }


def reply_payload_to_text(payload):
    """Backwards-compat shim — extract just the reply text from a payload.

    Use this anywhere old code assumed `_generate_single_reply` returned a
    plain string. New code should read the full dict so it can pass
    confidence + intent into `engage_routing.route_reply`.
    """
    if isinstance(payload, str):
        return payload
    return (payload or {}).get("reply", "")


# ─── Auto-Respond ────────────────────────────────────────────────────────────

def auto_respond(user):
    """Route AI replies through engage_routing — Engage Agent v2 (W2 May 2026).

    Replaces the old "always queue for review" behavior. Each candidate
    interaction's confidence + safety_flags + the user's autonomy level
    decide whether to auto-send, draft for review, or escalate.

    Gated by `settings.ENGAGE_GRADUATED_AUTONOMY_ENABLED` — even when the
    routing returns AUTO_SEND, we fall back to DRAFT_FOR_REVIEW until that
    flag flips. The new code path is exercised on every cycle either way
    so bugs surface before the flag goes live.

    Returns a dict summary: {"auto_sent", "drafted", "escalated", "skipped"}.
    """
    from django.conf import settings
    from apps.agents.engage_routing import (
        RoutingAction,
        route_reply,
        clamp_level_to_plan,
    )

    profile = user.profile

    # OFF disables the agent entirely — same as the legacy auto_engage=False
    if profile.engage_autonomy_level == "off":
        return {"auto_sent": 0, "drafted": 0, "escalated": 0, "skipped": 0}

    # Emergency pause halts all autonomous agent activity
    if profile.emergency_pause:
        logger.info("EMERGENCY PAUSE: Engage agent skipping auto-respond for %s", user.email)
        return {"auto_sent": 0, "drafted": 0, "escalated": 0, "skipped": 0}

    config = AgentConfig.objects.filter(user=user, agent_type="engage").first()
    if config and not config.is_active:
        return {"auto_sent": 0, "drafted": 0, "escalated": 0, "skipped": 0}

    # Defence in depth: clamp the user's level to whatever their plan allows.
    # A plan downgrade between cycles must not let a stale AGGRESSIVE flag
    # keep auto-sending.
    effective_level = clamp_level_to_plan(
        profile.engage_autonomy_level, (profile.plan or "starter").lower(),
    )

    autonomy_globally_enabled = bool(
        getattr(settings, "ENGAGE_GRADUATED_AUTONOMY_ENABLED", False)
    )

    # Candidates: comments + DMs with a draft reply ready. Sentiment filter
    # dropped — the routing layer + safety rails handle that better than the
    # old positive-only heuristic (complaints route to draft via safety
    # rails, praise can auto-send via high confidence).
    candidates = Interaction.objects.filter(
        user=user,
        interaction_type__in=["comment", "reply", "dm"],
        status=Interaction.Status.NEW,
    ).exclude(
        ai_suggested_reply="",
    ).select_related("social_account", "post")[:10]

    counts = {"auto_sent": 0, "drafted": 0, "escalated": 0, "skipped": 0}

    for interaction in candidates:
        confidence = interaction.ai_confidence or 0.0
        safety_flags = list(interaction.safety_flags or [])

        action = route_reply(
            autonomy_level=effective_level,
            confidence=confidence,
            safety_flags=safety_flags,
        )

        # When the global flag is off, AUTO_SEND decisions soft-fall through
        # to DRAFT_FOR_REVIEW. The new routing layer still ran so we catch
        # any bugs before flipping the flag.
        if action == RoutingAction.AUTO_SEND and not autonomy_globally_enabled:
            action = RoutingAction.DRAFT_FOR_REVIEW

        if action == RoutingAction.AUTO_SEND:
            send_result = _send_reply_to_platform(interaction)
            if send_result.get("ok"):
                interaction.status = Interaction.Status.AI_REPLIED
                interaction.ai_reply_sent = interaction.ai_suggested_reply
                interaction.responded_at = timezone.now()
                interaction.save(update_fields=[
                    "status", "ai_reply_sent", "responded_at",
                ])

                # Record the auto-send for audit + undo (W2 commit 3).
                # Single source of truth for the "what did the AI send for me"
                # surface and for Adapt Agent's correction-learning loop.
                from datetime import timedelta
                from apps.engage.models import EngageReply
                EngageReply.objects.create(
                    interaction=interaction,
                    sent_text=interaction.ai_suggested_reply,
                    confidence=confidence,
                    autonomy_level=effective_level,
                    safety_flags_snapshot=safety_flags,
                    platform_reply_id=send_result.get("platform_reply_id", ""),
                    can_undo_until=timezone.now() + timedelta(minutes=5),
                )

                counts["auto_sent"] += 1
                logger.info(
                    "ENGAGE auto-sent reply (conf=%.2f, level=%s) on %s/%s",
                    confidence, effective_level,
                    interaction.social_account.platform if interaction.social_account else "?",
                    interaction.id,
                )
            else:
                # Send failed — fall back to draft so the user can retry
                interaction.status = Interaction.Status.FLAGGED
                interaction.save(update_fields=["status"])
                counts["drafted"] += 1

        elif action == RoutingAction.DRAFT_FOR_REVIEW:
            interaction.status = Interaction.Status.FLAGGED
            interaction.save(update_fields=["status"])
            counts["drafted"] += 1

        elif action == RoutingAction.ESCALATE:
            interaction.status = Interaction.Status.FLAGGED
            interaction.save(update_fields=["status"])
            counts["escalated"] += 1

        else:  # RoutingAction.SKIP
            counts["skipped"] += 1

    # Single summary notification per cycle, only when there's something to
    # surface to the user.
    notify_count = counts["drafted"] + counts["escalated"]
    if notify_count or counts["auto_sent"]:
        from apps.notifications.models import Notification
        if counts["auto_sent"]:
            body_parts = [f"💬 {counts['auto_sent']} reply(s) auto-sent"]
            if notify_count:
                body_parts.append(f"{notify_count} need review")
            body = " · ".join(body_parts) + "."
        else:
            body = f"💬 {notify_count} AI-suggested replies ready for your review in the Engage inbox."
        Notification.create_for_user(user, "agent_action", body)
        logger.info(
            "Engage cycle for %s: %d auto-sent, %d drafted, %d escalated, %d skipped",
            user.email,
            counts["auto_sent"], counts["drafted"], counts["escalated"], counts["skipped"],
        )

    return counts


def _send_reply_to_platform(interaction) -> dict:
    """Actually post the reply to the social platform.

    Returns a dict {"ok": bool, "platform_reply_id": str, "error": str}.
    ``ok=True`` means the reply landed on the platform and ``platform_reply_id``
    carries the comment ID needed for later undo via provider.delete_comment.
    ``ok=False`` means the caller should fall back to DRAFT_FOR_REVIEW so the
    user can retry from the inbox.

    Only supports comment + reply auto-send for now. DMs are queued for
    review in v2 — full DM auto-send lands in Phase 3 work once the per-
    platform DM APIs are wired (some need elevated app review).
    """
    fail = lambda err: {"ok": False, "platform_reply_id": "", "error": err}

    account = interaction.social_account
    if not account or not account.is_active:
        logger.warning("ENGAGE auto-send: no active social_account on %s", interaction.id)
        return fail("No active social_account")

    # DMs are draft-only for now — surface to user even on AUTO_SEND verdict.
    if interaction.interaction_type == "dm":
        return fail("DM auto-send deferred until Phase 3")

    from apps.platforms.providers import get_provider
    provider = get_provider(account.platform)
    if not provider or not hasattr(provider, "post_comment"):
        logger.warning(
            "ENGAGE auto-send: provider %s has no post_comment method",
            account.platform,
        )
        return fail(f"Provider {account.platform} has no post_comment")

    try:
        # All providers' post_comment accept **kwargs after W2 commit 3.
        # We pass account so the FB / IG provider can resolve a Page-scoped
        # token if needed.
        result = provider.post_comment(
            access_token=account.access_token,
            post_id=interaction.platform_interaction_id,
            message=interaction.ai_suggested_reply,
            account=account,
        ) or {}
        if result.get("success"):
            return {
                "ok": True,
                "platform_reply_id": result.get("id", ""),
                "error": "",
            }
        err = result.get("error", "no result")
        logger.warning(
            "ENGAGE auto-send failed on %s/%s: %s",
            account.platform, interaction.id, err,
        )
        return fail(err)
    except Exception as exc:
        logger.exception(
            "ENGAGE auto-send crashed on %s/%s: %s",
            account.platform, interaction.id, exc,
        )
        return fail(str(exc))


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
    auto_respond_result = auto_respond(user)

    # auto_respond returns a counts dict; extract the int for the summary
    if isinstance(auto_respond_result, dict):
        auto_sent_count = auto_respond_result.get("auto_sent", 0)
        drafted = auto_respond_result.get("drafted", 0)
        escalated = auto_respond_result.get("escalated", 0)
    else:
        auto_sent_count = auto_respond_result or 0
        drafted = 0
        escalated = 0

    return {
        "fetched": fetched,
        "analyzed": analyzed,
        "replies_generated": replies,
        "auto_sent": auto_sent_count,
        "drafted": drafted,
        "escalated": escalated,
    }


def _notify_account_deactivated(user, account, error_detail):
    """Send a notification when an account is deactivated after repeated failures."""
    try:
        from apps.notifications.models import Notification

        platform_name = account.get_platform_display()
        Notification.create_for_user(
            user=user,
            notification_type=Notification.NotificationType.SYSTEM,
            message=(
                f"🔴 Your {platform_name} account (@{account.username}) was deactivated "
                f"after repeated API errors. Please reconnect it in Platforms to restore "
                f"publishing and engagement. Error: {error_detail[:200]}"
            ),
        )
    except Exception:
        logger.warning("Could not notify user about deactivated account %s", account)
