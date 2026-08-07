"""First Business Report — the "Kova already understands my business" moment.

Delivered right after onboarding instead of a bare "account created" screen.
It reads the Business Brain and any early signals and returns an assessment:
a marketing score, strengths, weaknesses, growth opportunities, an estimated
growth potential, and a 90-day plan.

The score here measures *readiness/understanding*, not live performance — a
brand-new account has no metrics yet. Live health is tracked separately by the
Daily Brief's Kova Score (apps/briefs/tasks.calculate_kova_score).

LLM enriches the growth opportunities; a deterministic fallback guarantees a
useful report even with no AI configured.
"""

from __future__ import annotations

import logging

from apps.core.accounts.business_brain import brain_completeness

logger = logging.getLogger(__name__)

FIRST_REPORT_CACHE_TTL = 60 * 60 * 24 * 7  # 7 days


def _cache_key(user) -> str:
    return f"first_business_report:{user.pk}"


def cache_first_business_report(user, *, use_llm: bool = False) -> dict:
    """Generate and cache the report so the completion screen renders instantly."""
    from django.core.cache import cache

    report = build_first_business_report(user, use_llm=use_llm)
    cache.set(_cache_key(user), report, FIRST_REPORT_CACHE_TTL)
    return report


def get_first_business_report(user, *, generate_if_missing: bool = True) -> dict:
    """Return the cached report, regenerating on a miss if asked."""
    from django.core.cache import cache

    cached = cache.get(_cache_key(user))
    if cached is not None:
        return cached
    if generate_if_missing:
        return cache_first_business_report(user)
    return _empty_report()


def build_first_business_report(user, *, use_llm: bool = True) -> dict:
    """Return the First Business Report for a freshly onboarded user."""
    profile = getattr(user, "profile", None)
    if profile is None:
        return _empty_report()

    signals = _gather_signals(user, profile)
    score, breakdown = _readiness_score(profile, signals)
    strengths, weaknesses = _strengths_and_weaknesses(breakdown)
    opportunities = _growth_opportunities(profile, signals, use_llm=use_llm)
    growth_potential = _estimated_growth_potential(score)
    plan = _ninety_day_plan(profile)

    return {
        "marketing_score": score,
        "grade": _grade(score),
        "breakdown": breakdown,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "growth_opportunities": opportunities,
        "estimated_growth_potential": growth_potential,
        "ninety_day_plan": plan,
        "brain_completeness": brain_completeness(profile),
    }


# ── Signals ─────────────────────────────────────────────────────────────────


def _gather_signals(user, profile) -> dict:
    connected = 0
    try:
        connected = user.social_accounts.filter(is_active=True).count()
    except Exception:
        connected = 0

    posts = 0
    try:
        from apps.create.content.models import Post

        posts = Post.objects.filter(user=user).count()
    except Exception:
        posts = 0

    products = 0
    try:
        from apps.commerce.products.models import Product

        products = Product.objects.filter(user=user).count()
    except Exception:
        products = 0

    return {"connected_platforms": connected, "posts": posts, "products": products}


# ── Readiness score ─────────────────────────────────────────────────────────


def _readiness_score(profile, signals) -> tuple[int, dict]:
    """Score onboarding readiness 0-100 across five components."""
    b = {
        "brand_clarity": {"points": 0, "max": 25, "label": "Brand clarity"},
        "customer_understanding": {"points": 0, "max": 25, "label": "Customer understanding"},
        "offerings": {"points": 0, "max": 15, "label": "Offerings & pillars"},
        "channels": {"points": 0, "max": 20, "label": "Connected channels"},
        "direction": {"points": 0, "max": 15, "label": "Goals & direction"},
    }

    # Brand clarity — voice, tone, founder story
    brand = 0
    if _s(profile.brand_voice):
        brand += 12
    if _l(profile.tone_attributes):
        brand += 7
    if _s(getattr(profile, "founder_story", "")):
        brand += 6
    b["brand_clarity"]["points"] = min(25, brand)

    # Customer understanding — audience, problems, buy triggers
    cust = 0
    if _s(profile.target_audience):
        cust += 11
    if _s(getattr(profile, "customer_problems", "")):
        cust += 8
    if _s(getattr(profile, "buy_triggers", "")):
        cust += 6
    b["customer_understanding"]["points"] = min(25, cust)

    # Offerings & pillars
    off = 0
    if _l(profile.key_offerings):
        off += 9
    if _l(profile.content_pillars):
        off += 6
    b["offerings"]["points"] = min(15, off)

    # Connected channels
    connected = signals.get("connected_platforms", 0)
    b["channels"]["points"] = min(20, connected * 7)

    # Goals & direction
    direction = 0
    if _l(profile.goals):
        direction += 8
    if _s(getattr(profile, "success_vision", "")):
        direction += 7
    b["direction"]["points"] = min(15, direction)

    score = sum(c["points"] for c in b.values())
    return max(0, min(100, score)), b


