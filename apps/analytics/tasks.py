"""
Analytics Celery tasks — Competitor intelligence + metrics.
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="analyze-competitor")
def analyze_competitor_task(user_id, competitor_id):
    """Run AI analysis on a single competitor, then alert on high-priority insights."""
    from apps.accounts.models import User
    from apps.analytics.competitor_intel import analyze_competitor
    from apps.analytics.models import Competitor

    try:
        user = User.objects.get(id=user_id)
        competitor = Competitor.objects.get(id=competitor_id, user=user)
        analysis = analyze_competitor(user, competitor)
        if analysis:
            logger.info("Competitor analysis complete: %s for %s", competitor.name, user.email)
            _send_competitor_alerts(user, competitor, analysis)
            _auto_act_on_insights(user, competitor)
        return str(analysis.id) if analysis else None
    except Exception as e:
        logger.exception("analyze_competitor_task failed: %s", e)
        return None


def _send_competitor_alerts(user, competitor, analysis):
    """Create notifications for high-priority competitor insights."""
    from datetime import timedelta

    from apps.analytics.models import CompetitorInsight
    from apps.notifications.models import Notification

    recent_insights = CompetitorInsight.objects.filter(
        competitor=competitor,
        created_at__gte=timezone.now() - timedelta(minutes=10),
        priority="high",
    )

    for insight in recent_insights[:3]:
        message = f"🔔 Competitor alert: {competitor.name} — {insight.title}"
        try:
            Notification.create_for_user(
                user=user,
                notification_type=Notification.NotificationType.AGENT_ACTION,
                message=message,
            )
        except Exception:
            logger.exception("Failed to create competitor alert notification")


def _auto_act_on_insights(user, competitor):
    """
    Auto-create ContentSeeds from high-priority competitor insights that have
    suggested content ideas. Turns intelligence into action without manual clicks.

    Limits: max 1 auto-seed per competitor per analysis to avoid flooding.
    Only acts on insights that are HIGH priority and have a content idea.
    """
    from datetime import timedelta

    from apps.analytics.models import CompetitorInsight
    from apps.content.models import ContentSeed
    from apps.platforms.models import SocialAccount

    platforms = list(
        SocialAccount.objects.filter(user=user, is_active=True)
        .values_list("platform", flat=True)
    )
    if not platforms:
        return

    # Get recent high-priority insights with content ideas, not yet acted on
    insights = CompetitorInsight.objects.filter(
        user=user,
        competitor=competitor,
        priority="high",
        is_acted_on=False,
        is_dismissed=False,
        created_at__gte=timezone.now() - timedelta(minutes=10),
    ).exclude(
        suggested_content_idea=""
    ).order_by("-created_at")[:1]  # Max 1 per analysis

    for insight in insights:
        idea = (
            f"Competitive response — {competitor.name}: {insight.title}\n\n"
            f"{insight.suggested_content_idea}\n\n"
            f"Context: {insight.description[:300]}"
        )

        ContentSeed.objects.create(
            user=user,
            idea=idea,
            notes=f"Auto-created from competitor insight: {insight.title} ({competitor.name})",
            target_platforms=platforms[:3],
        )

        insight.is_acted_on = True
        insight.save(update_fields=["is_acted_on"])

        logger.info(
            "Auto-acted on competitor insight: %s — %s (user: %s)",
            competitor.name, insight.title, user.email,
        )


@shared_task(name="analyze-all-competitors")
def analyze_all_competitors():
    """
    Periodic task: analyze all active competitors for all users.
    Runs weekly via Celery Beat.
    """
    from datetime import timedelta

    from apps.accounts.models import User
    from apps.analytics.models import Competitor

    cutoff = timezone.now() - timedelta(days=6)  # Don't re-analyze within 6 days

    from django.db.models import Q
    competitors = Competitor.objects.filter(
        is_active=True,
    ).filter(
        Q(last_analyzed_at__isnull=True) | Q(last_analyzed_at__lt=cutoff)
    ).select_related("user")

    count = 0
    for comp in competitors:
        # Check user has active subscription (don't analyze for free users)
        profile = getattr(comp.user, "profile", None)
        if not profile:
            continue

        analyze_competitor_task.delay(str(comp.user_id), str(comp.id))
        count += 1

    logger.info("Queued %d competitor analyses", count)
    return count


# ══════════════════════════════════════════════════════════════════════════════
# SCREENSHOT TO COMPETE
# ══════════════════════════════════════════════════════════════════════════════


@shared_task(name="analytics.process_competitor_screenshot")
def process_competitor_screenshot(screenshot_id: str):
    """
    Analyze a competitor screenshot with AI vision → generate counter-posts.

    Pipeline: Screenshot → Vision AI analysis (brand, messaging, strategy) →
    match to existing competitor → generate counter-strategy → create ContentSeed
    with counter-posts in user's brand voice.
    """
    from django.utils import timezone
    from apps.analytics.models import CompetitorScreenshot, Competitor
    from apps.content.models import ContentSeed
    from apps.agents.models import AgentAction

    try:
        ss = CompetitorScreenshot.objects.select_related("user", "user__profile").get(pk=screenshot_id)
    except CompetitorScreenshot.DoesNotExist:
        logger.error("CompetitorScreenshot %s not found", screenshot_id)
        return {"error": "not_found"}

    user = ss.user
    profile = getattr(user, "profile", None)

    try:
        # ── Step 1: Vision Analysis ──
        ss.status = CompetitorScreenshot.Status.ANALYZING
        ss.save(update_fields=["status"])

        from apps.agents.llm_router import call_llm_vision
        import json

        brand_context = ""
        if profile:
            brand_context = f"My brand: Industry={profile.industry or 'general'}, Voice={profile.brand_voice or 'professional'}."

        vision_prompt = (
            "Analyze this screenshot of a competitor's social media post or ad.\n\n"
            f"{brand_context}\n"
            f"User notes: {ss.user_notes}\n\n"
            "Return a JSON object:\n"
            "- competitor_name: brand/business name visible in the screenshot\n"
            "- platform: which social platform this is from (instagram, facebook, twitter, etc.)\n"
            "- content_type: post, ad, story, reel, etc.\n"
            "- messaging: what message they're communicating (1-2 sentences)\n"
            "- visual_style: describe the visual design/style\n"
            "- cta: what call-to-action they use (if any)\n"
            "- strategy: what marketing strategy they're using (discount-led, social-proof, urgency, etc.)\n"
            "- strengths: list of 2-3 things they did well\n"
            "- weaknesses: list of 2-3 weaknesses or gaps\n"
            "- hashtags: any hashtags visible\n"
            "- counter_angle: how MY brand should respond — a specific angle that exploits their weaknesses\n"
            "Return ONLY valid JSON."
        )

        vision_response = call_llm_vision(
            prompt=vision_prompt,
            image_path=ss.image.path,
            task="competitor_screenshot",
            user=user,
        )

        try:
            analysis = json.loads(vision_response["text"])
        except (json.JSONDecodeError, KeyError):
            analysis = {"raw_response": vision_response.get("text", "")}

        ss.competitor_name = analysis.get("competitor_name", "Unknown")[:200]
        ss.analysis = analysis
        ss.save(update_fields=["competitor_name", "analysis"])

        # Try to match existing competitor
        if ss.competitor_name:
            existing = Competitor.objects.filter(
                user=user, name__icontains=ss.competitor_name,
            ).first()
            if existing:
                ss.competitor = existing
                ss.save(update_fields=["competitor"])

        # ── Step 2: Generate Counter-Posts ──
        ss.status = CompetitorScreenshot.Status.GENERATING
        ss.save(update_fields=["status"])

        counter_angle = analysis.get("counter_angle", "")
        weaknesses = analysis.get("weaknesses", [])
        messaging = analysis.get("messaging", "")

        ss.counter_strategy = (
            f"Competitor ({ss.competitor_name}) strategy: {analysis.get('strategy', 'unknown')}.\n"
            f"Their messaging: {messaging}\n"
            f"Weaknesses to exploit: {', '.join(weaknesses) if weaknesses else 'none identified'}.\n"
            f"Our angle: {counter_angle}"
        )

        # Create ContentSeed with counter-posts
        seed = ContentSeed.objects.create(
            user=user,
            idea=(
                f"Counter-post responding to {ss.competitor_name}'s {analysis.get('content_type', 'post')}.\n\n"
                f"Their angle: {messaging}\n"
                f"Our counter-angle: {counter_angle}\n\n"
                f"Exploit their gaps: {', '.join(weaknesses) if weaknesses else 'generic content'}.\n"
                f"Don't mention the competitor by name. Focus on our strengths."
            ),
            notes=f"[Screenshot to Compete] vs {ss.competitor_name}",
        )
        ss.counter_seed = seed
        ss.posts_generated = 1

        # Trigger content generation
        from apps.content.tasks import generate_from_seed
        generate_from_seed.delay(str(seed.pk))

        # ── Complete ──
        ss.status = CompetitorScreenshot.Status.COMPLETED
        ss.completed_at = timezone.now()
        ss.save()

        AgentAction.objects.create(
            user=user,
            agent_type="research",
            action_type="screenshot_to_compete",
            input_data={"competitor": ss.competitor_name, "notes": ss.user_notes[:200]},
            output_data={"analysis": analysis, "seed_id": str(seed.pk)},
            tokens_used=vision_response.get("tokens_used", 0),
            model_used=vision_response.get("model", ""),
        )

        logger.info("Screenshot analysis completed: %s vs %s", screenshot_id, ss.competitor_name)
        return {"status": "completed", "competitor": ss.competitor_name, "seed_id": str(seed.pk)}

    except Exception as e:
        logger.exception("Screenshot analysis %s failed: %s", screenshot_id, e)
        ss.status = CompetitorScreenshot.Status.FAILED
        ss.error_message = str(e)[:1000]
        ss.save(update_fields=["status", "error_message"])
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# PERFORMANCE TO EMAIL — Detect top performers → auto-generate email drafts
# ══════════════════════════════════════════════════════════════════════════════


@shared_task(name="analytics.detect_top_performers")
def detect_top_performers():
    """
    Periodic task: scan recent PostMetrics for posts that exceed 2x average
    engagement → create PerformanceRecycle records → generate email drafts.

    Run daily via Celery Beat.
    """
    from django.utils import timezone
    from django.db.models import Avg
    from apps.analytics.models import PostMetric, PerformanceRecycle
    from apps.content.models import Post
    from apps.agents.models import AgentAction

    MULTIPLIER_THRESHOLD = 2.0  # 2x average = worth recycling
    LOOKBACK_DAYS = 7

    cutoff = timezone.now() - timezone.timedelta(days=LOOKBACK_DAYS)
    detected = 0

    # Get all users who have recent metrics
    user_ids = (
        PostMetric.objects.filter(fetched_at__gte=cutoff)
        .values_list("post__user_id", flat=True)
        .distinct()
    )

    for user_id in user_ids:
        # Calculate user's average engagement rate
        avg_engagement = (
            PostMetric.objects.filter(
                post__user_id=user_id,
                fetched_at__gte=cutoff,
            ).aggregate(avg=Avg("engagement_rate"))["avg"]
        )

        if not avg_engagement or avg_engagement <= 0:
            continue

        # Find posts that exceed threshold
        threshold = float(avg_engagement) * MULTIPLIER_THRESHOLD
        top_metrics = (
            PostMetric.objects.filter(
                post__user_id=user_id,
                fetched_at__gte=cutoff,
                engagement_rate__gte=threshold,
            )
            .select_related("post")
            .order_by("-engagement_rate")[:3]  # Max 3 per user
        )

        for metric in top_metrics:
            post = metric.post
            # Skip if already recycled
            if PerformanceRecycle.objects.filter(source_post=post).exists():
                continue

            multiplier = round(float(metric.engagement_rate) / float(avg_engagement), 2)

            PerformanceRecycle.objects.create(
                user_id=user_id,
                source_post=post,
                post_metric=metric,
                performance_multiplier=multiplier,
                trigger_metric="engagement_rate",
                status=PerformanceRecycle.Status.DETECTED,
            )
            detected += 1

    logger.info("Performance recycling: detected %d top performers", detected)

    # Now generate email drafts for detected items
    pending = PerformanceRecycle.objects.filter(
        status=PerformanceRecycle.Status.DETECTED,
    ).select_related("source_post", "user", "user__profile")[:20]

    for recycle in pending:
        generate_recycle_email.delay(str(recycle.pk))

    return {"detected": detected}


@shared_task(name="analytics.generate_recycle_email")
def generate_recycle_email(recycle_id: str):
    """Generate an email draft from a top-performing post."""
    from django.utils import timezone
    from apps.analytics.models import PerformanceRecycle
    from apps.agents.models import AgentAction

    try:
        recycle = PerformanceRecycle.objects.select_related(
            "source_post", "user", "user__profile",
        ).get(pk=recycle_id)
    except PerformanceRecycle.DoesNotExist:
        return {"error": "not_found"}

    user = recycle.user
    post = recycle.source_post
    profile = getattr(user, "profile", None)

    try:
        recycle.status = PerformanceRecycle.Status.GENERATING
        recycle.save(update_fields=["status"])

        from apps.agents.llm_router import call_llm
        import json

        brand_context = ""
        if profile:
            brand_context = f"Brand voice: {profile.brand_voice or 'professional'}. Industry: {profile.industry or 'general'}."

        prompt = (
            "You are an email marketing expert. A social media post performed exceptionally well.\n"
            "Turn this post's topic into a deeper, value-packed email for subscribers.\n\n"
            f"Original post ({post.platform}): \"{post.content_text[:500]}\"\n"
            f"Performance: {recycle.performance_multiplier}x average engagement\n"
            f"{brand_context}\n\n"
            "Return JSON with:\n"
            "- subject: compelling email subject line (max 60 chars)\n"
            "- body_html: full email HTML body — expand on the post topic with more depth, tips, insights. 200-400 words.\n"
            "- reasoning: one sentence explaining why this post would make good email content\n"
            "Return ONLY valid JSON."
        )

        response = call_llm(prompt=prompt, task="performance_to_email", user=user, json_mode=True)

        try:
            result = json.loads(response["text"])
        except (json.JSONDecodeError, KeyError):
            result = {
                "subject": f"What our community loved: {post.content_text[:60]}",
                "body_html": f"<p>{post.content_text}</p>",
                "reasoning": "High engagement post recycled to email",
            }

        recycle.email_subject = result.get("subject", "")[:200]
        recycle.email_body_html = result.get("body_html", "")
        recycle.ai_reasoning = result.get("reasoning", "")
        recycle.status = PerformanceRecycle.Status.READY
        recycle.save()

        from apps.emails.automation import auto_email_enabled, send_performance_recycle

        if auto_email_enabled(user):
            send_performance_recycle(recycle)

        AgentAction.objects.create(
            user=user,
            agent_type="strategist",
            action_type="performance_to_email",
            input_data={"post_id": str(post.pk), "multiplier": float(recycle.performance_multiplier)},
            output_data={"subject": recycle.email_subject},
            tokens_used=response.get("tokens_used", 0),
            model_used=response.get("model", ""),
        )

        logger.info("Recycle email generated for post %s (%sx)", post.pk, recycle.performance_multiplier)
        return {"status": "ready", "subject": recycle.email_subject}

    except Exception as e:
        logger.exception("Recycle email generation failed for %s: %s", recycle_id, e)
        recycle.status = PerformanceRecycle.Status.DETECTED  # Reset to retry
        recycle.save(update_fields=["status"])
        return {"error": str(e)}
