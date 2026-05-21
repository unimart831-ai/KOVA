"""
AI Content Autopilot — weekly content planning with preview-before-generate.

Pipeline:
  1. Strategist plans the week (preview) → user reviews every topic
  2. User approves the strategy → Create Agent generates posts
  3. Adapt Agent schedules posts only when auto_approve_posts is enabled
  4. User reviews posts in Studio when auto-approve is off
  5. Weekly review email summarizes performance

Runs every Monday via Celery Beat for users with autopilot_enabled.
Does NOT require auto_approve_posts — that only controls auto-scheduling/publishing.
"""

import logging
from datetime import date, timedelta

from celery import shared_task
from django.utils import timezone

from apps.utils.locks import single_run

logger = logging.getLogger(__name__)

AUTOPILOT_ACTIVE_STATUSES = (
    "pending_review",
    "planning",
    "generating",
    "scheduling",
    "active",
)


def get_autopilot_users():
    """Users who receive automatic weekly plan previews."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.filter(
        is_active=True,
        profile__autopilot_enabled=True,
        profile__emergency_pause=False,
    ).select_related("profile")


def get_plan_posts(plan):
    """Posts belonging to an autopilot plan (FK-first, notes-prefix fallback)."""
    from apps.content.models import Post

    if plan.seeds.exists():
        return (
            Post.objects.filter(user=plan.user, seed__weekly_plan=plan)
            .select_related("social_account")
            .order_by("scheduled_at", "-created_at")
        )
    return (
        Post.objects.filter(
            user=plan.user,
            created_at__date__gte=plan.week_start,
            created_at__date__lte=plan.week_end,
            seed__notes__startswith="[Autopilot]",
        )
        .select_related("social_account")
        .order_by("scheduled_at", "-created_at")
    )


def get_plan_live_stats(plan):
    """Live counts for dashboard — not persisted until week-end email."""
    from apps.content.models import Post

    posts = get_plan_posts(plan)
    return {
        "posts_generated": posts.count(),
        "posts_published": posts.filter(status=Post.Status.PUBLISHED).count(),
        "posts_pending": posts.filter(
            status__in=[Post.Status.DRAFT, Post.Status.PENDING_APPROVAL],
        ).count(),
        "posts_scheduled": posts.filter(
            status__in=[Post.Status.APPROVED, Post.Status.SCHEDULED],
        ).count(),
        "posts_failed": posts.filter(status=Post.Status.FAILED).count(),
    }


def _next_monday():
    """Return the next Monday (or today if today is Monday)."""
    today = date.today()
    days_ahead = 0 - today.weekday()
    if days_ahead < 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


def _resolve_autopilot_platforms(user, connected_platforms, profile):
    """Honor profile.autopilot_platforms when set."""
    chosen = profile.autopilot_platforms if profile else []
    if chosen:
        return [p for p in chosen if p in connected_platforms]
    return connected_platforms


@shared_task(name="content.plan_weekly_autopilot", soft_time_limit=30 * 60, time_limit=35 * 60)
@single_run("content.plan_weekly_autopilot", timeout=40 * 60)
def plan_weekly_autopilot():
    """
    Weekly orchestrator: create plan PREVIEWS for autopilot users.
    Generation happens only after the user approves the strategy.
    """
    week_start = _next_monday()
    planned = 0

    for user in get_autopilot_users():
        try:
            plan_user_week.delay(str(user.pk), week_start.isoformat())
            planned += 1
        except Exception as e:
            logger.error("Failed to queue autopilot preview for user %s: %s", user.email, e)

    logger.info("Autopilot: queued weekly previews for %d users", planned)
    return {"users_queued": planned}


@shared_task(name="content.plan_user_week", soft_time_limit=15 * 60, time_limit=18 * 60)
def plan_user_week(user_id: str, week_start_iso: str):
    """
    Step 1 only: Strategist creates a weekly plan preview.
    Stops at PENDING_REVIEW — user must approve before posts are generated.
    """
    from django.contrib.auth import get_user_model
    from apps.content.models import WeeklyContentPlan
    from apps.agents.models import AgentAction
    from apps.notifications.models import Notification
    from apps.platforms.models import SocialAccount

    User = get_user_model()
    try:
        user = User.objects.select_related("profile").get(pk=user_id)
    except User.DoesNotExist:
        return {"error": "user_not_found"}

    week_start = date.fromisoformat(week_start_iso)
    week_end = week_start + timedelta(days=6)
    profile = user.profile

    if profile.emergency_pause:
        return {"error": "emergency_pause"}

    plan, created = WeeklyContentPlan.objects.get_or_create(
        user=user,
        week_start=week_start,
        defaults={"week_end": week_end, "status": WeeklyContentPlan.Status.PLANNING},
    )

    if not created and plan.status not in (
        WeeklyContentPlan.Status.FAILED,
        WeeklyContentPlan.Status.CANCELLED,
    ):
        return {"skipped": "plan_already_exists", "plan_id": str(plan.pk), "status": plan.status}

    if not created:
        plan.status = WeeklyContentPlan.Status.PLANNING
        plan.error_message = ""
        plan.week_end = week_end
        plan.save(update_fields=["status", "error_message", "week_end"])

    try:
        connected = list(
            SocialAccount.objects.filter(user=user, is_active=True)
            .values_list("platform", flat=True)
        )
        if not connected:
            plan.status = WeeklyContentPlan.Status.FAILED
            plan.error_message = "No connected platforms"
            plan.save(update_fields=["status", "error_message"])
            return {"error": "no_platforms"}

        platforms = _resolve_autopilot_platforms(user, connected, profile)
        if not platforms:
            plan.status = WeeklyContentPlan.Status.FAILED
            plan.error_message = "No autopilot target platforms match connected accounts"
            plan.save(update_fields=["status", "error_message"])
            return {"error": "no_target_platforms"}

        posts_per_week = profile.autopilot_posts_per_week or 5
        strategy = _strategist_plan_week(
            user, profile, platforms, week_start, posts_per_week,
        )
        plan.strategy = strategy
        plan.strategy_reasoning = strategy.get("reasoning", "")
        plan.status = WeeklyContentPlan.Status.PENDING_REVIEW
        plan.save(update_fields=["strategy", "strategy_reasoning", "status"])

        AgentAction.objects.create(
            user=user,
            agent_type="strategist",
            action_type="weekly_autopilot_preview",
            description=f"Prepared autopilot preview for week of {week_start}",
            status=AgentAction.ActionStatus.COMPLETED,
            input_data={"week_start": week_start_iso, "platforms": platforms},
            output_data={
                "strategy_theme": strategy.get("theme", ""),
                "topics": len(strategy.get("daily_topics", [])),
            },
        )

        topic_count = len(strategy.get("daily_topics", []))
        Notification.create_for_user(
            user,
            Notification.NotificationType.SYSTEM,
            f"Your weekly content plan is ready: {topic_count} topic{'s' if topic_count != 1 else ''} "
            f"for the week of {week_start.strftime('%b %d')}. Review and approve to generate posts.",
        )

        logger.info("Autopilot preview ready for %s (week %s)", user.email, week_start)
        return {
            "plan_id": str(plan.pk),
            "status": "pending_review",
            "topics": topic_count,
            "theme": strategy.get("theme", ""),
        }

    except Exception as e:
        logger.exception("Autopilot preview failed for user %s: %s", user.email, e)
        plan.status = WeeklyContentPlan.Status.FAILED
        plan.error_message = str(e)[:1000]
        plan.save(update_fields=["status", "error_message"])
        return {"error": str(e)}


@shared_task(name="content.execute_autopilot_plan", soft_time_limit=20 * 60, time_limit=25 * 60)
def execute_autopilot_plan(plan_id: str):
    """
    Step 2: User approved the preview — generate seeds, posts, and optionally schedule.

    auto_approve_posts controls whether Adapt auto-schedules. When off, posts land
    in Studio as pending approval — autopilot still delivers value without autonomy.
    """
    from django.contrib.auth import get_user_model
    from apps.content.models import ContentSeed, Post, WeeklyContentPlan
    from apps.agents.models import AgentAction
    from apps.agents.create_agent import run_create_agent
    from apps.agents.adapt_agent import auto_schedule_post
    from apps.notifications.models import Notification
    from apps.platforms.models import SocialAccount

    User = get_user_model()
    try:
        plan = WeeklyContentPlan.objects.select_related("user", "user__profile").get(pk=plan_id)
    except WeeklyContentPlan.DoesNotExist:
        return {"error": "plan_not_found"}

    user = plan.user
    profile = user.profile

    if plan.status != WeeklyContentPlan.Status.PENDING_REVIEW:
        return {"error": "invalid_status", "status": plan.status}

    if profile.emergency_pause:
        return {"error": "emergency_pause"}

    connected = list(
        SocialAccount.objects.filter(user=user, is_active=True)
        .values_list("platform", flat=True)
    )
    platforms = _resolve_autopilot_platforms(user, connected, profile)
    strategy = plan.strategy or {}
    posts_per_week = profile.autopilot_posts_per_week or 5
    daily_topics = strategy.get("daily_topics", [])[:posts_per_week]

    plan.status = WeeklyContentPlan.Status.GENERATING
    plan.error_message = ""
    plan.save(update_fields=["status", "error_message"])

    try:
        seeds = []
        for topic in daily_topics:
            raw_target = topic.get("platforms", platforms[:2])
            if isinstance(raw_target, str):
                target = [raw_target]
            else:
                target = [p for p in raw_target if p in connected] or platforms[:2]

            seed = ContentSeed.objects.create(
                user=user,
                idea=topic.get("topic", ""),
                notes=(
                    f"[Autopilot] Week of {plan.week_start} — "
                    f"{topic.get('intent', '')}"
                ),
                target_platforms=target,
                target_intent=topic.get("intent", ""),
                weekly_plan=plan,
            )
            seeds.append(seed)

        plan.seeds_created = len(seeds)
        plan.save(update_fields=["seeds_created"])

        total_posts = 0
        auto_approve = profile.auto_approve_posts

        for seed in seeds:
            try:
                posts = run_create_agent(seed)
                total_posts += len(posts)

                if auto_approve:
                    for post in posts:
                        try:
                            auto_schedule_post(post)
                        except Exception as e:
                            logger.warning(
                                "Autopilot: auto-schedule failed for post %s: %s",
                                post.id, e,
                            )
            except Exception as e:
                logger.error("Autopilot: seed generation failed for %s: %s", seed.id, e)
                seed.status = ContentSeed.SeedStatus.FAILED
                seed.error_message = str(e)[:500]
                seed.save(update_fields=["status", "error_message", "updated_at"])

        plan.posts_generated = total_posts
        plan.status = WeeklyContentPlan.Status.ACTIVE
        plan.save(update_fields=["posts_generated", "status"])

        AgentAction.objects.create(
            user=user,
            agent_type="strategist",
            action_type="weekly_autopilot_execute",
            description=(
                f"Executed autopilot plan for {plan.week_start}: "
                f"{len(seeds)} seeds → {total_posts} posts"
            ),
            status=AgentAction.ActionStatus.COMPLETED,
            output_data={
                "plan_id": str(plan.pk),
                "seeds": len(seeds),
                "posts": total_posts,
                "auto_approve": auto_approve,
            },
        )

        if auto_approve:
            msg = (
                f"Autopilot generated {total_posts} posts for the week of "
                f"{plan.week_start.strftime('%b %d')} and scheduled them automatically."
            )
        else:
            msg = (
                f"Autopilot generated {total_posts} posts for the week of "
                f"{plan.week_start.strftime('%b %d')}. Review and approve them in Studio."
            )
        Notification.create_for_user(
            user, Notification.NotificationType.POSTS_GENERATED, msg,
        )

        logger.info(
            "Autopilot executed for %s: %d seeds → %d posts (auto_approve=%s)",
            user.email, len(seeds), total_posts, auto_approve,
        )
        return {
            "plan_id": str(plan.pk),
            "seeds": len(seeds),
            "posts": total_posts,
            "auto_approve": auto_approve,
        }

    except Exception as e:
        logger.exception("Autopilot execute failed for plan %s: %s", plan.pk, e)
        plan.status = WeeklyContentPlan.Status.FAILED
        plan.error_message = str(e)[:1000]
        plan.save(update_fields=["status", "error_message"])
        return {"error": str(e)}


def _strategist_plan_week(user, profile, platforms, week_start, posts_per_week=5):
    """
    Have the Strategist agent create a weekly content plan based on
    the user's brand, audience, recent performance, and connected platforms.
    """
    from apps.agents.llm import generate, get_model_for_task, parse_llm_json
    from apps.analytics.models import PostMetric
    from apps.content.models import Post

    recent_posts = (
        Post.objects.filter(user=user, status=Post.Status.PUBLISHED)
        .order_by("-published_at")[:10]
        .values_list("content_text", "platform", "published_at")
    )
    recent_summary = "\n".join(
        f"- [{p[1]}] {p[0][:100]}..." for p in recent_posts
    ) or "No recent posts."

    top_metrics = (
        PostMetric.objects.filter(post__user=user)
        .order_by("-engagement_rate")[:5]
        .select_related("post")
    )
    performance_context = "\n".join(
        f"- {m.post.content_text[:80]}... ({m.engagement_rate:.1f}% engagement, {m.impressions} impressions)"
        for m in top_metrics
    ) or "No performance data yet."

    brand_voice = profile.brand_voice or "professional"
    industry = profile.industry or "general"
    company = profile.company_name or "my business"
    week_label = week_start.strftime("%B %d, %Y")
    days = [(week_start + timedelta(days=i)).strftime("%A %b %d") for i in range(7)]

    prompt = f"""You are a social media strategist for an African SME.

