import json
from datetime import timedelta

from django.contrib import messages
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.admin_dashboard.decorators import superuser_required
from apps.agents.models import AgentAction, LLMConfig
from apps.agents.pricing import calculate_token_cost
from apps.billing.models import PLAN_LIMITS, get_all_plan_limits


# ── Image model catalog for the quick-select UI ─────────────────────────
POPULAR_IMAGE_MODELS = {
    "FLUX (Together.ai)": [
        ("black-forest-labs/FLUX.1-schnell", "FLUX.1 Schnell — ~$0.003/img · fast, good quality"),
        ("black-forest-labs/FLUX.1-krea-dev", "FLUX.1 Krea Dev — ~$0.025/img · better detail"),
        ("black-forest-labs/FLUX.1.1-pro", "FLUX.1.1 Pro — $0.04/img · best FLUX quality"),
        ("black-forest-labs/FLUX.1-kontext-pro", "FLUX.1 Kontext Pro — $0.04/img · image editing"),
        ("black-forest-labs/FLUX.2-pro", "FLUX.2 Pro — latest generation"),
        ("black-forest-labs/FLUX.2-dev", "FLUX.2 Dev — latest dev tier"),
    ],
    "Google Imagen (Together.ai)": [
        ("google/imagen-4.0-fast", "Imagen 4.0 Fast — $0.02/img"),
        ("google/imagen-4.0-preview", "Imagen 4.0 Preview — $0.04/img"),
        ("google/imagen-4.0-ultra", "Imagen 4.0 Ultra — $0.06/img · highest quality"),
    ],
    "Other (Together.ai)": [
        ("ByteDance-Seed/Seedream-4.0", "Seedream 4.0 — $0.03/img"),
        ("ideogram/ideogram-3.0", "Ideogram 3.0 — $0.06/img · text in images"),
        ("RunDiffusion/Juggernaut-pro-flux", "Juggernaut Pro — $0.005/img · budget"),
        ("stabilityai/stable-diffusion-xl-base-1.0", "SDXL — $0.002/img · cheapest"),
    ],
}

# Default image models per plan (mirrors TIER_IMAGE_MODELS in media.py)
DEFAULT_IMAGE_PLAN_MODELS = {
    "starter": {"model": "black-forest-labs/FLUX.1-schnell", "provider": "together", "price": "~$0.003"},
    "growth":  {"model": "black-forest-labs/FLUX.1-krea-dev", "provider": "together", "price": "~$0.025"},
    "pro":     {"model": "black-forest-labs/FLUX.1.1-pro", "provider": "together", "price": "$0.04"},
    "agency":  {"model": "black-forest-labs/FLUX.1.1-pro", "provider": "together", "price": "$0.04"},
}


# ── All available task keys (for the per-task override UI) ───────────────
TASK_KEYS = [
    ("create.generate", "Create → Generate posts"),
    ("create.regenerate", "Create → Regenerate post"),
    ("create.repurpose", "Create → Repurpose post"),
    ("engage.analyze", "Engage → Analyze interactions"),
    ("engage.reply", "Engage → Generate replies"),
    ("analyst.performance", "Analyst → Performance analysis"),
    ("analyst.content_dna", "Analyst → Content DNA extraction"),
    ("analyst.predict", "Analyst → Engagement prediction"),
    ("research.trends", "Research → Trend research"),
    ("research.angles", "Research → Content angles"),
    ("adapt.schedule", "Adapt → Smart scheduling"),
    ("strategist.brief", "Strategist → Daily brief"),
    ("strategist.decide", "Strategist → Strategic decisions"),
    ("snap.vision", "Snap → Vision AI analysis"),
    ("snap.vision_batch", "Snap → Batch vision analysis"),
    ("snap.carousel", "Snap → Carousel compose"),
    ("snap.reel", "Snap → Reel compose"),
    ("commerce.quick_post", "Commerce → Quick post copy"),
    ("commerce.photo_variations", "Commerce → Photo variation copy"),
    ("commerce.fix_and_promote", "Commerce → Fix & promote copy"),
    ("educator.draft_article", "Educator → Draft article"),
    ("educator.compile_digest", "Educator → Compile digest"),
    ("educator.suggest_topics", "Educator → Suggest topics"),
]

