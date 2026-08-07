from datetime import timedelta

from django.conf import settings as django_settings
from django.core.paginator import Paginator
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from apps.core.admin_dashboard.decorators import staff_required
from apps.create.agents.models import AgentAction, AgentConfig


AGENT_TYPES = [
    ("research", "Research"),
    ("create", "Create"),
    ("adapt", "Adapt"),
    ("engage", "Engage"),
    ("analyst", "Analyst"),
    ("strategist", "Strategist"),
]


def calculate_action_cost(action):
    """Calculate accurate USD cost for a single AgentAction using per-model pricing."""
    costs = getattr(django_settings, "MODEL_TOKEN_COSTS", {})
    default = getattr(django_settings, "DEFAULT_TOKEN_COST", (0.0, 0.0))

    model = action.model_used or ""
    input_cost_per_1k, output_cost_per_1k = costs.get(model, default)

    # Use granular token counts if available, fall back to total_tokens split estimate
    if action.input_tokens or action.output_tokens:
        cost = (action.input_tokens / 1000 * input_cost_per_1k) + \
               (action.output_tokens / 1000 * output_cost_per_1k)
    else:
        # Legacy records: no input/output split. Use average of input+output rates.
        avg_rate = (input_cost_per_1k + output_cost_per_1k) / 2
        cost = action.tokens_used / 1000 * avg_rate

    return cost


def calculate_cost_from_tokens(model, input_tokens=0, output_tokens=0, total_tokens=0):
    """Calculate cost given a model name and token counts. For aggregated queries."""
    costs = getattr(django_settings, "MODEL_TOKEN_COSTS", {})
    default = getattr(django_settings, "DEFAULT_TOKEN_COST", (0.0, 0.0))

    input_cost_per_1k, output_cost_per_1k = costs.get(model or "", default)

    if input_tokens or output_tokens:
        return (input_tokens / 1000 * input_cost_per_1k) + \
               (output_tokens / 1000 * output_cost_per_1k)
    else:
        avg_rate = (input_cost_per_1k + output_cost_per_1k) / 2
        return total_tokens / 1000 * avg_rate


