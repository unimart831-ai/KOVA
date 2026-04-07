"""
Cost Economics Dashboard — Full financial visibility for Kova Agent.

Sections:
1. Real-time AI cost tracking (actual token usage → estimated USD cost)
2. Per-plan unit economics (revenue vs cost per plan tier)
3. Per-user profitability (top consumers, underwater users)
4. Cost projections / scenario calculator (HTMX endpoint)
5. Infrastructure cost tracking
"""

import json
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.admin_dashboard.decorators import superuser_required
from apps.agents.models import AgentAction, LLMConfig
from apps.billing.models import PLAN_LIMITS, MpesaPayment


# ── Model pricing (USD per 1M tokens) ───────────────────────────────────
# Kept here so admin can see what rates the system uses. Updated manually
# when provider pricing changes. Key = model identifier substring.
MODEL_PRICING = {
    # Free OpenRouter models
    "qwen/qwen3": {"input": 0.00, "output": 0.00, "label": "Qwen 3 (Free)"},
    "stepfun/step-3.5-flash:free": {"input": 0.00, "output": 0.00, "label": "StepFun Flash (Free)"},
    "nvidia/nemotron": {"input": 0.00, "output": 0.00, "label": "Nemotron (Free)"},
    "minimax/minimax": {"input": 0.00, "output": 0.00, "label": "MiniMax (Free)"},
    "mistralai/mistral": {"input": 0.00, "output": 0.00, "label": "Mistral (Free)"},
    ":free": {"input": 0.00, "output": 0.00, "label": "Free Model"},
    # Paid — Kova Recommended Stack
    "deepseek-v3.2": {"input": 0.26, "output": 0.38, "label": "DeepSeek V3.2 ★ PRIMARY FALLBACK"},
    "deepseek-v3": {"input": 0.26, "output": 0.38, "label": "DeepSeek V3"},
    "deepseek-r1": {"input": 0.55, "output": 2.19, "label": "DeepSeek R1"},
    "gemini-3-flash": {"input": 0.50, "output": 3.00, "label": "Gemini 3 Flash ★ PRO/AGENCY"},
    "gemini-3.1-flash-lite": {"input": 0.25, "output": 1.50, "label": "Gemini 3.1 Flash Lite"},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60, "label": "Gemini 2.5 Flash"},
    "stepfun/step-3.5-flash": {"input": 0.10, "output": 0.30, "label": "Step 3.5 Flash ★ BULK TASKS"},
    # Paid — OpenAI
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "label": "GPT-4o Mini (old fallback)"},
    "gpt-4o": {"input": 2.50, "output": 10.00, "label": "GPT-4o"},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00, "label": "GPT-4 Turbo"},
    "o3-mini": {"input": 1.10, "output": 4.40, "label": "o3-mini"},
    # Paid — Anthropic
    "claude-3-5-haiku": {"input": 0.80, "output": 4.00, "label": "Claude 3.5 Haiku"},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00, "label": "Claude 3.5 Sonnet"},
    "claude-sonnet-4": {"input": 3.00, "output": 15.00, "label": "Claude Sonnet 4"},
}

# ── Non-LLM AI service pricing ──────────────────────────────────────
NON_LLM_PRICING = {
    "whisper-1": {
        "label": "OpenAI Whisper (Voice Memo)",
        "cost_per_minute": 0.006,
        "avg_memo_seconds": 20,
        "provider": "OpenAI",
    },
    "image_together": {
        "label": "Together.ai FLUX.1-schnell",
        "cost_per_image": 0.00,
        "provider": "Together.ai",
        "priority": 1,
    },
    "image_huggingface": {
        "label": "HuggingFace FLUX.1-schnell",
        "cost_per_image": 0.00,
        "provider": "HuggingFace",
        "priority": 2,
    },
    "image_pollinations": {
        "label": "Pollinations.ai Flux",
        "cost_per_image": 0.005,
        "provider": "Pollinations.ai",
        "priority": 3,
    },
    "graphics_pillow": {
        "label": "Branded Graphics (Pillow)",
        "cost_per_image": 0.00,
        "provider": "On-device (Pillow)",
        "types": ["Quote Cards", "Tip Graphics", "Stat Highlights", "CTA Banners"],
    },
}