# ── Plan tiers for per-plan config UI ────────────────────────────────────
PLAN_TIERS = [
    ("starter", "Starter"),
    ("growth", "Growth"),
    ("pro", "Pro"),
    ("agency", "Agency"),
]

# ── Model presets for one-click configuration ────────────────────────────
MODEL_PRESETS = {
    "free_only": {
        "label": "Phase 2 — Free (Current)",
        "description": "Free models + DeepSeek V3.2 paid fallback. $0.005-$0.05/user/mo.",
        "premium": "qwen/qwen3.6-plus:free",
        "workhorse": "qwen/qwen3.6-plus:free",
        "fast": "stepfun/step-3.5-flash:free",
    },
    "budget_smart": {
        "label": "Phase 3 — DeepSeek Primary",
        "description": "DeepSeek V3.2 all tiers. 89th-percentile quality at $0.26/$0.38/1M. ~$0.05-$2.25/user/mo.",
        "premium": "deepseek/deepseek-v3.2",
        "workhorse": "deepseek/deepseek-v3.2",
        "fast": "deepseek/deepseek-v3.2",
    },
    "quality_tiered": {
        "label": "Phase 3 — Quality (Pro/Agency)",
        "description": "Gemini Flash for creative (Pro/Agency), DeepSeek for rest. ~$2.66-$6.66/user/mo.",
        "premium": "google/gemini-3-flash-preview",
        "workhorse": "deepseek/deepseek-v3.2",
        "fast": "deepseek/deepseek-v3.2",
    },
    "phase4_optimized": {
        "label": "Phase 4 — Optimized",
        "description": "Per-task routing: Gemini creative, DeepSeek reasoning, Step Flash bulk. ~$1.80-$4.50/user/mo.",
        "premium": "google/gemini-3-flash-preview",
        "workhorse": "deepseek/deepseek-v3.2",
        "fast": "stepfun/step-3.5-flash",
    },
}

# ── Popular models for the quick-select UI ──────────────────────────────
POPULAR_MODELS = {
    "Free (OpenRouter)": [
        ("qwen/qwen3.6-plus:free", "Qwen 3.6 Plus — #1 ranked, strong all-round"),
        ("nvidia/nemotron-3-super-120b-a12b:free", "Nemotron 120B — powerful reasoning"),
        ("minimax/minimax-m2.5:free", "MiniMax M2.5 — balanced"),
        ("stepfun/step-3.5-flash:free", "StepFun Flash — fast, frequent empty responses"),
    ],
    "Kova Recommended": [
        ("deepseek/deepseek-v3.2", "DeepSeek V3.2 — $0.26/$0.38/1M · 89th% intel · BEST VALUE"),
        ("google/gemini-3-flash-preview", "Gemini 3 Flash — $0.50/$3/1M · 94th% intel · 7.8% halluc"),
        ("stepfun/step-3.5-flash", "Step 3.5 Flash — $0.10/$0.30/1M · 117 tok/s · bulk tasks"),
    ],
    "Google": [
        ("google/gemini-3-flash-preview", "Gemini 3 Flash — $0.50/$3 per 1M"),
        ("google/gemini-3.1-flash-lite-preview", "Gemini 3.1 Flash Lite — $0.25/$1.50 per 1M"),
        ("google/gemini-2.5-flash-preview", "Gemini 2.5 Flash — $0.15/$0.60 per 1M"),
    ],
    "DeepSeek": [
        ("deepseek/deepseek-v3.2", "DeepSeek V3.2 — $0.26/$0.38 per 1M"),
        ("deepseek/deepseek-r1", "DeepSeek R1 — $0.55/$2.19 per 1M"),
    ],
    "OpenAI": [
        ("gpt-4o-mini", "GPT-4o Mini — $0.15/$0.60 per 1M (+ Vision)"),
        ("gpt-4o", "GPT-4o — $2.50/$10 per 1M"),
    ],
    "Anthropic": [
        ("claude-3-5-haiku-20241022", "Claude 3.5 Haiku — $0.80/$4 per 1M"),
        ("claude-sonnet-4-20250514", "Claude Sonnet 4 — $3/$15 per 1M"),
    ],
}

# Default rate limits per plan
DEFAULT_RATE_LIMITS = {
    "starter": {"max_calls_per_hour": 30, "max_tokens_per_day": 200_000},
    "growth": {"max_calls_per_hour": 100, "max_tokens_per_day": 1_000_000},
    "pro": {"max_calls_per_hour": 300, "max_tokens_per_day": 4_000_000},
    "agency": {"max_calls_per_hour": 600, "max_tokens_per_day": 8_000_000},
}


