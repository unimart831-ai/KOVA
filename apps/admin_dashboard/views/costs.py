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
from apps.agents.models import AgentAction, LLMConfig, UserTokenBucket
from apps.agents.pricing import calculate_token_cost, get_pricing_display_registry
from apps.billing.models import MpesaPayment, get_all_plan_limits
from apps.billing.visual_credits import get_platform_photoroom_usage
from apps.content.models import Post
from apps.products.models import CommercePayment


# ── Non-LLM AI service pricing ──────────────────────────────────────
# Image costs are now tier-routed: each plan uses a different FLUX model.
NON_LLM_PRICING = {
    "whisper-1": {
        "label": "OpenAI Whisper (Voice Memo)",
        "cost_per_minute": 0.006,
        "avg_memo_seconds": 20,
        "provider": "OpenAI",
    },
    "image_together_schnell": {
        "label": "Together.ai FLUX.1-schnell",
        "cost_per_image": 0.003,
        "provider": "Together.ai",
        "plan": "starter",
        "note": "Starter fallback only (images disabled for starter)",
    },
    "image_together_krea": {
        "label": "Together.ai FLUX.1-krea-dev",
        "cost_per_image": 0.025,
        "provider": "Together.ai",
        "plan": "growth",
        "note": "Growth plan — 50 images/month limit",
    },
    "image_together_pro": {
        "label": "Together.ai FLUX.1.1-pro",
        "cost_per_image": 0.04,
        "provider": "Together.ai",
        "plan": "pro / agency",
        "note": "Pro (100/mo) & Agency (500/mo)",
    },
    "image_huggingface": {
        "label": "HuggingFace FLUX.1-schnell",
        "cost_per_image": 0.00,
        "provider": "HuggingFace",
        "note": "Fallback provider (free tier)",
    },
    "image_pollinations": {
        "label": "Pollinations.ai Flux",
        "cost_per_image": 0.00,
        "provider": "Pollinations.ai",
        "note": "Last-resort fallback (free)",
    },
    "graphics_pillow": {
        "label": "Branded Graphics (Pillow)",
        "cost_per_image": 0.00,
        "provider": "On-device (Pillow)",
        "types": ["Quote Cards", "Tip Graphics", "Stat Highlights", "CTA Banners"],
    },
    "visual_photoroom_basic": {
        "label": "Photoroom Basic (Studio polish)",
        "cost_per_image": 0.02,
        "provider": "Photoroom",
        "note": "1 credit per studio polish — $100/5,000 pool; see docs/VISUAL_ENHANCEMENT_SPEC.md",
    },
    "vision_gpt4o_mini": {
        "label": "GPT-4o Mini Vision (Snap to Sell)",
        "cost_per_call": 0.0003,
        "avg_input_tokens": 1500,
        "avg_output_tokens": 400,
        "provider": "OpenAI",
        "note": "Product/service photo analysis — ~800 input tokens for image + prompt, 400 output",
    },
}

# Per-plan image cost (USD per image) — matches tier-routed models
PLAN_IMAGE_COST = {
    "starter": 0.00,    # Images disabled for starter
    "growth": 0.025,    # FLUX.1-krea-dev
    "pro": 0.04,        # FLUX.1.1-pro
    "agency": 0.04,     # FLUX.1.1-pro
}

# Default per-plan token estimates (from cost analysis doc)
# voice_memos = estimated monthly voice memo recordings per user
PLAN_TOKEN_ESTIMATES = {
    "starter": {"input": 40_000, "output": 35_000, "images": 0, "voice_memos": 5},
    "growth": {"input": 260_000, "output": 220_000, "images": 50, "voice_memos": 20},
    "pro": {"input": 1_100_000, "output": 900_000, "images": 100, "voice_memos": 50},
    "agency": {"input": 2_200_000, "output": 1_800_000, "images": 500, "voice_memos": 100},
}

# Infrastructure base costs (USD/month)
INFRA_COSTS = {
    "railway_base": 20.00,
    "email_free_limit": 100,  # emails/day on Resend free tier
    "r2_storage_free_gb": 10,
}


