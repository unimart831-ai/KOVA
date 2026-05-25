"""Admin dashboard — Photoroom Plus configuration and usage."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required
from apps.agents.models import AgentAction
from apps.billing.models import PLAN_LIMITS
from apps.billing.visual_credits import get_platform_photoroom_usage
from apps.products.photoroom import photoroom_enabled
from apps.products.photoroom_plus import (
    AI_BG_MODEL_HEADER,
    AI_BG_SEEDS,
    PHOTOROOM_EDIT_URL,
    PLUS_VARIANT_CATALOG,
    PRODUCT_CATEGORIES,
)

STUDIO_POLISH_ACTIONS = ("commerce.studio_polish", "commerce.pro_scene")

# Photoroom v2/edit parameter groups (Plus plan) — reference for operators
API_PARAM_GROUPS = [
    {
        "group": "Input",
        "params": [
            ("imageUrl", "GET", "Public URL of source image"),
            ("imageFile", "POST", "Multipart upload when URL is not public"),
        ],
    },
    {
        "group": "Background removal",
        "params": [
            ("removeBackground", "bool", "Pro cutout — true/false"),
            ("keepExistingAlphaChannel", "bool", "Preserve alpha from PNG input"),
        ],
    },
    {
        "group": "background.*",
        "params": [
            ("background.color", "hex", "Solid studio color (no # prefix)"),
            ("background.prompt", "text", "AI-generated lifestyle scene"),
            ("background.negativePrompt", "text", "Legacy model v2 only"),
            ("background.seed", "int", "Reproducible AI background"),
            ("background.expandPrompt.mode", "enum", "ai.never to disable prompt expansion"),
            ("background.guidance.imageUrl", "url", "Image prompt for AI bg"),
            ("background.guidance.imageFile", "file", "Image prompt upload"),
            ("background.guidance.scale", "float", "0–1 weight vs text prompt"),
            ("background.blur.mode", "enum", "ai.auto depth blur"),
            ("background.blur.radius", "float", "Blur strength"),
        ],
    },
    {
        "group": "shadow.*",
        "params": [
            ("shadow.mode", "enum", "ai.soft | ai.hard | ai.floating (+ overrides)"),
            ("shadow.directionOverride", "float", "Shadow angle override"),
            ("shadow.intensityOverride", "float", "Shadow strength"),
            ("shadow.softnessOverride", "float", "Shadow softness"),
        ],
    },
    {
        "group": "lighting.*",
        "params": [
            ("lighting.mode", "enum", "ai.auto relight"),
        ],
    },
    {
        "group": "beautify.*",
        "params": [
            ("beautify.mode", "enum", "ai.auto touch-up"),
            ("beautify.seed", "int", "Reproducible beautify"),
        ],
    },
    {
        "group": "flatLay.*",
        "params": [
            ("flatLay.mode", "enum", "ai.auto"),
            ("flatLay.prompt", "text", "Style guidance"),
            ("flatLay.size", "enum", "SQUARE_HD, PORTRAIT_HD_*, LANDSCAPE_HD_*"),
        ],
    },
    {
        "group": "ghostMannequin.*",
        "params": [
            ("ghostMannequin.mode", "enum", "ai.auto"),
            ("ghostMannequin.prompt", "text", "Apparel styling hint"),
            ("ghostMannequin.size", "enum", "Output dimensions preset"),
        ],
    },
    {
        "group": "virtualModel.*",
        "params": [
            ("virtualModel.mode", "enum", "ai.auto"),
            ("virtualModel.prompt", "text", "Model/scene guidance"),
            ("virtualModel.quality", "enum", "high | standard"),
            ("virtualModel.size", "enum", "Output dimensions preset"),
        ],
    },
    {
        "group": "textRemoval.*",
        "params": [
            ("textRemoval.mode", "enum", "ai.auto clean labels/text"),
        ],
    },
    {
        "group": "outline.*",
        "params": [
            ("outline.color", "hex", "Subject outline color"),
            ("outline.width", "int", "Outline stroke width"),
            ("outline.blurRadius", "float", "Outline blur"),
        ],
    },
    {
        "group": "editWithAI.*",
        "params": [
            ("editWithAI.mode", "enum", "ai.auto"),
            ("editWithAI.prompt", "text", "Describe edits (recolor, enhance…)"),
            ("editWithAI.seed", "int", "Reproducible edit"),
        ],
    },
    {
        "group": "upscale / expand / uncrop",
        "params": [
            ("upscale.mode", "enum", "ai.auto"),
            ("upscale.downscaleIfNeeded", "bool", "Fit large inputs"),
            ("expand.mode", "enum", "ai.auto canvas expand"),
            ("expand.seed", "int", "Reproducible expand"),
            ("uncrop.mode", "enum", "ai.auto"),
            ("uncrop.seed", "int", "Reproducible uncrop"),
        ],
    },
    {
        "group": "Layout & export",
        "params": [
            ("referenceBox", "enum", "originalImage"),
            ("outputSize", "string", "e.g. 1080x1080"),
            ("padding", "float", "Product padding ratio"),
            ("paddingTop/Bottom/Left/Right", "float", "Per-side padding"),
            ("margin", "float", "Canvas margin"),
            ("horizontalAlignment", "enum", "left | center | right"),
            ("verticalAlignment", "enum", "top | center | bottom"),
            ("export.format", "enum", "jpeg | png | webp"),
            ("export.dpi", "int", "Print DPI"),
        ],
    },
]

ENV_SETTINGS = [
    {
        "key": "PHOTOROOM_API_KEY",
        "kind": "secret",
        "description": "Plus API key from Photoroom dashboard. Use sandbox_sk_pr_* for dev.",
    },
    {
        "key": "PHOTOROOM_SANDBOX",
        "kind": "bool",
        "description": "Prepends sandbox_ to key when true (watermarked free calls).",
    },
    {
        "key": "VISUAL_ENHANCE_ENABLED",
        "kind": "bool",
        "description": "Master switch for studio polish / Plus pack.",
    },
    {
        "key": "PHOTO_VARIATIONS_ENABLED",
        "kind": "bool",
        "description": "Enables photo expansion pipeline (Plus + promo frame).",
    },
    {
        "key": "PHOTOROOM_MONTHLY_POOL",
        "kind": "int",
        "description": "Platform-wide monthly API call pool.",
    },
    {
        "key": "PHOTOROOM_POOL_RESERVE",
        "kind": "int",
        "description": "Headroom reserved from pool (usable = pool − reserve).",
    },
    {
        "key": "PHOTOROOM_MONTHLY_COST_USD",
        "kind": "float",
        "description": "Assumed monthly Photoroom spend for cost dashboard.",
    },
    {
        "key": "PHOTOROOM_OUTPUT_SIZE",
        "kind": "string",
        "description": "Default v2/edit outputSize (social square).",
    },
    {
        "key": "PHOTOROOM_PADDING",
        "kind": "float",
        "description": "Default padding around product (0–1 ratio).",
    },
    {
        "key": "PHOTOROOM_DEFAULT_SHADOW",
        "kind": "string",
        "description": "Default shadow.mode for studio variants.",
    },
    {
        "key": "SITE_URL",
        "kind": "string",
        "description": "Public site URL — Photoroom fetches images via GET when reachable.",
    },
]


def _mask_api_key(key: str) -> str:
    key = (key or "").strip()
    if not key:
        return "Not set"
    if len(key) <= 8:
        return "••••••••"
    prefix = "sandbox_" if key.startswith("sandbox_") else ""
    tail = key[-4:]
    return f"{prefix}••••{tail}"


def _env_display(key: str, kind: str) -> str:
    val = getattr(settings, key, None)
    if kind == "secret":
        return _mask_api_key(str(val or ""))
    if kind == "bool":
        return "True" if val else "False"
    if val is None or val == "":
        return "—"
    return str(val)


@staff_required
def photoroom_config(request):
    """Photoroom Plus — env settings, variant catalog, plan limits, usage."""
    tab = request.GET.get("tab", "overview")
    if tab not in ("overview", "environment", "variants", "plans", "api", "usage"):
        tab = "overview"

    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days_30 = now - timedelta(days=30)

    pool = get_platform_photoroom_usage()
    api_key = getattr(settings, "PHOTOROOM_API_KEY", "") or ""
    enabled = photoroom_enabled()
    sandbox = getattr(settings, "PHOTOROOM_SANDBOX", False)

    env_rows = [
        {**row, "value": _env_display(row["key"], row["kind"])}
        for row in ENV_SETTINGS
    ]

    plan_rows = []
    for tier, limits in PLAN_LIMITS.items():
        plan_rows.append(
            {
                "tier": tier,
                "label": limits.get("label", tier),
                "credits": limits.get("visual_enhancements_per_month", 0),
                "max_variants": limits.get("plus_max_variants_per_product", 3),
                "premium": limits.get("visual_enhance_premium", False),
            }
        )

    variants = []
    for spec in sorted(PLUS_VARIANT_CATALOG.values(), key=lambda s: (-s.priority, s.id)):
        param_keys = sorted(spec.params.keys())
        variants.append(
            {
                "id": spec.id,
                "label": spec.label,
                "min_plan": spec.min_plan,
                "priority": spec.priority,
                "categories": ", ".join(spec.categories) if spec.categories else "All",
                "offering_types": ", ".join(spec.offering_types),
                "param_count": len(spec.params),
                "param_keys": ", ".join(param_keys),
                "params": spec.params,
                "headers": spec.headers,
                "uses_ai_bg": "background.prompt" in spec.params,
            }
        )

    studio_qs = AgentAction.objects.filter(
        action_type__in=STUDIO_POLISH_ACTIONS,
    )
    usage_month = studio_qs.filter(created_at__gte=month_start).count()
    usage_30d = studio_qs.filter(created_at__gte=days_30).count()

    variant_usage = []
    for row in (
        studio_qs.filter(created_at__gte=days_30)
        .values("output_data__variant")
        .annotate(count=Count("id"))
        .order_by("-count")[:20]
    ):
        vid = row.get("output_data__variant") or "(legacy)"
        variant_usage.append({"variant": vid, "count": row["count"]})

    recent_actions = (
        studio_qs.select_related("user")
        .order_by("-created_at")[:25]
    )

    pool_pct = round(pool["used"] / pool["usable"] * 100, 1) if pool["usable"] else 0

    return render(
        request,
        "admin_dashboard/commerce/photoroom.html",
        {
            "page_title": "Photoroom Plus",
            "commerce_section": "photoroom",
            "tab": tab,
            "tab_items": [
                ("overview", "Overview"),
                ("environment", "Environment"),
                ("variants", "Variant catalog"),
                ("plans", "Plan limits"),
                ("api", "API reference"),
                ("usage", "Usage"),
            ],
            "enabled": enabled,
            "sandbox": sandbox,
            "api_key_display": _mask_api_key(api_key),
            "api_key_set": bool(api_key.strip()),
            "pool": pool,
            "pool_pct": pool_pct,
            "env_rows": env_rows,
            "plan_rows": plan_rows,
            "variants": variants,
            "variant_count": len(variants),
            "api_param_groups": API_PARAM_GROUPS,
            "api_endpoint": PHOTOROOM_EDIT_URL,
            "ai_bg_model": AI_BG_MODEL_HEADER,
            "ai_bg_seeds": AI_BG_SEEDS,
            "product_categories": PRODUCT_CATEGORIES,
            "usage_month": usage_month,
            "usage_30d": usage_30d,
            "variant_usage": variant_usage,
            "recent_actions": recent_actions,
        },
    )
