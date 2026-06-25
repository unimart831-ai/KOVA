"""
Kova platform cost registry — single source for unit economics math and admin dashboards.

Every paid API, token, image credit, conversation, and infra line item lives here.
Actual usage is aggregated in ``aggregate_platform_spend()``; estimates use ``COST_CATALOG``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.agents.pricing import calculate_token_cost
from apps.billing.visual_credits import get_platform_photoroom_usage


# ── Per-plan image cost (USD) — tier-routed FLUX models ─────────────────────
PLAN_IMAGE_COST = {
    "kova": 0.025,
    "starter": 0.00,
    "growth": 0.025,
    "pro": 0.04,
    "agency": 0.04,
}

# Plan token/image/voice estimates for scenario calculator (medium utilization)
PLAN_TOKEN_ESTIMATES = {
    "kova": {"input": 1_600_000, "output": 1_400_000, "images": 50, "voice_memos": 20},
    "starter": {"input": 400_000, "output": 350_000, "images": 0, "voice_memos": 5},
    "growth": {"input": 1_600_000, "output": 1_400_000, "images": 50, "voice_memos": 20},
    "pro": {"input": 4_000_000, "output": 3_500_000, "images": 100, "voice_memos": 50},
    "agency": {"input": 16_000_000, "output": 14_000_000, "images": 200, "voice_memos": 100},
}

INFRA_COSTS = {
    "railway_base": 20.00,
    "email_free_limit": 100,
    "r2_storage_free_gb": 10,
}


@dataclass(frozen=True)
class CostLineItem:
    """One billable unit in the Kova stack."""

    id: str
    category: str
    label: str
    provider: str
    feature: str
    unit: str
    unit_cost_usd: float
    formula: str
    tracking: str
    notes: str = ""
    is_variable: bool = True
    plan_gated: str = ""


def _photoroom_plus_unit_cost() -> float:
    pool = int(getattr(settings, "PHOTOROOM_MONTHLY_POOL", 5000))
    monthly = float(getattr(settings, "PHOTOROOM_MONTHLY_COST_USD", 500))
    return round(monthly / max(pool, 1), 4)


def _photoroom_basic_unit_cost() -> float:
    ratio = float(getattr(settings, "PHOTOROOM_BASIC_COST_RATIO", 0.2))
    return round(_photoroom_plus_unit_cost() * ratio, 4)


def get_non_llm_pricing() -> dict[str, dict]:
    """Legacy dict shape used by cost calculator — derived from catalog."""
    plus = _photoroom_plus_unit_cost()
    return {
        "whisper-1": {
            "label": "OpenAI Whisper (Voice Memo)",
            "cost_per_minute": float(getattr(settings, "WHISPER_COST_PER_MINUTE", 0.006)),
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
        },
        "image_together_pro": {
            "label": "Together.ai FLUX.1.1-pro",
            "cost_per_image": 0.04,
            "provider": "Together.ai",
            "plan": "pro / agency",
        },
        "image_huggingface": {
            "label": "HuggingFace FLUX.1-schnell",
            "cost_per_image": 0.00,
            "provider": "HuggingFace",
            "note": "Fallback (free tier)",
        },
        "image_pollinations": {
            "label": "Pollinations.ai Flux",
            "cost_per_image": 0.00,
            "provider": "Pollinations.ai",
            "note": "Last-resort fallback",
        },
        "graphics_pillow": {
            "label": "Branded Graphics (Pillow)",
            "cost_per_image": 0.00,
            "provider": "On-device (Pillow)",
        },
        "visual_photoroom_plus": {
            "label": "Photoroom Plus (Studio polish)",
            "cost_per_image": plus,
            "provider": "Photoroom",
            "note": "1 credit per v2/edit API call",
        },
        "visual_photoroom_basic": {
            "label": "Photoroom Basic (segment API)",
            "cost_per_image": _photoroom_basic_unit_cost(),
            "provider": "Photoroom",
            "note": "~5 Basic calls ≈ 1 Plus credit",
        },
        "vision_gpt4o_mini": {
            "label": "GPT-4o Mini Vision (Snap to Sell)",
            "cost_per_call": 0.0003,
            "avg_input_tokens": 1500,
            "avg_output_tokens": 400,
            "provider": "OpenAI",
        },
    }


def get_cost_catalog() -> list[CostLineItem]:
    """Full inventory of every cost line — math at your fingertips."""
    plus = _photoroom_plus_unit_cost()
    basic = _photoroom_basic_unit_cost()
    whisper_min = float(getattr(settings, "WHISPER_COST_PER_MINUTE", 0.006))
    wa_marketing = float(getattr(settings, "WHATSAPP_MARKETING_COST_USD", 0.049))
    wa_utility = float(getattr(settings, "WHATSAPP_UTILITY_COST_USD", 0.020))
    resend_per = float(getattr(settings, "RESEND_COST_PER_EMAIL_USD", 0.0004))
    tavily_per = float(getattr(settings, "TAVILY_COST_PER_SEARCH_USD", 0.008))
    stripe_pct = float(getattr(settings, "STRIPE_FEE_PERCENT", 2.9)) / 100
    stripe_fixed = float(getattr(settings, "STRIPE_FEE_FIXED_USD", 0.30))

    return [
        # ── LLM tokens ──
        CostLineItem(
            id="llm_agents",
            category="llm",
            label="Agent LLM tokens (Create, Analyst, Engage, …)",
            provider="OpenRouter / OpenAI / Anthropic",
            feature="Social agents, briefs, engage replies",
            unit="token",
            unit_cost_usd=0.0,
            formula="Σ (input/1M × $in + output/1M × $out) per model",
            tracking="agent_action",
            notes="Free-tier models = $0; paid fallback DeepSeek ~$0.26/$0.38 per 1M",
        ),
        CostLineItem(
            id="llm_snap_vision",
            category="llm",
            label="Snap to Sell vision (GPT-4o mini)",
            provider="OpenAI",
            feature="Snap pipeline — product photo analysis",
            unit="call",
            unit_cost_usd=0.0003,
            formula="~1,500 in + 400 out tokens × gpt-4o-mini rates",
            tracking="agent_action_snap",
            notes="Not gated by daily token budget when user=None",
        ),
        CostLineItem(
            id="llm_voice_intent",
            category="llm",
            label="Voice brief intent + campaign generation",
            provider="OpenRouter",
            feature="Voice Campaign — post-Whisper LLM steps",
            unit="call",
            unit_cost_usd=0.002,
            formula="Included in agent_action totals (voice brief tasks)",
            tracking="agent_action",
            notes="Whisper STT is separate line item",
        ),
        CostLineItem(
            id="llm_whatsapp_ai",
            category="llm",
            label="WhatsApp inbox AI replies",
            provider="OpenRouter",
            feature="WhatsApp — AI-assisted replies",
            unit="call",
            unit_cost_usd=0.001,
            formula="Included in agent_action / engage.*",
            tracking="agent_action",
            plan_gated="pro+",
        ),
        CostLineItem(
            id="llm_commerce",
            category="llm",
            label="Commerce copy & product descriptions",
            provider="OpenRouter",
            feature="Snap to Sell, shop SEO, product cards",
            unit="call",
            unit_cost_usd=0.001,
            formula="action_type commerce.* token sum",
            tracking="agent_action_commerce",
        ),
        # ── Speech ──
        CostLineItem(
            id="voice_whisper",
            category="voice",
            label="Whisper transcription",
            provider="OpenAI",
            feature="Voice Campaign — audio → text",
            unit="minute",
            unit_cost_usd=whisper_min,
            formula="duration_seconds / 60 × $0.006",
            tracking="voice_brief",
        ),
        # ── Images ──
        CostLineItem(
            id="image_flux_growth",
            category="image",
            label="FLUX.1-krea-dev (Growth)",
            provider="Together.ai",
            feature="Post AI image generation",
            unit="image",
            unit_cost_usd=0.025,
            formula="generated posts × $0.025",
            tracking="post_media",
            plan_gated="growth",
        ),
        CostLineItem(
            id="image_flux_pro",
            category="image",
            label="FLUX.1.1-pro (Pro / Agency)",
            provider="Together.ai",
            feature="Post AI image generation",
            unit="image",
            unit_cost_usd=0.04,
            formula="generated posts × $0.04",
            tracking="post_media",
            plan_gated="pro, agency",
        ),
        CostLineItem(
            id="image_fallback",
            category="image",
            label="HF / Pollinations fallback",
            provider="HuggingFace / Pollinations",
            feature="Image gen fallback chain",
            unit="image",
            unit_cost_usd=0.0,
            formula="$0",
            tracking="post_media",
            is_variable=False,
        ),
        CostLineItem(
            id="graphics_pillow",
            category="image",
            label="Branded quote / tip / stat graphics",
            provider="Pillow (on-worker)",
            feature="Create agent — template graphics",
            unit="image",
            unit_cost_usd=0.0,
            formula="$0 compute",
            tracking="estimated",
            is_variable=False,
        ),
        # ── Studio / Photoroom ──
        CostLineItem(
            id="photoroom_plus",
            category="studio",
            label="Photoroom Plus v2/edit",
            provider="Photoroom",
            feature="Snap studio polish — variants, AI scenes, channel exports",
            unit="credit",
            unit_cost_usd=plus,
            formula=f"pool ${getattr(settings, 'PHOTOROOM_MONTHLY_COST_USD', 500)}/"
            f"{getattr(settings, 'PHOTOROOM_MONTHLY_POOL', 5000)} ≈ ${plus}/call",
            tracking="studio_polish",
            notes="1 API call = 1 credit; preflight repairs add extra calls",
        ),
        CostLineItem(
            id="photoroom_basic",
            category="studio",
            label="Photoroom Basic segment",
            provider="Photoroom",
            feature="White-bg cutout routing before Plus",
            unit="call",
            unit_cost_usd=basic,
            formula=f"basic_calls × ${basic} (~20% of Plus)",
            tracking="studio_polish_basic",
        ),
        # ── Video ──
        CostLineItem(
            id="reel_ffmpeg",
            category="video",
            label="Motion reel composition",
            provider="FFmpeg (Railway worker)",
            feature="Snap reels — Ken Burns slideshow",
            unit="reel",
            unit_cost_usd=0.0,
            formula="$0 API — CPU on worker dyno",
            tracking="estimated",
            is_variable=False,
            notes="Infra cost only",
        ),
        # ── Messaging ──
        CostLineItem(
            id="whatsapp_marketing",
            category="messaging",
            label="WhatsApp marketing conversations",
            provider="Meta Cloud API",
            feature="Template broadcasts, marketing category",
            unit="conversation",
            unit_cost_usd=wa_marketing,
            formula=f"distinct convos × ${wa_marketing} (Kenya est.)",
            tracking="whatsapp_message",
            plan_gated="pro+",
        ),
        CostLineItem(
            id="whatsapp_utility",
            category="messaging",
            label="WhatsApp utility templates",
            provider="Meta Cloud API",
            feature="Order updates, booking confirmations",
            unit="conversation",
            unit_cost_usd=wa_utility,
            formula=f"utility convos × ${wa_utility}",
            tracking="whatsapp_message",
            notes="1K service convos/mo free tier on WABA",
        ),
        CostLineItem(
            id="email_resend",
            category="messaging",
            label="Transactional & campaign email",
            provider="Resend",
            feature="Auth, billing, briefs, email campaigns",
            unit="email",
            unit_cost_usd=resend_per,
            formula=f"sent emails × ${resend_per} (after 100/day free)",
            tracking="email_log",
        ),
        # ── Search ──
        CostLineItem(
            id="tavily_search",
            category="search",
            label="Tavily web search",
            provider="Tavily",
            feature="Research agent — trend grounding",
            unit="search",
            unit_cost_usd=tavily_per,
            formula="1000 searches/mo free; then ~$8/1K",
            tracking="not_metered",
            plan_gated="growth+",
            notes="Not logged in DB — monitor Tavily dashboard",
        ),
        # ── Infrastructure ──
        CostLineItem(
            id="infra_railway",
            category="infra",
            label="Railway hosting (web, worker, beat, DB, Redis)",
            provider="Railway",
            feature="Platform runtime",
            unit="month",
            unit_cost_usd=25.0,
            formula="~$20–80/mo by scale (see INFRA_COSTS curve)",
            tracking="fixed_estimate",
            is_variable=False,
        ),
        CostLineItem(
            id="infra_r2",
            category="infra",
            label="Cloudflare R2 media storage",
            provider="Cloudflare",
            feature="Uploads, generated media, shop assets",
            unit="GB-month",
            unit_cost_usd=0.015,
            formula="~$0.015/GB after 10 GB free",
            tracking="fixed_estimate",
            is_variable=False,
        ),
        CostLineItem(
            id="infra_sentry",
            category="infra",
            label="Sentry error monitoring",
            provider="Sentry",
            feature="Ops / Celery beat alerts",
            unit="month",
            unit_cost_usd=0.0,
            formula="Free 5K events; Team ~$26/mo",
            tracking="fixed_estimate",
            is_variable=False,
        ),
        # ── Payments (pass-through / fee) ──
        CostLineItem(
            id="payment_stripe",
            category="payments",
            label="Stripe processing fee",
            provider="Stripe",
            feature="International card subscriptions",
            unit="transaction",
            unit_cost_usd=stripe_fixed,
            formula=f"{stripe_pct*100:.1f}% + ${stripe_fixed} per charge",
            tracking="stripe_payment",
            notes="M-Pesa STK Push: 0% merchant fee",
        ),
        CostLineItem(
            id="payment_mpesa",
            category="payments",
            label="M-Pesa Daraja API",
            provider="Safaricom",
            feature="Kenya subscription STK + commerce checkout",
            unit="transaction",
            unit_cost_usd=0.0,
            formula="$0 % on Paybill STK",
            tracking="estimated",
            is_variable=False,
        ),
    ]


def _aggregate_llm_cost(actions_qs) -> tuple[float, int, int, set[str]]:
    total = 0.0
    unknown: set[str] = set()
    inp = 0
    out = 0
    for row in actions_qs.exclude(model_used="").values("model_used").annotate(
        total_in=Sum("input_tokens"),
        total_out=Sum("output_tokens"),
    ):
        i = row["total_in"] or 0
        o = row["total_out"] or 0
        inp += i
        out += o
        result = calculate_token_cost(row["model_used"], i, o)
        total += result["cost_usd"]
        if result["is_unknown"]:
            unknown.add(row["model_used"])
    return round(total, 6), inp, out, unknown


def _studio_polish_qs(since):
    from apps.agents.models import AgentAction

    return AgentAction.objects.filter(
        Q(action_type="commerce.studio_polish") | Q(action_type="commerce.pro_scene"),
        status=AgentAction.ActionStatus.COMPLETED,
        created_at__gte=since,
    ).exclude(input_data__session=True)


def aggregate_platform_spend(*, days: int = 30) -> dict[str, Any]:
    """
    Actual platform COGS for the last ``days`` days, keyed to ``CostLineItem.id``.
    """
    from apps.agents.models import AgentAction, UserTokenBucket
    from apps.content.models import Post, VoiceBrief
    from apps.emails.models import EmailLog

    now = timezone.now()
    since = now - timedelta(days=days)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    actions = AgentAction.objects.filter(created_at__gte=since)
    llm_total, llm_in, llm_out, unknown_models = _aggregate_llm_cost(actions)

    snap_actions = actions.filter(action_type__startswith="snap.")
    snap_cost = 0.0
    for row in snap_actions.exclude(model_used="").values("model_used").annotate(
        inp=Sum("input_tokens"), out=Sum("output_tokens"),
    ):
        r = calculate_token_cost(row["model_used"], row["inp"] or 0, row["out"] or 0)
        snap_cost += r["cost_usd"]
        if r["is_unknown"]:
            unknown_models.add(row["model_used"])
    snap_cost = round(snap_cost, 6)

    commerce_actions = actions.filter(action_type__startswith="commerce.").exclude(
        action_type__in=("commerce.studio_polish", "commerce.pro_scene"),
    )
    commerce_cost = 0.0
    for row in commerce_actions.exclude(model_used="").values("model_used").annotate(
        inp=Sum("input_tokens"), out=Sum("output_tokens"),
    ):
        r = calculate_token_cost(row["model_used"], row["inp"] or 0, row["out"] or 0)
        commerce_cost += r["cost_usd"]
        if r["is_unknown"]:
            unknown_models.add(row["model_used"])
    commerce_cost = round(commerce_cost, 6)

    other_llm_cost = round(max(0.0, llm_total - snap_cost - commerce_cost), 6)

    # Images
    image_rows = (
        Post.objects.filter(created_at__gte=since, media_status="generated")
        .values("user__profile__plan")
        .annotate(count=Count("id"))
    )
    images_generated = 0
    image_cost = 0.0
    for row in image_rows:
        plan = row["user__profile__plan"] or "starter"
        c = row["count"]
        images_generated += c
        image_cost += c * PLAN_IMAGE_COST.get(plan, 0)

    # Photoroom
    polish_qs = _studio_polish_qs(since)
    plus_calls = polish_qs.exclude(input_data__provider="photoroom_basic").count()
    basic_calls = polish_qs.filter(input_data__provider="photoroom_basic").count()
    plus_unit = _photoroom_plus_unit_cost()
    basic_unit = _photoroom_basic_unit_cost()
    photoroom_plus_cost = round(plus_calls * plus_unit, 4)
    photoroom_basic_cost = round(basic_calls * basic_unit, 4)

    # Voice Whisper
    whisper_min = float(getattr(settings, "WHISPER_COST_PER_MINUTE", 0.006))
    vb_stats = VoiceBrief.objects.filter(
        status=VoiceBrief.Status.COMPLETED,
        created_at__gte=since,
    ).aggregate(
        count=Count("id"),
        seconds=Sum("duration_seconds"),
    )
    voice_count = vb_stats["count"] or 0
    voice_seconds = vb_stats["seconds"] or 0
    if voice_count and not voice_seconds:
        voice_seconds = voice_count * 20
    voice_minutes = voice_seconds / 60.0
    voice_cost = round(voice_minutes * whisper_min, 4)

    # WhatsApp
    wa_marketing_cost_usd = float(getattr(settings, "WHATSAPP_MARKETING_COST_USD", 0.049))
    wa_utility_cost_usd = float(getattr(settings, "WHATSAPP_UTILITY_COST_USD", 0.020))
    marketing_convos = 0
    utility_convos = 0
    try:
        from apps.billing.whatsapp_marketing import MARKETING_TEMPLATE_CATEGORIES
        from apps.whatsapp.models import WhatsAppMessage

        base_wa = WhatsAppMessage.objects.filter(
            direction=WhatsAppMessage.Direction.OUTBOUND,
            message_type=WhatsAppMessage.MessageType.TEMPLATE,
            created_at__gte=since,
            status__in=[
                WhatsAppMessage.MessageStatus.SENT,
                WhatsAppMessage.MessageStatus.DELIVERED,
                WhatsAppMessage.MessageStatus.READ,
            ],
        )
        marketing_convos = (
            base_wa.filter(template__category__in=MARKETING_TEMPLATE_CATEGORIES)
            .values("conversation_id")
            .distinct()
            .count()
        )
        utility_convos = (
            base_wa.exclude(template__category__in=MARKETING_TEMPLATE_CATEGORIES)
            .values("conversation_id")
            .distinct()
            .count()
        )
    except Exception:
        pass

    whatsapp_marketing_cost = round(marketing_convos * wa_marketing_cost_usd, 4)
    whatsapp_utility_cost = round(utility_convos * wa_utility_cost_usd, 4)

    # Email
    resend_per = float(getattr(settings, "RESEND_COST_PER_EMAIL_USD", 0.0004))
    emails_sent = EmailLog.objects.filter(
        created_at__gte=since,
        status__in=[
            EmailLog.Status.SENT,
            EmailLog.Status.DELIVERED,
            EmailLog.Status.OPENED,
            EmailLog.Status.CLICKED,
        ],
    ).count()
    email_cost = round(emails_sent * resend_per, 4)

    # Bucket reconciliation
    bucket_stats = UserTokenBucket.objects.filter(
        period_date__gte=(now - timedelta(days=days)).date(),
    ).aggregate(cost_micros=Sum("cost_usd_micros"))
    bucket_cost = (bucket_stats["cost_micros"] or 0) / 1_000_000

    photoroom_pool = get_platform_photoroom_usage()
    photoroom_month_calls = _studio_polish_qs(month_start).count()

    variable_cogs = round(
        llm_total
        + image_cost
        + photoroom_plus_cost
        + photoroom_basic_cost
        + voice_cost
        + whatsapp_marketing_cost
        + whatsapp_utility_cost
        + email_cost,
        4,
    )

    spend_lines = [
        {
            "id": "llm_agents",
            "usage": f"{llm_in + llm_out:,} tokens",
            "usage_count": actions.exclude(model_used="").count(),
            "cost_usd": other_llm_cost,
            "actual": True,
        },
        {
            "id": "llm_snap_vision",
            "usage": f"{snap_actions.count()} calls",
            "usage_count": snap_actions.count(),
            "cost_usd": snap_cost,
            "actual": True,
        },
        {
            "id": "llm_commerce",
            "usage": f"{commerce_actions.count()} calls",
            "usage_count": commerce_actions.count(),
            "cost_usd": commerce_cost,
            "actual": True,
        },
        {
            "id": "voice_whisper",
            "usage": f"{voice_count} memos · {voice_minutes:.1f} min",
            "usage_count": voice_count,
            "cost_usd": voice_cost,
            "actual": True,
        },
        {
            "id": "image_flux_growth",
            "usage": f"{images_generated} images (tier-routed)",
            "usage_count": images_generated,
            "cost_usd": round(image_cost, 4),
            "actual": True,
        },
        {
            "id": "image_flux_pro",
            "usage": "included above",
            "usage_count": 0,
            "cost_usd": 0.0,
            "actual": True,
        },
        {
            "id": "photoroom_plus",
            "usage": f"{plus_calls} Plus credits",
            "usage_count": plus_calls,
            "cost_usd": photoroom_plus_cost,
            "actual": True,
        },
        {
            "id": "photoroom_basic",
            "usage": f"{basic_calls} Basic calls",
            "usage_count": basic_calls,
            "cost_usd": photoroom_basic_cost,
            "actual": True,
        },
        {
            "id": "whatsapp_marketing",
            "usage": f"{marketing_convos} convos",
            "usage_count": marketing_convos,
            "cost_usd": whatsapp_marketing_cost,
            "actual": True,
        },
        {
            "id": "whatsapp_utility",
            "usage": f"{utility_convos} convos",
            "usage_count": utility_convos,
            "cost_usd": whatsapp_utility_cost,
            "actual": True,
        },
        {
            "id": "email_resend",
            "usage": f"{emails_sent} sent",
            "usage_count": emails_sent,
            "cost_usd": email_cost,
            "actual": True,
        },
        {
            "id": "tavily_search",
            "usage": "not metered in app",
            "usage_count": 0,
            "cost_usd": 0.0,
            "actual": False,
        },
        {
            "id": "infra_railway",
            "usage": "fixed monthly",
            "usage_count": 0,
            "cost_usd": INFRA_COSTS["railway_base"],
            "actual": False,
        },
    ]

    catalog_by_id = {c.id: c for c in get_cost_catalog()}
    ledger_rows = []
    for line in spend_lines:
        spec = catalog_by_id.get(line["id"])
        if not spec:
            continue
        ledger_rows.append({
            **line,
            "category": spec.category,
            "label": spec.label,
            "provider": spec.provider,
            "feature": spec.feature,
            "unit": spec.unit,
            "unit_cost_usd": spec.unit_cost_usd,
            "formula": spec.formula,
            "notes": spec.notes,
            "plan_gated": spec.plan_gated,
        })

    return {
        "days": days,
        "variable_cogs_usd": variable_cogs,
        "llm_total_usd": round(llm_total, 4),
        "bucket_cost_usd": round(bucket_cost, 4),
        "ledger_rows": ledger_rows,
        "catalog": get_cost_catalog(),
        "unknown_models": sorted(unknown_models),
        "photoroom_pool": photoroom_pool,
        "photoroom_month_calls": photoroom_month_calls,
        "images_generated": images_generated,
        "totals_by_category": _category_totals(ledger_rows),
    }


def _category_totals(ledger_rows: list[dict]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for row in ledger_rows:
        cat = row.get("category", "other")
        totals[cat] = round(totals.get(cat, 0) + float(row.get("cost_usd") or 0), 4)
    return totals


def calculate_infra_cost_per_user(total_users: int) -> float:
    """Estimate Railway infra per active subscriber."""
    if total_users <= 0:
        return INFRA_COSTS["railway_base"]
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
