from datetime import timedelta

from django.db.models import Avg, Case, Count, Q, Sum, When
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required


@staff_required
def overview(request):
    """Admin dashboard home — key metrics, charts data, activity feed."""
    from apps.accounts.models import User, UserProfile
    from apps.agents.models import AgentAction, AgentConfig
    from apps.billing.models import MpesaPayment
    from apps.content.models import ABTest, ContentSeed, Post
    from apps.engage.models import Interaction, Superfan
    from apps.help.models import HelpPageView
    from apps.platforms.models import SocialAccount
    from apps.teams.models import Team, TeamMember

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

    # MRR calculation
    plan_prices_kes = {
        "starter": 99,
        "growth": 500,
        "pro": 1500,
        "agency": 3500,
    }
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

    # ── Help Center ──────────────────────────────────────────────────────
    help_views_7d = HelpPageView.objects.filter(viewed_at__gte=seven_days_ago).count()
    help_articles = 15  # Static count from help article registry

    # ── Failed Content (recent) ──────────────────────────────────────────
    recent_failures = Post.objects.filter(
        status="failed",
    ).select_related("user", "social_account").order_by("-updated_at")[:5]

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
    }
    return render(request, "admin_dashboard/overview.html", context)