@superuser_required
def llm_overview(request):
    """Main LLM management page — current config + usage stats."""
    config = LLMConfig.load()
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    # Usage stats
    actions_24h = AgentAction.objects.filter(created_at__gte=last_24h)
    actions_7d = AgentAction.objects.filter(created_at__gte=last_7d)
    actions_30d = AgentAction.objects.filter(created_at__gte=last_30d)

    stats_24h = actions_24h.aggregate(
        total=Count("id"),
        completed=Count("id", filter=Q(status="completed")),
        failed=Count("id", filter=Q(status="failed")),
        tokens=Sum("tokens_used"),
        input_tokens=Sum("input_tokens"),
        output_tokens=Sum("output_tokens"),
    )
    stats_7d = actions_7d.aggregate(
        total=Count("id"),
        tokens=Sum("tokens_used"),
        input_tokens=Sum("input_tokens"),
        output_tokens=Sum("output_tokens"),
    )

    # Model usage breakdown (last 7 days) with cost
    model_usage = (
        actions_7d
        .exclude(model_used="")
        .values("model_used")
        .annotate(
            calls=Count("id"),
            total_tokens=Sum("tokens_used"),
            input_tokens=Sum("input_tokens"),
            output_tokens=Sum("output_tokens"),
            successes=Count("id", filter=Q(status="completed")),
            failures=Count("id", filter=Q(status="failed")),
            avg_duration=Avg("duration_ms", filter=Q(duration_ms__gt=0)),
        )
        .order_by("-calls")
    )
    model_usage_rows = []
    cost_7d = 0.0
    unknown_models_7d: set[str] = set()
    for row in model_usage:
        cost_info = calculate_token_cost(
            row["model_used"], row["input_tokens"] or 0, row["output_tokens"] or 0,
        )
        cost_7d += cost_info["cost_usd"]
        if cost_info["is_unknown"]:
            unknown_models_7d.add(row["model_used"])
        model_usage_rows.append({**row, **cost_info, "cost_usd": round(cost_info["cost_usd"], 4)})

    cost_30d = 0.0
    unknown_models_30d: set[str] = set()
    for row in actions_30d.exclude(model_used="").values("model_used").annotate(
        inp=Sum("input_tokens"), out=Sum("output_tokens"),
    ):
        cost_info = calculate_token_cost(row["model_used"], row["inp"] or 0, row["out"] or 0)
        cost_30d += cost_info["cost_usd"]
        if cost_info["is_unknown"]:
            unknown_models_30d.add(row["model_used"])

    # Model health — failure rate per model (last 7d)
    model_health = []
    for row in model_usage_rows:
        total = row["calls"]
        failures = row["failures"]
        rate = (failures / total * 100) if total > 0 else 0
        model_health.append({
            "model": row["model_used"],
            "calls": total,
            "failures": failures,
            "failure_rate": round(rate, 1),
            "healthy": rate < 10,
            "warning": 10 <= rate < 30,
            "critical": rate >= 30,
            "avg_ms": round(row["avg_duration"] or 0),
            "cost_usd": row.get("cost_usd", 0),
            "is_unknown": row.get("is_unknown", False),
        })

    # Paid fallback usage (how often are we escalating?)
    paid_model = config.paid_fallback_model if config.pk else "gpt-4o-mini"
    paid_fallback_count_7d = actions_7d.filter(model_used=paid_model).count() if paid_model else 0

    # Daily token trend (last 30 days)
    daily_tokens = list(
        actions_30d
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(tokens=Sum("tokens_used"), calls=Count("id"))
        .order_by("date")
    )

    # Build current task mapping for display
    task_models = config.get_task_models() if config.pk else {}
    task_config_display = []
    for key, label in TASK_KEYS:
        current = task_models.get(key, "")
        is_override = key in (config.task_model_overrides or {}) if config.pk else False
        tier = _get_tier_for_task(key)
        task_config_display.append({
            "key": key,
            "label": label,
            "current_model": current,
            "tier": tier,
            "is_override": is_override,
        })

    # Build per-plan model config display
    plan_model_overrides = config.plan_model_overrides if config.pk else {}
    plan_config_display = []
    for plan_code, plan_label in PLAN_TIERS:
        plan_models = plan_model_overrides.get(plan_code, {})
        limits = PLAN_LIMITS.get(plan_code, {})
        plan_config_display.append({
            "code": plan_code,
            "label": limits.get("label", plan_label),
            "price_usd": limits.get("price_usd", 0),
            "premium": plan_models.get("premium", ""),
            "workhorse": plan_models.get("workhorse", ""),
            "fast": plan_models.get("fast", ""),
            "has_overrides": bool(plan_models),
        })

    # Rate limits
    plan_rate_limits = config.plan_rate_limits if config.pk else {}
    rate_limits_display = []
    for plan_code, plan_label in PLAN_TIERS:
        current = plan_rate_limits.get(plan_code, {})
        defaults = DEFAULT_RATE_LIMITS.get(plan_code, {})
        rate_limits_display.append({
            "code": plan_code,
            "label": PLAN_LIMITS.get(plan_code, {}).get("label", plan_label),
            "max_calls_per_hour": current.get("max_calls_per_hour", defaults.get("max_calls_per_hour", 100)),
            "max_tokens_per_day": current.get("max_tokens_per_day", defaults.get("max_tokens_per_day", 1_000_000)),
            "enforced_daily_tokens": PLAN_LIMITS.get(plan_code, {}).get("daily_llm_tokens", 0),
            "is_custom": bool(current),
        })

    # Build per-plan image model config display
    image_plan_models = config.image_plan_models if config.pk else {}
    image_plan_display = []
    for plan_code, plan_label in PLAN_TIERS:
        plan_img = image_plan_models.get(plan_code, {})
        defaults = DEFAULT_IMAGE_PLAN_MODELS.get(plan_code, {})
        image_plan_display.append({
            "code": plan_code,
            "label": PLAN_LIMITS.get(plan_code, {}).get("label", plan_label),
            "model": plan_img.get("model", ""),
            "provider": plan_img.get("provider", ""),
            "default_model": defaults.get("model", ""),
            "default_price": defaults.get("price", ""),
            "has_override": bool(plan_img.get("model")),
        })

    return render(request, "admin_dashboard/agents/llm_overview.html", {
        "page_title": "LLM Configuration",
        "config": config,
        "stats_24h": stats_24h,
        "stats_7d": stats_7d,
        "cost_7d": round(cost_7d, 4),
        "cost_30d": round(cost_30d, 4),
        "model_usage": model_usage_rows,
        "unknown_models": sorted(unknown_models_7d | unknown_models_30d),
        "model_health": model_health,
        "paid_fallback_count_7d": paid_fallback_count_7d,
        "daily_tokens": json.dumps([
            {"date": row["date"].isoformat(), "tokens": row["tokens"] or 0, "calls": row["calls"]}
            for row in daily_tokens
        ]),
        "task_config": task_config_display,
        "plan_config": plan_config_display,
        "rate_limits": rate_limits_display,
        "popular_models": POPULAR_MODELS,
        "model_presets": MODEL_PRESETS,
        "task_keys": TASK_KEYS,
        "plan_tiers": PLAN_TIERS,
        # Image config
        "popular_image_models": POPULAR_IMAGE_MODELS,
        "image_plan_config": image_plan_display,
        "default_image_plan_models": DEFAULT_IMAGE_PLAN_MODELS,
        # Strategy roadmap data
        "strategy_phases": _get_strategy_phases(),
        "model_benchmark": _get_model_benchmark(),
    })


