from datetime import timedelta

from django.db.models import Avg, Case, Count, Q, Sum, When
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from apps.accounts.pilot_metrics import get_pilot_metrics
from apps.admin_dashboard.decorators import staff_required
from apps.admin_dashboard.ops_hub import build_ops_hub_snapshot


@staff_required
def overview(request):
    """Admin dashboard home — key metrics, charts data, activity feed."""
    from apps.accounts.models import User, UserProfile
    from apps.agents.models import AgentAction, AgentConfig
    from apps.analytics.models import Conversion, PageView
    from apps.billing.models import MpesaPayment
    from apps.briefs.models import DailyBrief
    from apps.content.models import ABTest, ContentSeed, Post
    from apps.content.models import VoiceBrief
    from apps.engage.models import Interaction, Superfan
    from apps.help.models import HelpPageView
    from apps.platforms.models import SocialAccount
    from apps.teams.models import Brand, Team, TeamActivity, TeamMember
    from rest_framework.authtoken.models import Token

    now = timezone.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # ── Key Metrics ──────────────────────────────────────────────────────
    total_users = User.objects.count()
    users_7d_ago = User.objects.filter(date_joined__lte=seven_days_ago).count()

    active_users_7d = User.objects.filter(
        Q(posts__created_at__gte=seven_days_ago) |
        Q(content_seeds__created_at__gte=seven_days_ago)
    ).distinct().count()
    workspace_views_7d = PageView.objects.filter(
        viewed_at__gte=seven_days_ago,
        section__in=["brief"],
    ).count()
    today_briefs_7d = DailyBrief.objects.filter(date__gte=today - timedelta(days=6)).count()
    voice_launches_7d = VoiceBrief.objects.filter(created_at__gte=seven_days_ago).count()
    moment_packs_ready = 0

    posts_today = Post.objects.filter(
        status="published", published_at__date=today,
    ).count()
    posts_yesterday = Post.objects.filter(
        status="published", published_at__date=yesterday,
    ).count()

    # Agent success rate (24h)
    agent_24h = AgentAction.objects.filter(created_at__gte=now - timedelta(hours=24))
    agent_total_24h = agent_24h.count()
    agent_completed_24h = agent_24h.filter(status="completed").count()
    agent_success_rate = (
        round((agent_completed_24h / agent_total_24h) * 100, 1)
        if agent_total_24h > 0 else 100.0
    )

    # MRR calculation — use PLAN_LIMITS (Kova + legacy grandfathered tiers)
    from apps.billing.models import PLAN_LIMITS, PlanPrice

    plan_prices_kes = {tier: limits["price_kes"] for tier, limits in PLAN_LIMITS.items()}
    for pp in PlanPrice.objects.filter(is_active=True):
        plan_prices_kes[pp.tier] = pp.price_kes
    mrr_kes = 0
    plan_counts = (
        UserProfile.objects.filter(subscription_status__in=["active", "trialing"])
        .values("plan")
        .annotate(count=Count("id"))
    )
    for pc in plan_counts:
        mrr_kes += plan_prices_kes.get(pc["plan"], 0) * pc["count"]

    # ── Subscription Breakdown ───────────────────────────────────────────
    sub_breakdown = list(
        UserProfile.objects.values("plan", "subscription_status")
        .annotate(count=Count("id"))
        .order_by("plan")
    )
    paying_users = UserProfile.objects.filter(
        subscription_status__in=["active", "trialing"],
    ).count()

    # ── User Growth (30-day chart data) ──────────────────────────────────
    # Single query: count users by registration date, then compute running total
    thirty_days_ago_date = today - timedelta(days=30)
    daily_signups = dict(
        User.objects.filter(date_joined__date__gte=thirty_days_ago_date)
        .values_list("date_joined__date")
        .annotate(count=Count("id"))
        .values_list("date_joined__date", "count")
    )
    base_count = User.objects.filter(date_joined__date__lt=thirty_days_ago_date).count()
    user_growth = []
    running = base_count
    for i in range(30, -1, -1):
        d = today - timedelta(days=i)
        running += daily_signups.get(d, 0)
        user_growth.append({"date": d.isoformat(), "total": running})

    # ── Content Pipeline (7-day chart data) ──────────────────────────────
    seven_days_ago_date = today - timedelta(days=6)
    seed_counts = dict(
        ContentSeed.objects.filter(created_at__date__gte=seven_days_ago_date)
        .annotate(day=TruncDate("created_at"))
        .values("day").annotate(count=Count("id"))
        .values_list("day", "count")
    )
    post_counts = dict(
        Post.objects.filter(created_at__date__gte=seven_days_ago_date)
        .annotate(day=TruncDate("created_at"))
        .values("day").annotate(count=Count("id"))
        .values_list("day", "count")
    )
    pub_counts = dict(
        Post.objects.filter(status="published", published_at__date__gte=seven_days_ago_date)
        .annotate(day=TruncDate("published_at"))
        .values("day").annotate(count=Count("id"))
        .values_list("day", "count")
    )
    fail_counts = dict(
        Post.objects.filter(status="failed", updated_at__date__gte=seven_days_ago_date)
        .annotate(day=TruncDate("updated_at"))
        .values("day").annotate(count=Count("id"))
        .values_list("day", "count")
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

    # ── Revenue (30-day chart data) ──────────────────────────────────────
    mpesa_by_day = dict(
        MpesaPayment.objects.filter(
            status="completed", created_at__date__gte=thirty_days_ago_date,
        ).annotate(day=TruncDate("created_at"))
        .values("day").annotate(total=Sum("amount"))
        .values_list("day", "total")
    )
    revenue_data = []
    for i in range(30, -1, -1):
        d = today - timedelta(days=i)
        revenue_data.append({
            "date": d.isoformat(),
            "mpesa": float(mpesa_by_day.get(d, 0) or 0),
        })

    # ── Agent Health Grid ────────────────────────────────────────────────
    agent_types = ["create", "analyst", "research", "adapt", "engage", "strategist"]
    agent_stats = {
        row["agent_type"]: row
        for row in AgentAction.objects.filter(
            created_at__gte=now - timedelta(hours=24),
        ).values("agent_type").annotate(
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

    # ── Recent Activity Feed ─────────────────────────────────────────────
    recent_actions = (
        AgentAction.objects.select_related("user")
        .order_by("-created_at")[:20]
    )

    # ── Platform Health ──────────────────────────────────────────────────
    total_accounts = SocialAccount.objects.count()
    active_accounts = SocialAccount.objects.filter(is_active=True).count()
    expiring_tokens = SocialAccount.objects.filter(
        is_active=True,
        token_expires_at__lte=now + timedelta(hours=24),
        token_expires_at__gt=now,
    ).count()
    errored_accounts = SocialAccount.objects.filter(
        is_active=True,
    ).exclude(last_error="").exclude(last_error__isnull=True).count()

    # ── Quick Stats ──────────────────────────────────────────────────────
    total_posts = Post.objects.count()
    total_published = Post.objects.filter(status="published").count()
    total_seeds = ContentSeed.objects.count()
    total_interactions = Interaction.objects.count()
    total_superfans = Superfan.objects.count()

    # ── Teams & A/B Tests ────────────────────────────────────────────────
    total_teams = Team.objects.count()
    total_team_members = TeamMember.objects.count()
    total_ab_tests = ABTest.objects.count()
    running_ab_tests = ABTest.objects.filter(status="running").count()

    # ── Brands ───────────────────────────────────────────────────────────
    total_brands = Brand.objects.count()
    active_brands = Brand.objects.filter(is_active=True).count()

    # ── Revenue Attribution / Conversions ────────────────────────────────
    total_conversions = Conversion.objects.count()
    conversions_30d = Conversion.objects.filter(created_at__gte=thirty_days_ago).count()
    conversion_revenue = Conversion.objects.filter(
        created_at__gte=thirty_days_ago,
    ).aggregate(total=Sum("revenue"))["total"] or 0

    # ── Kova Pixel ───────────────────────────────────────────────────────
    from apps.analytics.models import WebsiteEvent
    pixel_events_30d = WebsiteEvent.objects.filter(created_at__gte=thirty_days_ago).count()
    active_pixels = UserProfile.objects.exclude(pixel_token__isnull=True).exclude(pixel_token="").count()

    # ── API Tokens ───────────────────────────────────────────────────────
    total_api_tokens = Token.objects.count()

    # ── Team Activity (recent across all teams) ──────────────────────────
    recent_team_activity = (
        TeamActivity.objects.select_related("team", "actor")
        .order_by("-created_at")[:10]
    )

    # ── Help Center ──────────────────────────────────────────────────────
    from apps.help.models import Article

    help_views_7d = HelpPageView.objects.filter(viewed_at__gte=seven_days_ago).count()
    help_articles = Article.objects.filter(status=Article.Status.PUBLISHED).count()

    # ── Partners ─────────────────────────────────────────────────────────
    from apps.partners.models import Partner, PartnerApplication, Referral
    total_partners = Partner.objects.filter(is_active=True).count()
    pending_partner_apps = PartnerApplication.objects.filter(status="pending").count()
    total_referrals = Referral.objects.count()
    active_referrals = Referral.objects.filter(is_active=True, activated_at__isnull=False).count()

    # ── Failed Content (recent) ──────────────────────────────────────────
    recent_failures = Post.objects.filter(
        status="failed",
    ).select_related("user", "social_account").order_by("-updated_at")[:5]

    # ── AI Automation Intelligence ────────────────────────────────────────
    from apps.leads.models import Lead

    # Auto-seeded content (from agents, products, competitors, recycling)
    auto_seeds_7d = ContentSeed.objects.filter(
        created_at__gte=seven_days_ago,
        notes__startswith="[",
    ).count()
    total_seeds_7d = ContentSeed.objects.filter(
        created_at__gte=seven_days_ago,
    ).count()

    # Smart auto-approved posts
    auto_approved_7d = Post.objects.filter(
        created_at__gte=seven_days_ago,
        generated_by_agent="create",
        status__in=["approved", "scheduled", "published"],
    ).count()

    # Content recycled
    recycled_seeds = ContentSeed.objects.filter(
        notes__startswith="[Recycle]",
    ).count()

    # AI campaigns built (legacy — campaigns app is models-only stub)
    ai_campaigns = 0

    # Nurture emails sent (7d)
    from apps.leads.models import LeadActivity, LeadEnrollment
    nurture_emails_7d = LeadActivity.objects.filter(
        activity_type="email_sent",
        created_at__gte=seven_days_ago,
    ).count()
    nurture_whatsapp_7d = LeadActivity.objects.filter(
        activity_type="whatsapp_sent",
        created_at__gte=seven_days_ago,
    ).count()
    stale_leads_count = Lead.objects.exclude(
        status__in=["converted", "lost"],
    ).filter(last_activity_at__lt=seven_days_ago).count()
    nurture_due_now = LeadEnrollment.objects.filter(
        completed=False, paused=False, next_step_at__lte=now,
    ).count()

    # Lead scoring
    scored_leads = Lead.objects.exclude(
        status__in=["converted", "lost"],
    ).count()
    high_priority_leads = Lead.objects.filter(priority="high").exclude(
        status__in=["converted", "lost"],
    ).count()

    # WhatsApp ops snapshot
    try:
        from apps.whatsapp.models import WhatsAppConversation, WhatsAppTemplate
        wa_escalated = WhatsAppConversation.objects.filter(status="escalated").count()
        wa_templates_pending = WhatsAppTemplate.objects.filter(status="submitted").count()
    except Exception:
        wa_escalated = 0
        wa_templates_pending = 0

    # Platform operations snapshot (24h)
    try:
        from apps.briefs.operations_report import build_platform_operations_report

        ops_24h = build_platform_operations_report(hours=24)
        ops_tasks_24h = ops_24h.get("total_tasks", 0)
    except Exception:
        ops_tasks_24h = 0

    # Active automation types (distinct agent action types, 7d)
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

    context = {
        "page_title": "Dashboard Overview",
        # Key metrics
        "total_users": total_users,
        "users_7d_ago": users_7d_ago,
        "active_users_7d": active_users_7d,
        "paying_users": paying_users,
        "posts_today": posts_today,
        "posts_yesterday": posts_yesterday,
        "agent_success_rate": agent_success_rate,
        "agent_total_24h": agent_total_24h,
        "mrr_kes": mrr_kes,
        # Chart data (JSON-serializable)
        "user_growth_json": user_growth,
        "content_pipeline_json": content_pipeline,
        "revenue_json": revenue_data,
        # Agent health
        "agent_health": agent_health,
        # Activity
        "recent_actions": recent_actions,
        # Platform health
        "total_accounts": total_accounts,
        "active_accounts": active_accounts,
        "expiring_tokens": expiring_tokens,
        "errored_accounts": errored_accounts,
        # Quick stats
        "total_posts": total_posts,
        "total_published": total_published,
        "total_seeds": total_seeds,
        "total_interactions": total_interactions,
        "total_superfans": total_superfans,
        # Subscription breakdown
        "sub_breakdown": sub_breakdown,
        # Failures
        "recent_failures": recent_failures,
        # Teams & A/B Tests
        "total_teams": total_teams,
        "total_team_members": total_team_members,
        "total_ab_tests": total_ab_tests,
        "running_ab_tests": running_ab_tests,
        # Help Center
        "help_views_7d": help_views_7d,
        "help_articles": help_articles,
        # Brands
        "total_brands": total_brands,
        "active_brands": active_brands,
        # Conversions / Revenue Attribution
        "total_conversions": total_conversions,
        "conversions_30d": conversions_30d,
        "conversion_revenue": conversion_revenue,
        # Kova Pixel
        "pixel_events_30d": pixel_events_30d,
        "active_pixels": active_pixels,
        # API
        "total_api_tokens": total_api_tokens,
        # Team Activity
        "recent_team_activity": recent_team_activity,
        # Partners
        "total_partners": total_partners,
        "pending_partner_apps": pending_partner_apps,
        "total_referrals": total_referrals,
        "active_referrals": active_referrals,
        # AI Automation
        "auto_seeds_7d": auto_seeds_7d,
        "total_seeds_7d": total_seeds_7d,
        "auto_approved_7d": auto_approved_7d,
        "recycled_seeds": recycled_seeds,
        "ai_campaigns": ai_campaigns,
        "nurture_emails_7d": nurture_emails_7d,
        "nurture_whatsapp_7d": nurture_whatsapp_7d,
        "stale_leads_count": stale_leads_count,
        "nurture_due_now": nurture_due_now,
        "wa_escalated": wa_escalated,
        "wa_templates_pending": wa_templates_pending,
        "scored_leads": scored_leads,
        "high_priority_leads": high_priority_leads,
        "ops_tasks_24h": ops_tasks_24h,
        "automation_types_7d": automation_types_7d,
        "automation_labels": automation_labels,
        "workspace_views_7d": workspace_views_7d,
        "today_briefs_7d": today_briefs_7d,
        "voice_launches_7d": voice_launches_7d,
        "moment_packs_ready": moment_packs_ready,
        "ops_hub": build_ops_hub_snapshot(),
        "pilot_metrics": get_pilot_metrics(),
    }
    return render(request, "admin_dashboard/overview.html", context)