def _strengths_and_weaknesses(breakdown: dict) -> tuple[list[str], list[str]]:
    strengths, weaknesses = [], []
    for comp in breakdown.values():
        ratio = comp["points"] / comp["max"] if comp["max"] else 0
        if ratio >= 0.7:
            strengths.append(f"Strong {comp['label'].lower()}")
        elif ratio < 0.4:
            weaknesses.append(f"{comp['label']} needs work")
    if not strengths:
        strengths.append("You've taken the first step — Kova is learning your business")
    return strengths, weaknesses


# ── Growth opportunities ────────────────────────────────────────────────────


def _growth_opportunities(profile, signals, *, use_llm: bool = True) -> list[str]:
    if use_llm:
        ai = _llm_opportunities(profile)
        if ai:
            return ai
    return _fallback_opportunities(profile, signals)


def _fallback_opportunities(profile, signals) -> list[str]:
    opps: list[str] = []
    bm = (getattr(profile, "business_model", "") or "").strip()

    if signals.get("connected_platforms", 0) == 0:
        opps.append("Connect WhatsApp and Instagram so Kova can start bringing you customers")
    if bm == "service":
        opps.append("Set up a booking page so customers can reserve appointments 24/7")
    elif bm == "product":
        opps.append("Add your best-sellers so Kova can create snap-to-sell campaigns")
    elif bm == "digital":
        opps.append("Enable instant checkout so buyers can purchase without friction")
    elif bm == "professional":
        opps.append("Showcase your best projects as proof to win new clients")

    if not _l(profile.content_pillars):
        opps.append("Let Kova plan a weekly content mix so posting stays consistent")
    opps.append("Turn on a referral offer to grow through word-of-mouth")
    return opps[:4]


def _llm_opportunities(profile) -> list[str]:
    try:
        from apps.create.agents.llm import coerce_llm_dict, generate, parse_llm_json
    except Exception:  # pragma: no cover
        return []

    industry = ""
    try:
        industry = profile.get_industry_display() if profile.industry else ""
    except Exception:
        industry = getattr(profile, "industry", "") or ""

    system = (
        "You are Kova, an AI growth strategist for African SMEs. Suggest "
        "concrete, high-impact growth opportunities. Return STRICT JSON only."
    )
    prompt = (
        f"Business: {profile.company_name or 'a small business'}\n"
        f"Industry: {industry or 'unknown'}\n"
        f"Model: {getattr(profile, 'business_model', '') or 'unknown'}\n"
        f"Audience: {(profile.target_audience or '')[:200]}\n"
        f"Goals: {profile.goals or []}\n\n"
        'Return JSON: {"opportunities": ["...", "...", "..."]} with 3-4 short, '
        "specific, action-oriented opportunities in the owner's context."
    )
    try:
        resp = generate(prompt, system=system, temperature=0.6, max_tokens=500, json_mode=True)
        data = coerce_llm_dict(parse_llm_json(resp.content))
        items = data.get("opportunities") or []
        cleaned = [str(x).strip() for x in items if str(x).strip()]
        return cleaned[:4]
    except Exception as exc:
        logger.warning("First report opportunities LLM failed, using fallback: %s", exc)
        return []


# ── Growth potential + 90-day plan ──────────────────────────────────────────


def _estimated_growth_potential(score: int) -> str:
    """Lower readiness → more headroom. Bounded to a credible range."""
    headroom = 100 - score
    pct = max(15, min(60, round(headroom * 0.6)))
    return f"+{pct}%"


def _ninety_day_plan(profile) -> list[dict]:
    bm = (getattr(profile, "business_model", "") or "").strip()
    month3 = {
        "service": "Fill your calendar — optimise for bookings and reviews",
        "product": "Turn attention into sales — best-seller pushes and offers",
        "digital": "Scale instant sales — bundles and upsells",
        "professional": "Convert proof into projects — case studies and consults",
    }.get(bm, "Revenue optimization — turn audience into paying customers")
    return [
        {"month": 1, "theme": "Consistency", "focus": "Show up daily in your brand voice across your channels"},
        {"month": 2, "theme": "Audience growth", "focus": "Grow reach with content that earns saves and shares"},
        {"month": 3, "theme": "Revenue", "focus": month3},
    ]


# ── Helpers ─────────────────────────────────────────────────────────────────


def _grade(score: int) -> str:
    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Good"
    if score >= 40:
        return "Getting there"
    return "Just starting"


def _s(value) -> bool:
    return bool(value and str(value).strip())


def _l(value) -> bool:
    return bool(value and len(value) > 0)


def _empty_report() -> dict:
    return {
        "marketing_score": 0,
        "grade": "Just starting",
        "breakdown": {},
        "strengths": [],
        "weaknesses": [],
        "growth_opportunities": [],
        "estimated_growth_potential": "+0%",
        "ninety_day_plan": [],
        "brain_completeness": 0,
    }