@superuser_required
@require_POST
def llm_update_config(request):
    """Save global LLM configuration changes."""
    config = LLMConfig.load()
    if not config.pk:
        config.pk = 1

    config.default_provider = request.POST.get("default_provider", config.default_provider)
    config.default_model = request.POST.get("default_model", "").strip() or config.default_model
    config.paid_fallback_model = request.POST.get("paid_fallback_model", "").strip()
    config.paid_fallback_provider = request.POST.get("paid_fallback_provider", config.paid_fallback_provider)
    config.paid_fallback_enabled = request.POST.get("paid_fallback_enabled") == "on"
    config.max_retries = int(request.POST.get("max_retries", 3))

    # Tier models
    config.model_premium = request.POST.get("model_premium", "").strip() or config.model_premium
    config.model_workhorse = request.POST.get("model_workhorse", "").strip() or config.model_workhorse
    config.model_fast = request.POST.get("model_fast", "").strip() or config.model_fast

    # Free fallback chain
    fallbacks_raw = request.POST.get("free_fallback_models", "").strip()
    if fallbacks_raw:
        config.free_fallback_models = [m.strip() for m in fallbacks_raw.split("\n") if m.strip()]
    else:
        config.free_fallback_models = []

    config.updated_by = request.user
    config.save()

    messages.success(request, "LLM configuration updated. Changes take effect immediately.")
    return redirect("admin_dashboard:llm_overview")


