from datetime import timedelta

from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required


@staff_required
def overview(request):
    """Admin dashboard home — key metrics, charts data, activity feed."""
    from apps.accounts.models import User, UserProfile
    from apps.agents.models import AgentAction, AgentConfig
    from apps.billing.models import MpesaPayment
    from apps.content.models import ContentSeed, Post
    from apps.engage.models import Interaction, Superfan
    from apps.platforms.models import SocialAccount

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
    user_growth = []
    for i in range(30, -1, -1):
        d = today - timedelta(days=i)
        user_growth.append({
            "date": d.isoformat(),
            "total": User.objects.filter(date_joined__date__lte=d).count(),
        })

    # ── Content Pipeline (7-day chart data) ──────────────────────────────
    content_pipeline = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        content_pipeline.append({
            "date": d.isoformat(),
            "seeds": ContentSeed.objects.filter(created_at__date=d).count(),
            "generated": Post.objects.filter(created_at__date=d).count(),
            "published": Post.objects.filter(
                status="published", published_at__date=d,
            ).count(),
            "failed": Post.objects.filter(
                status="failed", updated_at__date=d,
            ).count(),
        })

    # ── Revenue (30-day chart data) ──────────────────────────────────────
    revenue_data = []
    for i in range(30, -1, -1):
        d = today - timedelta(days=i)
        mpesa = MpesaPayment.objects.filter(
            status="completed", created_at__date=d,
        ).aggregate(total=Sum("amount"))["total"] or 0
        revenue_data.append({
            "date": d.isoformat(),
            "mpesa": float(mpesa),
        })

    # ── Agent Health Grid ────────────────────────────────────────────────
    agent_types = ["create", "analyst", "research", "adapt", "engage", "strategist"]
    agent_health = []
    for at in agent_types:
        actions = AgentAction.objects.filter(
            agent_type=at, created_at__gte=now - timedelta(hours=24),
        )
        total = actions.count()
        completed = actions.filter(status="completed").count()
        failed = actions.filter(status="failed").count()
        tokens = actions.aggregate(t=Sum("tokens_used"))["t"] or 0
        avg_dur = actions.filter(duration_ms__gt=0).aggregate(
            a=Avg("duration_ms"),
        )["a"] or 0
        rate = round((completed / total) * 100, 1) if total > 0 else 100.0

        agent_health.append({
            "type": at,
            "name": at.title(),
            "success_rate": rate,
            "runs_24h": total,
            "failed_24h": failed,
            "avg_duration_ms": int(avg_dur),
            "tokens_24h": tokens,
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
    }
    return render(request, "admin_dashboard/overview.html", context)