BUSINESS: {company}
INDUSTRY: {industry}
BRAND VOICE: {brand_voice}
PLATFORMS: {', '.join(platforms)}

RECENT POSTS:
{recent_summary}

TOP PERFORMING CONTENT:
{performance_context}

Create a weekly content plan for the week of {week_label}.

Rules:
- Plan exactly {posts_per_week} posts across the week (not every day needs a post — rest days are OK)
- Mix content intents: problem_awareness, solution, proof, offer, authority
- Vary platforms — don't post the same thing everywhere
- Each topic should be a specific, actionable content idea (not generic)
- Consider what performed well and do more of it
- Only use platforms from the PLATFORMS list above

Return ONLY valid JSON:
{{
  "theme": "One-line weekly theme",
  "reasoning": "Why this strategy fits this week",
  "content_mix": {{"problem_awareness": 1, "solution": 2, "proof": 1, "offer": 1, "authority": 1}},
  "daily_topics": [
    {{
      "day": "{days[0]}",
      "topic": "Specific content topic/idea",
      "intent": "problem_awareness",
      "platforms": ["instagram", "linkedin"],
      "notes": "Any special angle or format suggestion"
    }}
  ]
}}"""

    model = get_model_for_task("strategist.brief")
    response = generate(
        prompt=prompt,
        system="You are the Chief Strategist AI for an African SME social media platform. Return JSON only.",
        model=model,
        temperature=0.8,
        max_tokens=2048,
        json_mode=True,
    )

    parsed = parse_llm_json(response.content) if response.content else None
    if not parsed or "daily_topics" not in parsed:
        fallback_topics = [
            {
                "day": days[i % 7],
                "topic": f"Share a {['tip', 'story', 'product highlight', 'customer win', 'behind the scenes'][i % 5]} about {company}",
                "intent": ["problem_awareness", "solution", "proof", "offer", "authority"][i % 5],
                "platforms": platforms[:2],
                "notes": "",
            }
            for i in range(min(posts_per_week, 5))
        ]
        return {
            "theme": "Mixed content week",
            "reasoning": "Fallback plan — AI strategy unavailable",
            "content_mix": {"problem_awareness": 1, "solution": 1, "proof": 1, "offer": 1, "authority": 1},
            "daily_topics": fallback_topics,
        }

    parsed["daily_topics"] = parsed.get("daily_topics", [])[:posts_per_week]
    return parsed


# ─── Weekly Review Email ──────────────────────────────────────────────────────

@shared_task(name="content.send_autopilot_review_emails", soft_time_limit=10 * 60, time_limit=12 * 60)
@single_run("content.send_autopilot_review_emails", timeout=15 * 60)
def send_autopilot_review_emails():
    """
    Send weekly review emails for completed autopilot plans.
    Runs daily via Celery Beat.
    """
    from apps.content.models import Post, WeeklyContentPlan
    from apps.analytics.models import PostMetric
    from django.db.models import Avg, Sum

    plans = WeeklyContentPlan.objects.filter(
        status=WeeklyContentPlan.Status.ACTIVE,
        review_email_sent=False,
        week_end__lte=date.today(),
    ).select_related("user", "user__profile")

    sent = 0
    for plan in plans[:100]:
        try:
            posts = get_plan_posts(plan)
            published = posts.filter(status=Post.Status.PUBLISHED)
            metrics = PostMetric.objects.filter(
                post__in=published,
            ).aggregate(
                total_impressions=Sum("impressions"),
                total_likes=Sum("likes"),
                total_comments=Sum("comments"),
                total_shares=Sum("shares"),
                avg_engagement=Avg("engagement_rate"),
            )

            plan.posts_published = published.count()
            plan.posts_generated = posts.count()
            plan.posts_failed = posts.filter(status=Post.Status.FAILED).count()
            plan.performance_summary = {
                k: float(v) if v else 0
                for k, v in metrics.items()
            }
            plan.status = WeeklyContentPlan.Status.COMPLETED
            plan.completed_at = timezone.now()

            _send_review_email(plan, published, metrics)

            plan.review_email_sent = True
            plan.review_email_sent_at = timezone.now()
            plan.save()
            sent += 1

        except Exception as e:
            logger.error("Autopilot review email failed for plan %s: %s", plan.pk, e)

    logger.info("Autopilot: sent %d review emails", sent)
    return {"emails_sent": sent}


def _send_review_email(plan, published_posts, metrics):
    """Send the weekly performance review email."""
    try:
        import resend
        from django.conf import settings as django_settings

        if not getattr(django_settings, "RESEND_API_KEY", ""):
            logger.warning("RESEND_API_KEY not set — skipping autopilot review email")
            return

        resend.api_key = django_settings.RESEND_API_KEY
        user = plan.user
        theme = plan.strategy.get("theme", "your weekly content")
        impressions = metrics.get("total_impressions") or 0
        engagement = metrics.get("avg_engagement") or 0
        published_count = published_posts.count()

        top_post = None
        if published_posts.exists():
            top = published_posts.order_by("-metrics__engagement_rate").first()
            if top:
                top_post = top.content_text[:150]

        subject = f"Your Kova Autopilot Week: {published_count} posts, {impressions:,.0f} impressions"

        html_body = f"""
        <div style="font-family: Inter, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #7c3aed, #a855f7); padding: 24px; border-radius: 12px; color: white; margin-bottom: 24px;">
                <h1 style="margin: 0 0 8px; font-size: 22px;">Weekly Autopilot Report</h1>
                <p style="margin: 0; opacity: 0.9;">Week of {plan.week_start.strftime('%b %d')} — Theme: {theme}</p>
            </div>

            <div style="display: flex; gap: 16px; margin-bottom: 24px;">
                <div style="flex: 1; background: #f9fafb; padding: 16px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 28px; font-weight: 700; color: #7c3aed;">{published_count}</div>
                    <div style="font-size: 12px; color: #6b7280;">Posts Published</div>
                </div>
                <div style="flex: 1; background: #f9fafb; padding: 16px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 28px; font-weight: 700; color: #7c3aed;">{impressions:,.0f}</div>
                    <div style="font-size: 12px; color: #6b7280;">Impressions</div>
                </div>
                <div style="flex: 1; background: #f9fafb; padding: 16px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 28px; font-weight: 700; color: #7c3aed;">{engagement:.1f}%</div>
                    <div style="font-size: 12px; color: #6b7280;">Avg Engagement</div>
                </div>
            </div>

            {"<div style='background: #f0fdf4; border: 1px solid #bbf7d0; padding: 16px; border-radius: 8px; margin-bottom: 24px;'><strong>Top Post:</strong><br>" + top_post + "</div>" if top_post else ""}

            <p style="color: #6b7280; font-size: 14px;">
                Next week's plan preview will arrive soon. Review and approve it before posts are generated.
            </p>

            <div style="text-align: center; margin-top: 24px;">
                <a href="https://app.kova.page/content/autopilot/" style="display: inline-block; background: #7c3aed; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600;">
                    Review Autopilot
                </a>
            </div>

            <p style="color: #9ca3af; font-size: 12px; text-align: center; margin-top: 32px;">
                You're receiving this because Autopilot is enabled. Manage in Settings.
            </p>
        </div>
        """

        resend.Emails.send({
            "from": f"Kova Agent <{getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'kova@kova.page')}>",
            "to": [user.email],
            "subject": subject,
            "html": html_body,
        })

    except Exception as e:
        logger.error("Failed to send autopilot review email for plan %s: %s", plan.pk, e)