@superuser_required
@require_POST
def llm_update_plan_models(request):
    """Save per-plan model tier configuration."""
    config = LLMConfig.load()
    if not config.pk:
        config.pk = 1

    plan_overrides = config.plan_model_overrides or {}

    for plan_code, _ in PLAN_TIERS:
        premium = request.POST.get(f"{plan_code}_premium", "").strip()
        workhorse = request.POST.get(f"{plan_code}_workhorse", "").strip()
        fast = request.POST.get(f"{plan_code}_fast", "").strip()

        # Only store if at least one value is set
        if premium or workhorse or fast:
            plan_overrides[plan_code] = {}
            if premium:
                plan_overrides[plan_code]["premium"] = premium
            if workhorse:
                plan_overrides[plan_code]["workhorse"] = workhorse
            if fast:
                plan_overrides[plan_code]["fast"] = fast
        elif plan_code in plan_overrides:
            del plan_overrides[plan_code]

    config.plan_model_overrides = plan_overrides
    config.updated_by = request.user
    config.save()

    messages.success(request, "Per-plan model routing updated. Changes take effect immediately.")
    return redirect("admin_dashboard:llm_overview")


# ── Image Generation Configuration ───────────────────────────────────────

@superuser_required
@require_POST
def llm_update_image_config(request):
    """Save global image generation configuration."""
    config = LLMConfig.load()
    if not config.pk:
        config.pk = 1

    config.image_default_provider = request.POST.get("image_default_provider", "").strip() or "together"
    config.image_default_model = request.POST.get("image_default_model", "").strip() or config.image_default_model
    config.image_enabled = request.POST.get("image_enabled") == "on"

    # Fallback chain
    chain_raw = request.POST.get("image_fallback_chain", "").strip()
    if chain_raw:
        config.image_fallback_chain = [p.strip() for p in chain_raw.split(",") if p.strip()]
    else:
        config.image_fallback_chain = ["together", "huggingface", "pollinations"]

    config.updated_by = request.user
    config.save()

    messages.success(request, "Image generation config updated. Changes take effect immediately.")
    return redirect("admin_dashboard:llm_overview")


@superuser_required
@require_POST
def llm_update_image_plan_models(request):
    """Save per-plan image model routing."""
    config = LLMConfig.load()
    if not config.pk:
        config.pk = 1

    plan_models = config.image_plan_models or {}

    for plan_code, _ in PLAN_TIERS:
        model = request.POST.get(f"img_{plan_code}_model", "").strip()
        provider = request.POST.get(f"img_{plan_code}_provider", "").strip()

        if model:
            plan_models[plan_code] = {"model": model, "provider": provider or "together"}
        elif plan_code in plan_models:
            del plan_models[plan_code]

    config.image_plan_models = plan_models
    config.updated_by = request.user
    config.save()

    messages.success(request, "Per-plan image model routing updated. Changes take effect immediately.")
    return redirect("admin_dashboard:llm_overview")


@superuser_required
@require_POST
def llm_update_rate_limits(request):
    """Save per-plan rate limits."""
    config = LLMConfig.load()
    if not config.pk:
        config.pk = 1

    rate_limits = {}
    for plan_code, _ in PLAN_TIERS:
        calls = request.POST.get(f"{plan_code}_max_calls", "").strip()
        tokens = request.POST.get(f"{plan_code}_max_tokens", "").strip()
        defaults = DEFAULT_RATE_LIMITS.get(plan_code, {})

        try:
            calls_int = int(calls) if calls else defaults.get("max_calls_per_hour", 100)
        except (TypeError, ValueError):
            calls_int = defaults.get("max_calls_per_hour", 100)

        try:
            tokens_int = int(tokens) if tokens else defaults.get("max_tokens_per_day", 1_000_000)
        except (TypeError, ValueError):
            tokens_int = defaults.get("max_tokens_per_day", 1_000_000)

        rate_limits[plan_code] = {
            "max_calls_per_hour": max(1, calls_int),
            "max_tokens_per_day": max(1000, tokens_int),
        }

    config.plan_rate_limits = rate_limits
    config.updated_by = request.user
    config.save()

    messages.success(request, "Rate limits updated.")
    return redirect("admin_dashboard:llm_overview")


