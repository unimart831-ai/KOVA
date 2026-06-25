"""Admin overview metrics — consolidated queries + short-lived cache."""

from __future__ import annotations

from datetime import timedelta

from django.core.cache import cache
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

OVERVIEW_CACHE_KEY = "admin:overview:context:v1"
OVERVIEW_CACHE_TTL = 90


def get_cached_overview_context(*, force_refresh: bool = False) -> dict:
    """Return overview template context; recomputes at most every 90 seconds."""
    if not force_refresh:
        cached = cache.get(OVERVIEW_CACHE_KEY)
        if cached is not None:
            return cached
    context = build_overview_context()
    cache.set(OVERVIEW_CACHE_KEY, context, OVERVIEW_CACHE_TTL)
    return context


def invalidate_overview_cache() -> None:
    cache.delete(OVERVIEW_CACHE_KEY)


def build_overview_context() -> dict:
    from apps.accounts.models import User, UserProfile
    from apps.accounts.pilot_metrics import get_pilot_metrics
    from apps.admin_dashboard.ops_hub import get_cached_ops_hub_snapshot
    from apps.agents.models import AgentAction
    from apps.analytics.models import Conversion, PageView, WebsiteEvent
    from apps.billing.models import MpesaPayment, PLAN_LIMITS, PlanPrice
    from apps.briefs.models import DailyBrief
    from apps.content.models import ABTest, ContentSeed, Post, VoiceBrief
    from apps.engage.models import Interaction, Superfan
    from apps.help.models import Article, HelpPageView
    from apps.leads.models import Lead, LeadActivity, LeadEnrollment
    from apps.partners.models import Partner, PartnerApplication, Referral
    from apps.platforms.models import SocialAccount
    from apps.teams.models import Brand, Team, TeamActivity, TeamMember
    from rest_framework.authtoken.models import Token

    now = timezone.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)
    thirty_days_ago_date = today - timedelta(days=30)
    seven_days_ago_date = today - timedelta(days=6)
    agent_cutoff = now - timedelta(hours=24)

    # ── Users (2 queries → 1 aggregate + 1 distinct) ───────────────────
    user_agg = User.objects.aggregate(
        total=Count("id"),
        joined_before_7d=Count("id", filter=Q(date_joined__lte=seven_days_ago)),
    )
    total_users = user_agg["total"]
    users_7d_ago = user_agg["joined_before_7d"]

    active_users_7d = User.objects.filter(
        Q(posts__created_at__gte=seven_days_ago)
        | Q(content_seeds__created_at__gte=seven_days_ago),
    ).distinct().count()

    workspace_views_7d = PageView.objects.filter(
        viewed_at__gte=seven_days_ago,
        section__in=["brief"],
    ).count()
    today_briefs_7d = DailyBrief.objects.filter(
        date__gte=today - timedelta(days=6),
    ).count()
    voice_launches_7d = VoiceBrief.objects.filter(created_at__gte=seven_days_ago).count()

    # ── Posts (4 counts → 1 aggregate) ─────────────────────────────────
    post_agg = Post.objects.aggregate(
        total=Count("id"),
        published=Count("id", filter=Q(status="published")),
        posts_today=Count(
            "id",
            filter=Q(status="published", published_at__date=today),
        ),
        posts_yesterday=Count(
            "id",
            filter=Q(status="published", published_at__date=yesterday),
        ),
    )
    total_posts = post_agg["total"]
    total_published = post_agg["published"]
    posts_today = post_agg["posts_today"]
    posts_yesterday = post_agg["posts_yesterday"]

    # ── Agent 24h (shared with health grid) ──────────────────────────────
    agent_24h_qs = AgentAction.objects.filter(created_at__gte=agent_cutoff)
    agent_agg = agent_24h_qs.aggregate(
        total=Count("id"),
        completed=Count("id", filter=Q(status="completed")),
    )
    agent_total_24h = agent_agg["total"]
    agent_completed_24h = agent_agg["completed"]
    agent_success_rate = (
        round((agent_completed_24h / agent_total_24h) * 100, 1)
        if agent_total_24h > 0
        else 100.0
    )

    # ── MRR + subscription breakdown ─────────────────────────────────────
    plan_prices_kes = {tier: limits["price_kes"] for tier, limits in PLAN_LIMITS.items()}
    for pp in PlanPrice.objects.filter(is_active=True):
        plan_prices_kes[pp.tier] = pp.price_kes

    sub_breakdown = list(
        UserProfile.objects.values("plan", "subscription_status")
        .annotate(count=Count("id"))
        .order_by("plan"),
    )
    paying_users = sum(
        row["count"]
        for row in sub_breakdown
        if row["subscription_status"] in ("active", "trialing")
    )
    mrr_kes = sum(
        plan_prices_kes.get(pc["plan"], 0) * pc["count"]
        for pc in UserProfile.objects.filter(
            subscription_status__in=["active", "trialing"],
        ).values("plan").annotate(count=Count("id"))
    )

    # ── User growth chart ────────────────────────────────────────────────
    daily_signups = dict(
        User.objects.filter(date_joined__date__gte=thirty_days_ago_date)
        .annotate(day=TruncDate("date_joined"))
        .values("day")
        .annotate(count=Count("id"))
        .values_list("day", "count"),
    )
    base_count = User.objects.filter(date_joined__date__lt=thirty_days_ago_date).count()
    user_growth = []
    running = base_count
    for i in range(30, -1, -1):
        d = today - timedelta(days=i)
        running += daily_signups.get(d, 0)
        user_growth.append({"date": d.isoformat(), "total": running})

    # ── Content pipeline chart (4 queries — already grouped by day) ──────
    seed_counts = dict(
        ContentSeed.objects.filter(created_at__date__gte=seven_days_ago_date)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .values_list("day", "count"),
    )
    post_counts = dict(
        Post.objects.filter(created_at__date__gte=seven_days_ago_date)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .values_list("day", "count"),
    )
    pub_counts = dict(
        Post.objects.filter(status="published", published_at__date__gte=seven_days_ago_date)
        .annotate(day=TruncDate("published_at"))
        .values("day")
        .annotate(count=Count("id"))
        .values_list("day", "count"),
    )
    fail_counts = dict(
        Post.objects.filter(status="failed", updated_at__date__gte=seven_days_ago_date)
        .annotate(day=TruncDate("updated_at"))
        .values("day")
        .annotate(count=Count("id"))
        .values_list("day", "count"),
    )
    content_pipeline = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        content_pipeline.append({
            "date": d.isoformat(),
            "seeds": seed_counts.get(d, 0),
            "generated": post_counts.get(d, 0),
            "published": pub_counts.get(d, 0),
            "failed": fail_counts.get(d, 0),
        })

    # ── Revenue chart ────────────────────────────────────────────────────
    mpesa_by_day = dict(
        MpesaPayment.objects.filter(
            status="completed",
            created_at__date__gte=thirty_days_ago_date,
        )
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Sum("amount"))
        .values_list("day", "total"),
    )
    revenue_data = [
        {
            "date": (today - timedelta(days=i)).isoformat(),
            "mpesa": float(mpesa_by_day.get(today - timedelta(days=i), 0) or 0),
        }
        for i in range(30, -1, -1)
    ]

    # ── Agent health grid ─────────────────────────────────────────────────
    agent_types = ["create", "analyst", "research", "adapt", "engage", "strategist"]
    agent_stats = {
        row["agent_type"]: row
        for row in agent_24h_qs.values("agent_type").annotate(
            total=Count("id"),
            completed=Count("id", filter=Q(status="completed")),
            failed=Count("id", filter=Q(status="failed")),
            tokens=Sum("tokens_used"),
            avg_dur=Avg("duration_ms", filter=Q(duration_ms__gt=0)),
        )
    }
    agent_health = []
    for at in agent_types:
        row = agent_stats.get(at, {})
        total = row.get("total", 0)
        completed = row.get("completed", 0)
        rate = round((completed / total) * 100, 1) if total > 0 else 100.0
        agent_health.append({
            "type": at,
            "name": at.title(),
            "success_rate": rate,
            "runs_24h": total,
            "failed_24h": row.get("failed", 0),
            "avg_duration_ms": int(row.get("avg_dur", 0) or 0),
            "tokens_24h": row.get("tokens", 0) or 0,
            "status": "green" if rate >= 95 else ("yellow" if rate >= 80 else "red"),
        })

    # ── Live feeds (small LIMIT queries) ─────────────────────────────────
    recent_actions = list(
        AgentAction.objects.select_related("user").order_by("-created_at")[:20],
    )
    recent_failures = list(
        Post.objects.filter(status="failed")
        .select_related("user", "social_account")
        .order_by("-updated_at")[:5],
    )
    recent_team_activity = list(
        TeamActivity.objects.select_related("team", "actor").order_by("-created_at")[:10],
    )

    # ── Platform health (4 → 1 aggregate) ────────────────────────────────
    social_agg = SocialAccount.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        expiring=Count(
            "id",
            filter=Q(
                is_active=True,
                token_expires_at__lte=now + timedelta(hours=24),
                token_expires_at__gt=now,
            ),
        ),
        errored=Count(
            "id",
            filter=Q(is_active=True)
            & ~Q(last_error="")
            & ~Q(last_error__isnull=True),
        ),
    )

    # ── Quick stats (engage + seeds) ─────────────────────────────────────
    total_seeds = ContentSeed.objects.count()
    total_interactions = Interaction.objects.count()
    total_superfans = Superfan.objects.count()

    team_agg = {
        "teams": Team.objects.count(),
        "members": TeamMember.objects.count(),
    }
    ab_agg = ABTest.objects.aggregate(
        total=Count("id"),
        running=Count("id", filter=Q(status="running")),
    )
    brand_agg = Brand.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
    )

    conv_agg = Conversion.objects.aggregate(
        total=Count("id"),
        last_30d=Count("id", filter=Q(created_at__gte=thirty_days_ago)),
        revenue_30d=Sum("revenue", filter=Q(created_at__gte=thirty_days_ago)),
    )

    pixel_events_30d = WebsiteEvent.objects.filter(
        created_at__gte=thirty_days_ago,
    ).count()
    active_pixels = UserProfile.objects.exclude(
        pixel_token__isnull=True,
    ).exclude(pixel_token="").count()

    help_views_7d = HelpPageView.objects.filter(viewed_at__gte=seven_days_ago).count()
    help_articles = Article.objects.filter(status=Article.Status.PUBLISHED).count()

    partner_agg = {
        "active": Partner.objects.filter(is_active=True).count(),
        "pending_apps": PartnerApplication.objects.filter(status="pending").count(),
    }
    referral_agg = Referral.objects.aggregate(
        total=Count("id"),
        active=Count(
            "id",
            filter=Q(is_active=True, activated_at__isnull=False),
        ),
    )

    seed_7d_agg = ContentSeed.objects.filter(created_at__gte=seven_days_ago).aggregate(
        total=Count("id"),
        auto=Count("id", filter=Q(notes__startswith="[")),
    )
    auto_approved_7d = Post.objects.filter(
        created_at__gte=seven_days_ago,
        generated_by_agent="create",
        status__in=["approved", "scheduled", "published"],
    ).count()
    recycled_seeds = ContentSeed.objects.filter(notes__startswith="[Recycle]").count()

    nurture_agg = LeadActivity.objects.filter(created_at__gte=seven_days_ago).aggregate(
        emails=Count("id", filter=Q(activity_type="email_sent")),
        whatsapp=Count("id", filter=Q(activity_type="whatsapp_sent")),
    )
    lead_agg = Lead.objects.aggregate(
        scored=Count("id", filter=~Q(status__in=["converted", "lost"])),
        high_priority=Count(
            "id",
            filter=Q(priority="high") & ~Q(status__in=["converted", "lost"]),
        ),
        stale=Count(
            "id",
            filter=~Q(status__in=["converted", "lost"])
            & Q(last_activity_at__lt=seven_days_ago),
        ),
    )
    nurture_due_now = LeadEnrollment.objects.filter(
        completed=False,
        paused=False,
        next_step_at__lte=now,
    ).count()

    try:
        from apps.whatsapp.models import WhatsAppConversation, WhatsAppTemplate

        wa_agg = {
            "escalated": WhatsAppConversation.objects.filter(status="escalated").count(),
            "templates_pending": WhatsAppTemplate.objects.filter(status="submitted").count(),
        }
    except Exception:
        wa_agg = {"escalated": 0, "templates_pending": 0}

    try:
        from apps.briefs.operations_report import build_platform_operations_report

        ops_24h = build_platform_operations_report(hours=24)
        ops_tasks_24h = ops_24h.get("total_tasks", 0)
    except Exception:
        ops_tasks_24h = 0

    automation_types_7d = AgentAction.objects.filter(
        created_at__gte=seven_days_ago,
        status="completed",
    ).values("action_type").distinct().count()

    automation_labels = [
        "Lead scoring", "Catalog sampling", "Snap to Sell", "Batch Snap",
        "Motion reels", "Receipt restock", "Competitor intel", "Daily brief",
        "Trend seeding", "Smart approval", "Content recycling",
        "Nurture emails", "Campaign builder", "Engagement auto-reply",
        "Review requests", "Voice briefs",
    ]

    return {
        "total_users": total_users,
        "users_7d_ago": users_7d_ago,
        "active_users_7d": active_users_7d,
        "paying_users": paying_users,
        "posts_today": posts_today,
        "posts_yesterday": posts_yesterday,
        "agent_success_rate": agent_success_rate,
        "agent_total_24h": agent_total_24h,
        "mrr_kes": mrr_kes,
        "user_growth_json": user_growth,
        "content_pipeline_json": content_pipeline,
        "revenue_json": revenue_data,
        "agent_health": agent_health,
        "recent_actions": recent_actions,
        "total_accounts": social_agg["total"],
        "active_accounts": social_agg["active"],
        "expiring_tokens": social_agg["expiring"],
        "errored_accounts": social_agg["errored"],
        "total_posts": total_posts,
        "total_published": total_published,
        "total_seeds": total_seeds,
        "total_interactions": total_interactions,
        "total_superfans": total_superfans,
        "sub_breakdown": sub_breakdown,
        "recent_failures": recent_failures,
        "total_teams": team_agg["teams"],
        "total_team_members": team_agg["members"],
        "total_ab_tests": ab_agg["total"],
        "running_ab_tests": ab_agg["running"],
        "help_views_7d": help_views_7d,
        "help_articles": help_articles,
        "total_brands": brand_agg["total"],
        "active_brands": brand_agg["active"],
        "total_conversions": conv_agg["total"],
        "conversions_30d": conv_agg["last_30d"],
        "conversion_revenue": conv_agg["revenue_30d"] or 0,
        "pixel_events_30d": pixel_events_30d,
        "active_pixels": active_pixels,
        "total_api_tokens": Token.objects.count(),
        "recent_team_activity": recent_team_activity,
        "total_partners": partner_agg["active"],
        "pending_partner_apps": partner_agg["pending_apps"],
        "total_referrals": referral_agg["total"],
        "active_referrals": referral_agg["active"],
        "auto_seeds_7d": seed_7d_agg["auto"],
        "total_seeds_7d": seed_7d_agg["total"],
        "auto_approved_7d": auto_approved_7d,
        "recycled_seeds": recycled_seeds,
        "ai_campaigns": 0,
        "nurture_emails_7d": nurture_agg["emails"],
        "nurture_whatsapp_7d": nurture_agg["whatsapp"],
        "stale_leads_count": lead_agg["stale"],
        "nurture_due_now": nurture_due_now,
        "wa_escalated": wa_agg["escalated"],
        "wa_templates_pending": wa_agg["templates_pending"],
        "scored_leads": lead_agg["scored"],
        "high_priority_leads": lead_agg["high_priority"],
        "ops_tasks_24h": ops_tasks_24h,
        "automation_types_7d": automation_types_7d,
        "automation_labels": automation_labels,
        "workspace_views_7d": workspace_views_7d,
        "today_briefs_7d": today_briefs_7d,
        "voice_launches_7d": voice_launches_7d,
        "moment_packs_ready": 0,
        "ops_hub": get_cached_ops_hub_snapshot(),
        "pilot_metrics": get_pilot_metrics(),
    }