def _get_model_cost(model_name, input_tokens, output_tokens):
    """Calculate USD cost for a model usage. Returns (cost, is_free, is_unknown)."""
    result = calculate_token_cost(model_name, input_tokens, output_tokens)
    return result["cost_usd"], result["is_free"], result["is_unknown"]


def _aggregate_actions_cost(qs):
    """Sum LLM cost across a queryset grouped by model."""
    total = 0.0
    unknown_models: set[str] = set()
    for row in qs.exclude(model_used="").values("model_used").annotate(
        inp=Sum("input_tokens"), out=Sum("output_tokens"),
    ):
        cost, _, is_unknown = _get_model_cost(row["model_used"], row["inp"] or 0, row["out"] or 0)
        total += cost
        if is_unknown:
            unknown_models.add(row["model_used"])
    return total, unknown_models


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
    unknown_model_names: set[str] = set()
    model_cost_rows = []
    for row in model_costs_30d:
        cost, is_free, is_unknown = _get_model_cost(
            row["model_used"],
            row["total_input"] or 0,
            row["total_output"] or 0,
        )
        if is_unknown:
            unknown_model_names.add(row["model_used"])
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
            "is_unknown": is_unknown,
            "avg_duration_ms": round(row["avg_duration"] or 0),
        })

    # 7d and 24h costs
    cost_7d, unknown_7d = _aggregate_actions_cost(actions_7d)
    cost_24h, unknown_24h = _aggregate_actions_cost(actions_24h)
    unknown_model_names |= unknown_7d | unknown_24h

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
        cost, is_free, is_unknown = _get_model_cost(row["model_used"], row["inp"] or 0, row["out"] or 0)
        if is_unknown:
            unknown_model_names.add(row["model_used"])
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

    # ── 3. Per-plan unit economics (actual LLM + actual images where available) ──
    plan_image_counts = {
        row["user__profile__plan"]: row["count"]
        for row in Post.objects.filter(created_at__gte=last_30d, media_status="generated")
        .values("user__profile__plan")
        .annotate(count=Count("id"))
    }

    plan_drafts: list[dict] = []
    total_active_users = 0
    total_monthly_revenue = Decimal("0")

    for plan_code, plan_label in UserProfile.PlanTier.choices:
        limits = get_all_plan_limits().get(plan_code, {})
        price_usd = float(limits.get("price_usd", 0))
        price_kes = limits.get("price_kes", 0)
        active_count = UserProfile.objects.filter(
            plan=plan_code, subscription_status="active"
        ).count()
        total_active_users += active_count

        plan_actions = actions_30d.filter(user__profile__plan=plan_code)
        plan_tokens = plan_actions.aggregate(
            inp=Sum("input_tokens"), out=Sum("output_tokens"),
            calls=Count("id"),
        )
        avg_input = (plan_tokens["inp"] or 0) / active_count if active_count else 0
        avg_output = (plan_tokens["out"] or 0) / active_count if active_count else 0
        avg_calls = (plan_tokens["calls"] or 0) / active_count if active_count else 0

        plan_model_costs = (
            plan_actions.exclude(model_used="")
            .values("model_used")
            .annotate(inp=Sum("input_tokens"), out=Sum("output_tokens"))
        )
        plan_total_cost = 0.0
        for mc in plan_model_costs:
            c, _, is_unknown = _get_model_cost(mc["model_used"], mc["inp"] or 0, mc["out"] or 0)
            plan_total_cost += c
            if is_unknown:
                unknown_model_names.add(mc["model_used"])

        avg_llm_cost = plan_total_cost / active_count if active_count else 0
        per_image_cost = PLAN_IMAGE_COST.get(plan_code, 0)
        plan_images_30d = plan_image_counts.get(plan_code, 0)
        avg_image_cost = (plan_images_30d * per_image_cost / active_count) if active_count else 0

        est = PLAN_TOKEN_ESTIMATES.get(plan_code, {})
        whisper = NON_LLM_PRICING["whisper-1"]
        voice_cost = (
            est.get("voice_memos", 0)
            * (whisper["avg_memo_seconds"] / 60)
            * whisper["cost_per_minute"]
        )

        revenue_plan = Decimal(str(price_usd)) * active_count
        total_monthly_revenue += revenue_plan

        plan_drafts.append({
            "code": plan_code,
            "label": limits.get("label", plan_label),
            "price_usd": price_usd,
            "price_kes": price_kes,
            "active_count": active_count,
            "avg_calls": round(avg_calls),
            "avg_input_tokens": round(avg_input),
            "avg_output_tokens": round(avg_output),
            "llm_cost": round(avg_llm_cost, 4),
            "image_cost": round(avg_image_cost, 4),
            "voice_cost": round(voice_cost, 4),
            "plan_images_30d": plan_images_30d,
            "revenue_total": round(float(revenue_plan), 2),
            "llm_cost_total": round(plan_total_cost, 2),
        })

    infra_per_user = _calculate_infra_cost_per_user(total_active_users) if total_active_users else 0
    plan_economics = []
    total_monthly_cost = 0.0
    for draft in plan_drafts:
        total_cost_per_user = (
            draft["llm_cost"] + draft["image_cost"] + draft["voice_cost"] + infra_per_user
        )
        margin = (
            (draft["price_usd"] - total_cost_per_user) / draft["price_usd"] * 100
            if draft["price_usd"] > 0 else 0
        )
        total_monthly_cost += total_cost_per_user * draft["active_count"]
        plan_economics.append({
            **draft,
            "infra_cost": round(infra_per_user, 4),
            "total_cost": round(total_cost_per_user, 4),
            "profit": round(draft["price_usd"] - total_cost_per_user, 4),
            "margin": round(margin, 1),
            "cost_total": round(total_cost_per_user * draft["active_count"], 2),
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
        user_model_costs = (
            actions_30d.filter(user_id=u["user_id"])
            .exclude(model_used="")
            .values("model_used")
            .annotate(inp=Sum("input_tokens"), out=Sum("output_tokens"))
        )
        user_cost = 0.0
        for mc in user_model_costs:
            c, _, is_unknown = _get_model_cost(mc["model_used"], mc["inp"] or 0, mc["out"] or 0)
            user_cost += c
            if is_unknown:
                unknown_model_names.add(mc["model_used"])

        plan = u["user__profile__plan"] or "starter"
        revenue = float(get_all_plan_limits().get(plan, {}).get("price_usd", 0))
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
            "note": "LLM cost only — excludes images/voice/infra",
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
            c, _, is_unknown = _get_model_cost(mc["model_used"], mc["inp"] or 0, mc["out"] or 0)
            agent_cost += c
            if is_unknown:
                unknown_model_names.add(mc["model_used"])
        agent_cost_rows.append({
            "agent": row["agent_type"],
            "calls": row["calls"],
            "tokens": row["total"] or 0,
            "input_tokens": row["inp"] or 0,
            "output_tokens": row["out"] or 0,
            "cost": round(agent_cost, 4),
        })

    # ── 5b. Cost by action type (commerce, snap, etc.) ───────────────
    action_type_costs = (
        actions_30d
        .values("action_type")
        .annotate(
            calls=Count("id"),
            inp=Sum("input_tokens"),
            out=Sum("output_tokens"),
            total=Sum("tokens_used"),
        )
        .order_by("-total")
    )
    action_cost_rows = []
    commerce_cost_30d = 0.0
    snap_cost_30d = 0.0
    for row in action_type_costs:
        action_type = row["action_type"] or "unknown"
        action_model_costs = (
            actions_30d.filter(action_type=row["action_type"])
            .exclude(model_used="")
            .values("model_used")
            .annotate(inp=Sum("input_tokens"), out=Sum("output_tokens"))
        )
        action_cost = 0.0
        for mc in action_model_costs:
            c, _, is_unknown = _get_model_cost(mc["model_used"], mc["inp"] or 0, mc["out"] or 0)
            action_cost += c
            if is_unknown:
                unknown_model_names.add(mc["model_used"])
        action_cost_rows.append({
            "action_type": action_type,
            "calls": row["calls"],
            "tokens": row["total"] or 0,
            "cost": round(action_cost, 4),
        })
        if action_type.startswith("commerce."):
            commerce_cost_30d += action_cost
        elif action_type.startswith("snap."):
            snap_cost_30d += action_cost

    # ── 6. Revenue (subscription M-Pesa + commerce checkout) ────────
    actual_subscription_revenue_30d = MpesaPayment.objects.filter(
        status="completed", completed_at__gte=last_30d,
    ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
    commerce_checkout_revenue_30d = CommercePayment.objects.filter(
        status=CommercePayment.Status.COMPLETED,
        completed_at__gte=last_30d,
    ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

    # ── 6b. UserTokenBucket reconciliation (enforcement ledger) ─────
    bucket_stats = UserTokenBucket.objects.filter(
        period_date__gte=(now - timedelta(days=30)).date(),
    ).aggregate(
        cost_micros=Sum("cost_usd_micros"),
        input_tokens=Sum("input_tokens"),
        output_tokens=Sum("output_tokens"),
        calls=Sum("call_count"),
    )
    bucket_cost_30d = (bucket_stats["cost_micros"] or 0) / 1_000_000
    bucket_tokens_30d = (bucket_stats["input_tokens"] or 0) + (bucket_stats["output_tokens"] or 0)

    # ── Current LLM config for display ──────────────────────────────
    config = LLMConfig.load()

    # ── 7. Image generation stats (30d) ─────────────────────────────
    image_stats_30d = (
        Post.objects.filter(created_at__gte=last_30d)
        .values("media_status")
        .annotate(count=Count("id"))
    )
    image_stats = {s["media_status"]: s["count"] for s in image_stats_30d}
    images_generated = image_stats.get("generated", 0)
    images_failed = image_stats.get("failed", 0)
    images_pending = image_stats.get("pending", 0)

    # Estimated actual image cost (30d) — by plan of post owner
    image_cost_30d = 0.0
    plan_image_counts = (
        Post.objects.filter(created_at__gte=last_30d, media_status="generated")
        .values("user__profile__plan")
        .annotate(count=Count("id"))
    )
    for pic in plan_image_counts:
        plan = pic["user__profile__plan"] or "starter"
        image_cost_30d += pic["count"] * PLAN_IMAGE_COST.get(plan, 0)

    # ── 8. AI Vision stats (Snap to Sell) ────────────────────────────
    vision_actions_30d = actions_30d.filter(action_type__startswith="snap.")
    vision_stats = vision_actions_30d.aggregate(
        calls=Count("id"),
        total_input=Sum("input_tokens"),
        total_output=Sum("output_tokens"),
        total_tokens=Sum("tokens_used"),
    )
    vision_calls_30d = vision_stats["calls"] or 0
    vision_tokens_30d = vision_stats["total_tokens"] or 0
    # Vision cost: calculated from actual token usage
    vision_cost_30d = 0.0
    vision_model_usage = (
        vision_actions_30d.exclude(model_used="")
        .values("model_used")
        .annotate(inp=Sum("input_tokens"), out=Sum("output_tokens"))
    )
    for row in vision_model_usage:
        c, _, is_unknown = _get_model_cost(row["model_used"], row["inp"] or 0, row["out"] or 0)
        vision_cost_30d += c
        if is_unknown:
            unknown_model_names.add(row["model_used"])
    vision_single = vision_actions_30d.filter(action_type="snap.vision").count()
    vision_batch = vision_actions_30d.filter(action_type="snap.vision_batch").count()
    vision_carousel = vision_actions_30d.filter(action_type="snap.carousel").count()
    vision_reel = vision_actions_30d.filter(action_type="snap.reel").count()

    total_ai_cost_30d = round(total_cost_30d + image_cost_30d + vision_cost_30d, 4)
    cost_per_token = (
        total_cost_30d / token_totals_30d["total"]
        if token_totals_30d["total"] else 0
    )
    avg_cost_per_image = (
        image_cost_30d / images_generated if images_generated else 0
    )
    bucket_vs_actions_delta = round(total_cost_30d - bucket_cost_30d, 4)

    photoroom_pool = get_platform_photoroom_usage()
    photoroom_cost_30d = round(
        photoroom_pool["used"] * photoroom_pool["cost_per_image"],
        4,
    )

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
        "cost_per_token": cost_per_token,
        "avg_cost_per_image": avg_cost_per_image,
        "total_ai_cost_30d": total_ai_cost_30d,
        # Revenue
        "total_monthly_revenue": round(float(total_monthly_revenue), 2),
        "total_monthly_cost": round(total_monthly_cost, 2),
        "gross_margin": round(
            (float(total_monthly_revenue) - total_monthly_cost) / float(total_monthly_revenue) * 100, 1
        ) if float(total_monthly_revenue) > 0 else 0,
        "estimated_mrr_usd": round(float(total_monthly_revenue), 2),
        "actual_subscription_revenue_30d": float(actual_subscription_revenue_30d),
        "commerce_checkout_revenue_30d": float(commerce_checkout_revenue_30d),
        "actual_revenue_30d": float(actual_subscription_revenue_30d),
        "total_active_users": total_active_users,
        # Bucket reconciliation
        "bucket_cost_30d": round(bucket_cost_30d, 4),
        "bucket_tokens_30d": bucket_tokens_30d,
        "bucket_vs_actions_delta": bucket_vs_actions_delta,
        "unknown_models": sorted(unknown_model_names),
        # Feature slices
        "commerce_cost_30d": round(commerce_cost_30d, 4),
        "snap_cost_30d": round(snap_cost_30d, 4),
        # Image generation stats
        "images_generated_30d": images_generated,
        "images_failed_30d": images_failed,
        "images_pending_30d": images_pending,
        "image_cost_30d": round(image_cost_30d, 4),
        "plan_image_cost": PLAN_IMAGE_COST,
        # Vision AI stats (Snap to Sell)
        "vision_calls_30d": vision_calls_30d,
        "vision_tokens_30d": vision_tokens_30d,
        "vision_cost_30d": round(vision_cost_30d, 4),
        "vision_single": vision_single,
        "vision_batch": vision_batch,
        "vision_carousel": vision_carousel,
        "vision_reel": vision_reel,
        # Charts
        "daily_cost_chart_json": daily_cost_chart,
        # Tables
        "model_cost_rows": model_cost_rows,
        "plan_economics": plan_economics,
        "top_user_rows": top_user_rows,
        "agent_cost_rows": agent_cost_rows,
        "action_cost_rows": action_cost_rows,
        # Config
        "config": config,
        "model_pricing_json": get_pricing_display_registry(),
        "non_llm_pricing": NON_LLM_PRICING,
        "plan_limits": get_all_plan_limits(),
        "infra_costs": INFRA_COSTS,
        "plan_token_estimates_json": PLAN_TOKEN_ESTIMATES,
        "photoroom_pool": photoroom_pool,
        "photoroom_cost_30d": photoroom_cost_30d,
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
    image_cost_growth = _float("image_cost_growth", 0.025)
    image_cost_pro = _float("image_cost_pro", 0.04)
    voice_cost_per_min = _float("voice_cost_per_min", 0.006)
    hosting_cost = _float("hosting_cost", 20.0)

    results = []
    total_revenue = 0.0
    total_cost = 0.0

    plan_image_costs = {
        "starter": 0.00,
        "growth": image_cost_growth,
        "pro": image_cost_pro,
        "agency": image_cost_pro,
    }

    for plan_code, user_count in [
        ("starter", starter_users), ("growth", growth_users),
        ("pro", pro_users), ("agency", agency_users),
    ]:
        if user_count <= 0:
            continue
        limits = get_all_plan_limits().get(plan_code, {})
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
        per_img = plan_image_costs.get(plan_code, 0)
        img_cost = images * per_img
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