@superuser_required
@require_POST
def llm_apply_preset(request):
    """Apply a model preset to global or plan-specific config."""
    config = LLMConfig.load()
    if not config.pk:
        config.pk = 1

    preset_key = request.POST.get("preset", "").strip()
    target = request.POST.get("target", "global")  # "global" or plan code

    preset = MODEL_PRESETS.get(preset_key)
    if not preset:
        messages.error(request, f"Unknown preset: {preset_key}")
        return redirect("admin_dashboard:llm_overview")

    if target == "global":
        config.model_premium = preset["premium"]
        config.model_workhorse = preset["workhorse"]
        config.model_fast = preset["fast"]
        messages.success(request, f"Applied '{preset['label']}' preset to global tiers.")
    else:
        plan_overrides = config.plan_model_overrides or {}
        plan_overrides[target] = {
            "premium": preset["premium"],
            "workhorse": preset["workhorse"],
            "fast": preset["fast"],
        }
        config.plan_model_overrides = plan_overrides
        label = PLAN_LIMITS.get(target, {}).get("label", target)
        messages.success(request, f"Applied '{preset['label']}' preset to {label} plan.")

    config.updated_by = request.user
    config.save()

    return redirect("admin_dashboard:llm_overview")


@superuser_required
@require_POST
def llm_update_task_model(request):
    """Update or clear a per-task model override."""
    config = LLMConfig.load()
    if not config.pk:
        config.pk = 1

    task_key = request.POST.get("task_key", "").strip()
    model_value = request.POST.get("model_value", "").strip()
    action = request.POST.get("action", "set")

    valid_keys = {k for k, _ in TASK_KEYS}
    if task_key not in valid_keys:
        messages.error(request, f"Unknown task key: {task_key}")
        return redirect("admin_dashboard:llm_overview")

    overrides = config.task_model_overrides or {}

    if action == "clear" and task_key in overrides:
        del overrides[task_key]
        messages.success(request, f"Cleared override for {task_key} — will use tier default.")
    elif model_value:
        overrides[task_key] = model_value
        messages.success(request, f"Set {task_key} → {model_value}")

    config.task_model_overrides = overrides
    config.updated_by = request.user
    config.save()

    return redirect("admin_dashboard:llm_overview")


def _get_tier_for_task(task_key):
    """Map task key to its tier name."""
    premium = {
        "create.generate", "create.regenerate", "create.repurpose", "engage.reply",
        "commerce.quick_post", "commerce.photo_variations", "commerce.fix_and_promote",
        "educator.draft_article", "educator.compile_digest", "educator.suggest_topics",
    }
    workhorse = {
        "research.trends", "research.angles", "strategist.brief", "strategist.decide",
        "snap.vision", "snap.vision_batch", "snap.carousel", "snap.reel",
    }
    if task_key in premium:
        return "premium"
    elif task_key in workhorse:
        return "workhorse"
    return "fast"


def _plan_revenue_usd(plan_code: str) -> float:
    return float(get_all_plan_limits().get(plan_code, {}).get("price_usd", 0))