@staff_required
def agent_overview(request):
    """Agent health grid + performance summary."""
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_30d = now - timedelta(days=30)

    # Per-agent health grid (single query instead of 30+)
    agent_stats = {
        row["agent_type"]: row
        for row in AgentAction.objects.filter(
            created_at__gte=last_24h,
        ).values("agent_type").annotate(
            total=Count("id"),
            completed=Count("id", filter=Q(status="completed")),
            failed=Count("id", filter=Q(status="failed")),
            tokens=Sum("tokens_used"),
            avg_dur=Avg("duration_ms", filter=Q(duration_ms__gt=0)),
        )
    }
    agents = []
    for agent_type, label in AGENT_TYPES:
        row = agent_stats.get(agent_type, {})
        total = row.get("total", 0)
        completed = row.get("completed", 0)
        failed = row.get("failed", 0)
        tokens = row.get("tokens", 0) or 0
        avg_dur = row.get("avg_dur")
        success_rate = (completed / total * 100) if total else 0
        if success_rate >= 95:
            health = "green"
        elif success_rate >= 80:
            health = "yellow"
        else:
            health = "red"

        agents.append({
            "type": agent_type,
            "label": label,
            "total": total,
            "completed": completed,
            "failed": failed,
            "success_rate": round(success_rate, 1),
            "health": health,
            "tokens": tokens,
            "avg_duration_ms": round(avg_dur) if avg_dur else None,
        })

    # Global totals (derived from agent_stats — no extra queries)
    total_actions_24h = sum(row.get("total", 0) for row in agent_stats.values())
    total_tokens_24h = sum((row.get("tokens", 0) or 0) for row in agent_stats.values())
    total_failed_24h = sum(row.get("failed", 0) for row in agent_stats.values())
    global_success = (
        (total_actions_24h - total_failed_24h) / total_actions_24h * 100
        if total_actions_24h
        else 0
    )

    # 30-day success rate trend (single query)
    thirty_days_ago_date = (now - timedelta(days=29)).date()
    daily_stats = {
        row["day"]: row
        for row in AgentAction.objects.filter(
            created_at__date__gte=thirty_days_ago_date,
        ).annotate(day=TruncDate("created_at"))
        .values("day").annotate(
            total=Count("id"),
            completed=Count("id", filter=Q(status="completed")),
        )
    }
    success_trend = []
    for i in range(29, -1, -1):
        d = (now - timedelta(days=i)).date()
        row = daily_stats.get(d, {})
        day_total = row.get("total", 0)
        day_completed = row.get("completed", 0)
        success_trend.append({
            "date": d.isoformat(),
            "rate": round(day_completed / day_total * 100, 1) if day_total else None,
            "total": day_total,
        })

    # 30-day token consumption by agent (single query)
    token_by_day_agent = {}
    for row in AgentAction.objects.filter(
        created_at__date__gte=thirty_days_ago_date,
    ).annotate(day=TruncDate("created_at")).values("day", "agent_type").annotate(
        tokens=Sum("tokens_used"),
    ):
        token_by_day_agent.setdefault(row["day"], {})[row["agent_type"]] = row["tokens"] or 0
    token_trend = []
    for i in range(29, -1, -1):
        d = (now - timedelta(days=i)).date()
        day_data = {"date": d.isoformat()}
        agent_tokens = token_by_day_agent.get(d, {})
        for agent_type, _ in AGENT_TYPES:
            day_data[agent_type] = agent_tokens.get(agent_type, 0)
        token_trend.append(day_data)

    # Recent errors (last 20)
    recent_errors = (
        AgentAction.objects.filter(status="failed")
        .select_related("user")
        .order_by("-created_at")[:20]
    )

    # ── AI Automation Stats ──────────────────────────────────────────────
    from apps.create.content.models import ContentSeed, Post

    # Auto-seeds by source (7d)
    auto_seed_sources = {
        "research": ContentSeed.objects.filter(
            created_at__gte=last_24h - timedelta(days=6),
            notes__startswith="[Research Agent]",
        ).count(),
        "competitor": ContentSeed.objects.filter(
            created_at__gte=last_24h - timedelta(days=6),
            notes__startswith="[Competitor Intel]",
        ).count(),
        "recycle": ContentSeed.objects.filter(
            created_at__gte=last_24h - timedelta(days=6),
            notes__startswith="[Recycle]",
        ).count(),
        "campaign_ai": ContentSeed.objects.filter(
            created_at__gte=last_24h - timedelta(days=6),
            notes__startswith="[Campaign AI]",
        ).count(),
    }
    total_auto_seeds_7d = sum(auto_seed_sources.values())

    # Smart auto-approval rate
    agent_posts_30d = Post.objects.filter(
        generated_by_agent="create",
        created_at__gte=last_30d,
    )
    total_agent_posts = agent_posts_30d.count()
    auto_approved_posts = agent_posts_30d.filter(
        status__in=["approved", "scheduled", "published"],
    ).count()

    # Users with auto-approve ON vs smart approval
    from apps.core.accounts.models import UserProfile
    auto_approve_on = UserProfile.objects.filter(auto_approve_posts=True).count()
    auto_approve_off = UserProfile.objects.filter(auto_approve_posts=False).count()

    context = {
        "page_title": "Agent Operations",
        "agents": agents,
        "total_actions_24h": total_actions_24h,
        "total_tokens_24h": total_tokens_24h,
        "total_failed_24h": total_failed_24h,
        "global_success": round(global_success, 1),
        "success_trend_json": success_trend,
        "token_trend_json": token_trend,
        "agent_types": AGENT_TYPES,
        "recent_errors": recent_errors,
        # AI Automation
        "auto_seed_sources": auto_seed_sources,
        "total_auto_seeds_7d": total_auto_seeds_7d,
        "total_agent_posts": total_agent_posts,
        "auto_approved_posts": auto_approved_posts,
        "auto_approve_on": auto_approve_on,
        "auto_approve_off": auto_approve_off,
    }
    return render(request, "admin_dashboard/agents/overview.html", context)


@staff_required
def agent_log(request):
    """Searchable, filterable agent action log."""
    qs = AgentAction.objects.select_related("user").all()

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(user__email__icontains=search)
            | Q(action_type__icontains=search)
            | Q(description__icontains=search)
        )

    agent = request.GET.get("agent", "")
    if agent:
        qs = qs.filter(agent_type=agent)

    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)

    sort = request.GET.get("sort", "-created_at")
    valid_sorts = {
        "created_at", "-created_at", "tokens_used", "-tokens_used",
        "duration_ms", "-duration_ms",
    }
    if sort not in valid_sorts:
        sort = "-created_at"
    qs = qs.order_by(sort)

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "Agent Action Log",
        "page_obj": page,
        "search": search,
        "current_agent": agent,
        "current_status": status,
        "current_sort": sort,
        "total_count": paginator.count,
        "agent_types": AGENT_TYPES,
        "status_choices": AgentAction.ActionStatus.choices,
    }
    return render(request, "admin_dashboard/agents/log.html", context)