# Default per-plan token estimates (from cost analysis doc)
# voice_memos = estimated monthly voice memo recordings per user
PLAN_TOKEN_ESTIMATES = {
    "starter": {"input": 55_000, "output": 50_000, "images": 5, "voice_memos": 5},
    "growth": {"input": 260_000, "output": 220_000, "images": 50, "voice_memos": 20},
    "pro": {"input": 1_100_000, "output": 900_000, "images": 200, "voice_memos": 50},
    "agency": {"input": 2_200_000, "output": 1_800_000, "images": 500, "voice_memos": 100},
}

# Infrastructure base costs (USD/month)
INFRA_COSTS = {
    "railway_base": 20.00,
    "email_free_limit": 100,  # emails/day on Resend free tier
    "r2_storage_free_gb": 10,
    "image_cost_free": 0.00,  # HuggingFace FLUX.1-schnell
    "image_cost_paid": 0.005,  # Gemini 2.5 Flash per image
}


def _get_model_cost(model_name, input_tokens, output_tokens):
    """Calculate USD cost for a model usage. Returns (cost, is_free)."""
    if not model_name:
        return 0.0, True
    model_lower = model_name.lower()
    for key, pricing in MODEL_PRICING.items():
        if key.lower() in model_lower:
            input_cost = (input_tokens / 1_000_000) * pricing["input"]
            output_cost = (output_tokens / 1_000_000) * pricing["output"]
            is_free = pricing["input"] == 0 and pricing["output"] == 0
            return round(input_cost + output_cost, 6), is_free
    # Unknown model — assume free (OpenRouter free tier)
    return 0.0, True


def _calculate_infra_cost_per_user(total_users):
    """Estimate infrastructure cost per user given total user count."""
    if total_users <= 0:
        return INFRA_COSTS["railway_base"]
    # Sub-linear scaling from the cost doc
    if total_users <= 50:
        railway = 25.0
    elif total_users <= 100:
        railway = 30.0
    elif total_users <= 500:
        railway = 50.0
    elif total_users <= 1000:
        railway = 80.0
    elif total_users <= 5000:
        railway = 200.0
    else:
        railway = 400.0
    return round(railway / total_users, 4)