def _get_strategy_phases():
    """Return the model strategy phases with live plan pricing."""
    return [
        {
            "phase": 2,
            "name": "Free Primary (Now)",
            "when": "Now — Month 3",
            "status": "active",
            "description": "Free models + DeepSeek V3.2 paid fallback. Validate PMF first.",
            "premium": "qwen/qwen3.6-plus:free",
            "workhorse": "qwen/qwen3.6-plus:free",
            "fast": "stepfun/step-3.5-flash:free",
            "fallback": "deepseek/deepseek-v3.2",
            "costs": {
                "starter": {"ai": 0.05, "revenue": _plan_revenue_usd("starter"), "margin": 97.6},
                "growth": {"ai": 0.23, "revenue": _plan_revenue_usd("growth"), "margin": 96.7},
                "pro": {"ai": 0.90, "revenue": _plan_revenue_usd("pro"), "margin": 93.6},
                "agency": {"ai": 2.25, "revenue": _plan_revenue_usd("agency"), "margin": 89.3},
            },
        },
        {
            "phase": 3,
            "name": "Paid Quality (Month 3-6)",
            "when": "After 50 paying users",
            "status": "planned",
            "description": "DeepSeek V3.2 as primary. Gemini 3 Flash for Pro/Agency creative content.",
            "premium_low": "deepseek/deepseek-v3.2",
            "premium_high": "google/gemini-3-flash-preview",
            "workhorse": "deepseek/deepseek-v3.2",
            "fast": "deepseek/deepseek-v3.2",
            "costs": {
                "starter": {"ai": 0.05, "revenue": _plan_revenue_usd("starter"), "margin": 97.6},
                "growth": {"ai": 0.24, "revenue": _plan_revenue_usd("growth"), "margin": 96.6},
                "pro": {"ai": 2.66, "revenue": _plan_revenue_usd("pro"), "margin": 81.1},
                "agency": {"ai": 6.66, "revenue": _plan_revenue_usd("agency"), "margin": 68.5},
            },
        },
        {
            "phase": 4,
            "name": "Optimized Routing (Month 6+)",
            "when": "100+ users, per-task tuning",
            "status": "planned",
            "description": "Gemini creative, DeepSeek reasoning, Step Flash bulk analysis.",
            "premium_low": "deepseek/deepseek-v3.2",
            "premium_high": "google/gemini-3-flash-preview",
            "workhorse": "deepseek/deepseek-v3.2",
            "fast": "stepfun/step-3.5-flash",
            "costs": {
                "starter": {"ai": 0.03, "revenue": _plan_revenue_usd("starter"), "margin": 98.6},
                "growth": {"ai": 0.15, "revenue": _plan_revenue_usd("growth"), "margin": 97.9},
                "pro": {"ai": 1.80, "revenue": _plan_revenue_usd("pro"), "margin": 87.2},
                "agency": {"ai": 4.50, "revenue": _plan_revenue_usd("agency"), "margin": 78.7},
            },
        },
    ]


def _get_model_benchmark():
    """Return model comparison data from strategy research."""
    return [
        {
            "model": "Qwen 3.6 Plus (free)",
            "input": 0, "output": 0,
            "context": "1M", "speed": "45 tok/s",
            "uptime": "99.9%", "struct_err": "0.95%",
            "intelligence": "#1 ranked", "hallucination": "N/A",
            "verdict": "current-primary", "note": "Collects prompt data",
        },
        {
            "model": "DeepSeek V3.2",
            "input": 0.26, "output": 0.38,
            "context": "164K", "speed": "76 tok/s",
            "uptime": "Multi", "struct_err": "0.78%",
            "intelligence": "89th %ile", "hallucination": "18.3%",
            "verdict": "recommended", "note": "Best value — primary fallback",
        },
        {
            "model": "Gemini 3 Flash",
            "input": 0.50, "output": 3.00,
            "context": "1M", "speed": "76 tok/s",
            "uptime": "99.4%", "struct_err": "1.22%",
            "intelligence": "94th %ile", "hallucination": "7.8%",
            "verdict": "recommended", "note": "Pro/Agency creative tier",
        },
        {
            "model": "Step 3.5 Flash",
            "input": 0.10, "output": 0.30,
            "context": "262K", "speed": "117 tok/s",
            "uptime": "99.9%", "struct_err": "2.78%",
            "intelligence": "82nd %ile", "hallucination": "14.8%",
            "verdict": "recommended", "note": "Bulk classification tasks",
        },
        {
            "model": "MiniMax M2.7",
            "input": 0.30, "output": 1.20,
            "context": "205K", "speed": "46 tok/s",
            "uptime": "89.3%", "struct_err": "N/A",
            "intelligence": "97th %ile", "hallucination": "65.6%",
            "verdict": "rejected", "note": "65.6% hallucination — DISQUALIFIED",
        },
        {
            "model": "gpt-4o-mini",
            "input": 0.15, "output": 0.60,
            "context": "128K", "speed": "varies",
            "uptime": "99.9%", "struct_err": "low",
            "intelligence": "Good", "hallucination": "Low",
            "verdict": "replaced", "note": "Replaced by DeepSeek as fallback",
        },
    ]