@staff_required
def token_economics(request):
    """Token usage and cost analysis — accurate per-model pricing."""
    now = timezone.now()
    today = now.date()
    month_start = today.replace(day=1)

    from apps.core.accounts.models import User
    from apps.create.content.models import Post

    # ── Aggregate tokens ──────────────────────────────────────────────
    tokens_today = AgentAction.objects.filter(
        created_at__date=today,
    ).aggregate(t=Sum("tokens_used"))["t"] or 0

    tokens_month = AgentAction.objects.filter(
        created_at__date__gte=month_start,
    ).aggregate(t=Sum("tokens_used"))["t"] or 0

    active_users = User.objects.filter(
        agent_actions__created_at__date__gte=month_start,
    ).distinct().count()

    posts_generated = Post.objects.filter(
        created_at__date__gte=month_start,
    ).count()

    # ── Per-model cost: today ─────────────────────────────────────────
    today_by_model = (
        AgentAction.objects.filter(created_at__date=today)
        .values("model_used")
        .annotate(
            input_t=Sum("input_tokens"),
            output_t=Sum("output_tokens"),
            total_t=Sum("tokens_used"),
        )
    )
    cost_today = sum(
        calculate_cost_from_tokens(
            r["model_used"], r["input_t"] or 0, r["output_t"] or 0, r["total_t"] or 0,
        )
        for r in today_by_model
    )

    # ── Per-model cost: month ─────────────────────────────────────────
    month_by_model = (
        AgentAction.objects.filter(created_at__date__gte=month_start)
        .values("model_used")
        .annotate(
            input_t=Sum("input_tokens"),
            output_t=Sum("output_tokens"),
            total_t=Sum("tokens_used"),
            runs=Count("id"),
        )
        .order_by("-total_t")
    )
    cost_month = 0
    model_breakdown = []
    for r in month_by_model:
        model_cost = calculate_cost_from_tokens(
            r["model_used"], r["input_t"] or 0, r["output_t"] or 0, r["total_t"] or 0,
        )
        cost_month += model_cost

        costs = getattr(django_settings, "MODEL_TOKEN_COSTS", {})
        default = getattr(django_settings, "DEFAULT_TOKEN_COST", (0.0, 0.0))
        input_rate, output_rate = costs.get(r["model_used"] or "", default)

        model_breakdown.append({
            "model": r["model_used"] or "(legacy / unknown)",
            "input_tokens": r["input_t"] or 0,
            "output_tokens": r["output_t"] or 0,
            "total_tokens": r["total_t"] or 0,
            "runs": r["runs"],
            "input_rate": input_rate,
            "output_rate": output_rate,
            "cost": round(model_cost, 6),
        })

    cost_per_user = cost_month / active_users if active_users else 0
    cost_per_post = cost_month / posts_generated if posts_generated else 0

    # ── Per-agent totals (month) ──────────────────────────────────────
    agent_by_model = (
        AgentAction.objects.filter(created_at__date__gte=month_start)
        .values("agent_type", "model_used")
        .annotate(
            input_t=Sum("input_tokens"),
            output_t=Sum("output_tokens"),
            total_t=Sum("tokens_used"),
            runs=Count("id"),
        )
    )
    agent_cost_map = {}  # {agent_type: {tokens, runs, cost}}
    for r in agent_by_model:
        at = r["agent_type"]
        model_cost = calculate_cost_from_tokens(
            r["model_used"], r["input_t"] or 0, r["output_t"] or 0, r["total_t"] or 0,
        )
        if at not in agent_cost_map:
            agent_cost_map[at] = {"agent_type": at, "tokens": 0, "runs": 0, "cost": 0}
        agent_cost_map[at]["tokens"] += r["total_t"] or 0
        agent_cost_map[at]["runs"] += r["runs"]
        agent_cost_map[at]["cost"] += model_cost

    agent_totals = sorted(agent_cost_map.values(), key=lambda x: x["tokens"], reverse=True)
    for at in agent_totals:
        at["cost"] = round(at["cost"], 6)

    # ── Top 10 most expensive users (month) ───────────────────────────
    user_by_model = (
        AgentAction.objects.filter(created_at__date__gte=month_start)
        .values("user_id", "user__email", "model_used")
        .annotate(
            input_t=Sum("input_tokens"),
            output_t=Sum("output_tokens"),
            total_t=Sum("tokens_used"),
            runs=Count("id"),
        )
    )
    user_cost_map = {}  # {user_id: {tokens, runs, cost, user__email}}
    for r in user_by_model:
        uid = r["user_id"]
        model_cost = calculate_cost_from_tokens(
            r["model_used"], r["input_t"] or 0, r["output_t"] or 0, r["total_t"] or 0,
        )
        if uid not in user_cost_map:
            user_cost_map[uid] = {
                "user_id": uid,
                "user__email": r["user__email"],
                "tokens": 0,
                "runs": 0,
                "cost": 0,
            }
        user_cost_map[uid]["tokens"] += r["total_t"] or 0
        user_cost_map[uid]["runs"] += r["runs"]
        user_cost_map[uid]["cost"] += model_cost

    top_users = sorted(user_cost_map.values(), key=lambda x: x["cost"], reverse=True)[:10]
    for tu in top_users:
        tu["cost"] = round(tu["cost"], 6)

    # ── Active model configuration ────────────────────────────────────
    agent_models = getattr(django_settings, "AGENT_MODELS", {})

    context = {
        "page_title": "Token Economics",
        "tokens_today": tokens_today,
        "tokens_month": tokens_month,
        "cost_today": round(cost_today, 6),
        "cost_month": round(cost_month, 6),
        "cost_per_user": round(cost_per_user, 6),
        "cost_per_post": round(cost_per_post, 6),
        "active_users": active_users,
        "posts_generated": posts_generated,
        "agent_totals": agent_totals,
        "top_users": top_users,
        "model_breakdown": model_breakdown,
        "agent_models": agent_models,
    }
    return render(request, "admin_dashboard/agents/token_economics.html", context)