@superuser_required
def cost_overview(request):
    """Main cost economics dashboard."""
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    # ── 1. Actual AI cost from AgentAction data ─────────────────────
    actions_30d = AgentAction.objects.filter(created_at__gte=last_30d)
    actions_7d = AgentAction.objects.filter(created_at__gte=last_7d)
    actions_24h = AgentAction.objects.filter(created_at__gte=last_24h)

    # Aggregate by model for cost calculation
    model_costs_30d = (
        actions_30d
        .exclude(model_used="")
        .values("model_used")
        .annotate(
            calls=Count("id"),
            total_input=Sum("input_tokens"),
            total_output=Sum("output_tokens"),
            total_tokens=Sum("tokens_used"),
            successes=Count("id", filter=Q(status="completed")),
            failures=Count("id", filter=Q(status="failed")),
            avg_duration=Avg("duration_ms", filter=Q(duration_ms__gt=0)),
        )
        .order_by("-total_tokens")
    )

    total_cost_30d = 0.0
    total_paid_cost_30d = 0.0
    total_free_calls = 0
    total_paid_calls = 0
    model_cost_rows = []
    for row in model_costs_30d:
        cost, is_free = _get_model_cost(
            row["model_used"],
            row["total_input"] or 0,
            row["total_output"] or 0,
        )
        total_cost_30d += cost
        if is_free:
            total_free_calls += row["calls"]
        else:
            total_paid_calls += row["calls"]
            total_paid_cost_30d += cost
        model_cost_rows.append({
            "model": row["model_used"],
            "calls": row["calls"],
            "input_tokens": row["total_input"] or 0,
            "output_tokens": row["total_output"] or 0,
            "total_tokens": row["total_tokens"] or 0,
            "successes": row["successes"],
            "failures": row["failures"],
            "cost_usd": round(cost, 4),
            "is_free": is_free,
            "avg_duration_ms": round(row["avg_duration"] or 0),
        })

    # 7d and 24h costs
    cost_7d = 0.0
    for row in actions_7d.exclude(model_used="").values("model_used").annotate(
        inp=Sum("input_tokens"), out=Sum("output_tokens")
    ):
        c, _ = _get_model_cost(row["model_used"], row["inp"] or 0, row["out"] or 0)
        cost_7d += c

    cost_24h = 0.0
    for row in actions_24h.exclude(model_used="").values("model_used").annotate(
        inp=Sum("input_tokens"), out=Sum("output_tokens")
    ):
        c, _ = _get_model_cost(row["model_used"], row["inp"] or 0, row["out"] or 0)
        cost_24h += c

    # Total tokens
    token_totals_30d = actions_30d.aggregate(
        calls=Count("id"),
        total=Sum("tokens_used"),
        inp=Sum("input_tokens"),
        out=Sum("output_tokens"),
    )

    # ── 2. Daily cost trend (last 30 days) ──────────────────────────
    daily_data = (
        actions_30d
        .exclude(model_used="")
        .annotate(day=TruncDate("created_at"))
        .values("day", "model_used")
        .annotate(
            inp=Sum("input_tokens"),
            out=Sum("output_tokens"),
            calls=Count("id"),
        )
        .order_by("day")
    )
    daily_cost_map = {}
    for row in daily_data:
        day_str = row["day"].strftime("%Y-%m-%d")
        cost, is_free = _get_model_cost(row["model_used"], row["inp"] or 0, row["out"] or 0)
        if day_str not in daily_cost_map:
            daily_cost_map[day_str] = {"free_cost": 0.0, "paid_cost": 0.0, "calls": 0, "tokens": 0}
        if is_free:
            daily_cost_map[day_str]["free_cost"] += cost
        else:
            daily_cost_map[day_str]["paid_cost"] += cost
        daily_cost_map[day_str]["calls"] += row["calls"]
        daily_cost_map[day_str]["tokens"] += (row["inp"] or 0) + (row["out"] or 0)

    daily_cost_chart = []
    for i in range(29, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        entry = daily_cost_map.get(day, {"free_cost": 0, "paid_cost": 0, "calls": 0, "tokens": 0})
        daily_cost_chart.append({
            "date": day,
            "paid_cost": round(entry["paid_cost"], 4),
            "free_cost": round(entry["free_cost"], 4),
            "calls": entry["calls"],
            "tokens": entry["tokens"],
        })

    # ── 3. Per-plan unit economics (actual data) ────────────────────
    plan_economics = []
    total_active_users = 0
    total_monthly_revenue = Decimal("0")
    total_monthly_cost = 0.0

    for plan_code, plan_label in UserProfile.PlanTier.choices:
        limits = PLAN_LIMITS.get(plan_code, {})
        price_usd = float(limits.get("price_usd", 0))
        price_kes = limits.get("price_kes", 0)
        active_count = UserProfile.objects.filter(
            plan=plan_code, subscription_status="active"
        ).count()
        total_active_users += active_count

        # Actual token usage for this plan's users (30d)
        plan_actions = actions_30d.filter(user__profile__plan=plan_code)
        plan_tokens = plan_actions.aggregate(
            inp=Sum("input_tokens"), out=Sum("output_tokens"),
            calls=Count("id"),
        )
        avg_input = 0
        avg_output = 0
        avg_calls = 0
        if active_count > 0:
            avg_input = (plan_tokens["inp"] or 0) / active_count
            avg_output = (plan_tokens["out"] or 0) / active_count
            avg_calls = (plan_tokens["calls"] or 0) / active_count

        # Calculate cost per user for this plan (using most expensive model seen)
        plan_model_costs = (
            plan_actions.exclude(model_used="")
            .values("model_used")
            .annotate(inp=Sum("input_tokens"), out=Sum("output_tokens"))
        )
        plan_total_cost = 0.0
        for mc in plan_model_costs:
            c, _ = _get_model_cost(mc["model_used"], mc["inp"] or 0, mc["out"] or 0)
            plan_total_cost += c

        avg_cost_per_user = plan_total_cost / active_count if active_count else 0
        # Image cost estimate (paid fallback only — primary providers are free)
        est = PLAN_TOKEN_ESTIMATES.get(plan_code, {})
        image_cost = est.get("images", 0) * INFRA_COSTS["image_cost_paid"] if plan_code != "starter" else 0

        # Voice cost estimate (Whisper @ $0.006/min, avg ~20s memo)
        whisper = NON_LLM_PRICING["whisper-1"]
        voice_cost = (
            est.get("voice_memos", 0)
            * (whisper["avg_memo_seconds"] / 60)
            * whisper["cost_per_minute"]
        )

        infra_per_user = _calculate_infra_cost_per_user(total_active_users) if total_active_users > 0 else 2.0

        total_cost_per_user = avg_cost_per_user + image_cost + voice_cost + infra_per_user
        margin = ((price_usd - total_cost_per_user) / price_usd * 100) if price_usd > 0 else 0
        profit = price_usd - total_cost_per_user

        revenue_plan = Decimal(str(price_usd)) * active_count
        total_monthly_revenue += revenue_plan
        total_monthly_cost += total_cost_per_user * active_count

        plan_economics.append({
            "code": plan_code,
            "label": limits.get("label", plan_label),
            "price_usd": price_usd,
            "price_kes": price_kes,
            "active_count": active_count,
            "avg_calls": round(avg_calls),
            "avg_input_tokens": round(avg_input),
            "avg_output_tokens": round(avg_output),
            "llm_cost": round(avg_cost_per_user, 4),
            "image_cost": round(image_cost, 4),
            "voice_cost": round(voice_cost, 4),
            "infra_cost": round(infra_per_user, 4),
            "total_cost": round(total_cost_per_user, 4),
            "profit": round(profit, 4),
            "margin": round(margin, 1),
            "revenue_total": round(float(revenue_plan), 2),
            "cost_total": round(total_cost_per_user * active_count, 2),
        })

    # ── 4. Top consuming users (30d) ────────────────────────────────
    top_users = (
        actions_30d
        .values("user_id", "user__email", "user__profile__plan", "user__profile__company_name")
        .annotate(
            calls=Count("id"),
            total_tokens=Sum("tokens_used"),
            input_tokens=Sum("input_tokens"),
            output_tokens=Sum("output_tokens"),
        )
        .order_by("-total_tokens")[:15]
    )
    top_user_rows = []
    for u in top_users:
        cost, _ = _get_model_cost("mixed", u["input_tokens"] or 0, u["output_tokens"] or 0)
        # Re-calculate with actual models for this user
        user_model_costs = (
            actions_30d.filter(user_id=u["user_id"])
            .exclude(model_used="")
            .values("model_used")
            .annotate(inp=Sum("input_tokens"), out=Sum("output_tokens"))
        )
        user_cost = 0.0
        for mc in user_model_costs:
            c, _ = _get_model_cost(mc["model_used"], mc["inp"] or 0, mc["out"] or 0)
            user_cost += c

        plan = u["user__profile__plan"] or "starter"
        revenue = float(PLAN_LIMITS.get(plan, {}).get("price_usd", 0))
        top_user_rows.append({
            "email": u["user__email"] or "—",
            "company": u["user__profile__company_name"] or "—",
            "plan": plan,
            "calls": u["calls"],
            "tokens": u["total_tokens"] or 0,
            "cost": round(user_cost, 4),
            "revenue": revenue,
            "profit": round(revenue - user_cost, 4),
            "profitable": user_cost <= revenue,
        })

    # ── 5. Cost by agent type (30d) ─────────────────────────────────
    agent_costs = (
        actions_30d
        .values("agent_type")
        .annotate(
            calls=Count("id"),
            inp=Sum("input_tokens"),
            out=Sum("output_tokens"),
            total=Sum("tokens_used"),
        )
        .order_by("-total")
    )
    agent_cost_rows = []
    for row in agent_costs:
        # Calculate cost across all models for this agent
        agent_model_costs = (
            actions_30d.filter(agent_type=row["agent_type"])
            .exclude(model_used="")
            .values("model_used")
            .annotate(inp=Sum("input_tokens"), out=Sum("output_tokens"))
        )
        agent_cost = 0.0
        for mc in agent_model_costs:
            c, _ = _get_model_cost(mc["model_used"], mc["inp"] or 0, mc["out"] or 0)
            agent_cost += c
        agent_cost_rows.append({
            "agent": row["agent_type"],
            "calls": row["calls"],
            "tokens": row["total"] or 0,
            "input_tokens": row["inp"] or 0,
            "output_tokens": row["out"] or 0,
            "cost": round(agent_cost, 4),
        })

    # ── 6. Monthly revenue from billing ─────────────────────────────
    actual_revenue_30d = MpesaPayment.objects.filter(
        status="completed", completed_at__gte=last_30d,
    ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

    # ── Current LLM config for display ──────────────────────────────
    config = LLMConfig.load()

    context = {
        "page_title": "Cost Economics",
        # Summary cards
        "cost_24h": round(cost_24h, 4),
        "cost_7d": round(cost_7d, 4),
        "cost_30d": round(total_cost_30d, 4),
        "paid_cost_30d": round(total_paid_cost_30d, 4),
        "free_calls_30d": total_free_calls,
        "paid_calls_30d": total_paid_calls,
        "total_calls_30d": token_totals_30d["calls"] or 0,
        "total_tokens_30d": token_totals_30d["total"] or 0,
        "total_input_30d": token_totals_30d["inp"] or 0,
        "total_output_30d": token_totals_30d["out"] or 0,
        # Revenue
        "total_monthly_revenue": round(float(total_monthly_revenue), 2),
        "total_monthly_cost": round(total_monthly_cost, 2),
        "gross_margin": round(
            (float(total_monthly_revenue) - total_monthly_cost) / float(total_monthly_revenue) * 100, 1
        ) if float(total_monthly_revenue) > 0 else 0,
        "actual_revenue_30d": float(actual_revenue_30d),
        "total_active_users": total_active_users,
        # Charts
        "daily_cost_chart_json": daily_cost_chart,
        # Tables
        "model_cost_rows": model_cost_rows,
        "plan_economics": plan_economics,
        "top_user_rows": top_user_rows,
        "agent_cost_rows": agent_cost_rows,
        # Config
        "config": config,
        "model_pricing_json": {k: v for k, v in MODEL_PRICING.items()},
        "non_llm_pricing": NON_LLM_PRICING,
        "plan_limits": PLAN_LIMITS,
        "infra_costs": INFRA_COSTS,
        "plan_token_estimates_json": PLAN_TOKEN_ESTIMATES,
    }
    return render(request, "admin_dashboard/costs/overview.html", context)


@superuser_required
def cost_calculator(request):
    """
    HTMX endpoint: scenario cost estimator.
    Accepts user counts per plan, model choices, and returns projected costs.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        data = json.loads(request.body) if request.content_type == "application/json" else request.POST
    except (json.JSONDecodeError, ValueError):
        data = request.POST

    # Parse inputs with defaults
    def _int(key, default=0):
        try:
            return max(0, int(data.get(key, default)))
        except (TypeError, ValueError):
            return default

    def _float(key, default=0.0):
        try:
            return max(0.0, float(data.get(key, default)))
        except (TypeError, ValueError):
            return default

    starter_users = _int("starter_users", 0)
    growth_users = _int("growth_users", 0)
    pro_users = _int("pro_users", 0)
    agency_users = _int("agency_users", 0)
    total_users = starter_users + growth_users + pro_users + agency_users

    # Model pricing overrides
    premium_input = _float("premium_input_price", 0.50)
    premium_output = _float("premium_output_price", 3.00)
    workhorse_input = _float("workhorse_input_price", 0.26)
    workhorse_output = _float("workhorse_output_price", 0.38)
    fast_input = _float("fast_input_price", 0.26)
    fast_output = _float("fast_output_price", 0.38)
    image_cost_per = _float("image_cost", 0.005)
    voice_cost_per_min = _float("voice_cost_per_min", 0.006)
    hosting_cost = _float("hosting_cost", 20.0)

    results = []
    total_revenue = 0.0
    total_cost = 0.0

    for plan_code, user_count in [
        ("starter", starter_users), ("growth", growth_users),
        ("pro", pro_users), ("agency", agency_users),
    ]:
        if user_count <= 0:
            continue
        limits = PLAN_LIMITS.get(plan_code, {})
        est = PLAN_TOKEN_ESTIMATES.get(plan_code, {})
        price_usd = float(limits.get("price_usd", 0))
        revenue = price_usd * user_count

        # Token estimates (split roughly 40% premium, 35% workhorse, 25% fast)
        inp = est.get("input", 0)
        out = est.get("output", 0)
        premium_frac = 0.40
        workhorse_frac = 0.35
        fast_frac = 0.25

        llm_cost_per_user = (
            (inp * premium_frac / 1_000_000 * premium_input)
            + (out * premium_frac / 1_000_000 * premium_output)
            + (inp * workhorse_frac / 1_000_000 * workhorse_input)
            + (out * workhorse_frac / 1_000_000 * workhorse_output)
            + (inp * fast_frac / 1_000_000 * fast_input)
            + (out * fast_frac / 1_000_000 * fast_output)
        )

        images = est.get("images", 0)
        img_cost = images * (0 if plan_code == "starter" else image_cost_per)
        voice_memos = est.get("voice_memos", 0)
        voice_cost = voice_memos * (20 / 60) * voice_cost_per_min  # 20s avg memo
        infra = hosting_cost / total_users if total_users > 0 else 0
        cost_per_user = llm_cost_per_user + img_cost + voice_cost + infra
        total_plan_cost = cost_per_user * user_count

        total_revenue += revenue
        total_cost += total_plan_cost

        margin = ((price_usd - cost_per_user) / price_usd * 100) if price_usd > 0 else 0

        results.append({
            "plan": limits.get("label", plan_code),
            "users": user_count,
            "price_usd": price_usd,
            "revenue": round(revenue, 2),
            "llm_cost": round(llm_cost_per_user, 4),
            "image_cost": round(img_cost, 4),
            "voice_cost": round(voice_cost, 4),
            "infra_cost": round(infra, 4),
            "total_cost_per_user": round(cost_per_user, 4),
            "total_cost": round(total_plan_cost, 2),
            "margin": round(margin, 1),
            "profit_per_user": round(price_usd - cost_per_user, 4),
        })

    gross_profit = total_revenue - total_cost
    overall_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0

    return JsonResponse({
        "results": results,
        "summary": {
            "total_users": total_users,
            "total_revenue": round(total_revenue, 2),
            "total_cost": round(total_cost, 2),
            "gross_profit": round(gross_profit, 2),
            "overall_margin": round(overall_margin, 1),
            "hosting_cost": hosting_cost,
        },
    })
