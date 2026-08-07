"""AI Quality Review Board — Kova doesn't publish content, it manufactures campaigns.

Every post is reviewed by a board of specialised critics before it reaches the
owner for approval:

  Production critics (reuse campaign_qa):
    visual · brand · platform · cta · compliance
  Business-impact critics (added here, grounded in the Business Brain):
    customer  — does this speak to THIS business's audience + their problems?
    sales     — does it actually drive a purchase/booking (offer + CTA + urgency)?
    strategy  — does it advance the owner's goals + use patterns that have worked?

The board produces a per-dimension scorecard, a combined score vs the publish
threshold, and — crucially — a plain-English "Why this will succeed" with a
confidence number and risk flags, so the owner trusts the AI instead of guessing.

All scoring is deterministic and Brain-grounded — no extra LLM cost.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from apps.create.content.campaign_qa import (
    DIMENSION_LABELS,
    get_publish_min_score,
    score_post_qa,
)

# Business-impact critics are blended with production quality into the overall.
PRODUCTION_WEIGHT = 0.6
IMPACT_WEIGHT = 0.4

# Dimensions that must clear a hard floor regardless of the weighted overall —
# we never ship non-compliant or media-broken content.
CRITICAL_FLOORS = {"compliance": 55, "visual": 45}

_LABELS = {
    **DIMENSION_LABELS,
    "customer": "Customer fit",
    "sales": "Sales",
    "strategy": "Strategy",
}

_OFFER_WORDS = frozenset(
    {
        "offer",
        "discount",
        "sale",
        "free",
        "deal",
        "save",
        "today",
        "now",
        "limited",
        "hurry",
        "last",
        "only",
        "bonus",
        "gift",
        "% off",
        "off",
    }
)
_ACTION_WORDS = frozenset(
    {
        "reply",
        "order",
        "book",
        "buy",
        "shop",
        "dm",
        "call",
        "message",
        "grab",
        "get",
        "claim",
        "visit",
        "tap",
        "click",
        "whatsapp",
    }
)
_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "of",
        "in",
        "on",
        "for",
        "with",
        "your",
        "you",
        "our",
        "we",
        "is",
        "are",
        "this",
        "that",
        "it",
        "at",
    }
)


@dataclass
class QualityReview:
    post_id: str
    dimensions: dict  # name -> {"score": int, "label": str, "note": str}
    production_score: int
    impact_score: int
    overall: int
    min_required: int
    passed: bool
    confidence: int
    why: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def review_post(post, *, user=None, seed=None) -> QualityReview:
    """Run the full Quality Review Board on a single post."""
    user = user or post.user
    seed = seed if seed is not None else getattr(post, "seed", None)
    profile = getattr(user, "profile", None)

    # Production critics (reuse the existing weighted QA scorer).
    qa = score_post_qa(post, seed=seed)
    production = qa.overall

    # Business-impact critics.
    cust_score, cust_note = _review_customer(post, profile)
    sales_score, sales_note = _review_sales(post)
    strat_score, strat_note = _review_strategy(post, profile)
    impact = round(cust_score * 0.34 + sales_score * 0.33 + strat_score * 0.33)

    overall = round(production * PRODUCTION_WEIGHT + impact * IMPACT_WEIGHT)

    dimensions: dict = {}
    for key, score in qa.dimensions.items():
        dimensions[key] = {"score": score, "label": _LABELS.get(key, key.title()), "note": ""}
    dimensions["customer"] = {"score": cust_score, "label": _LABELS["customer"], "note": cust_note}
    dimensions["sales"] = {"score": sales_score, "label": _LABELS["sales"], "note": sales_note}
    dimensions["strategy"] = {"score": strat_score, "label": _LABELS["strategy"], "note": strat_note}

    min_required = get_publish_min_score(user)
    floors_ok = all(dimensions.get(dim, {}).get("score", 100) >= floor for dim, floor in CRITICAL_FLOORS.items())
    passed = overall >= min_required and floors_ok

    confidence, why, risks = _why_will_succeed(post, dimensions, overall, profile, qa)
    if not floors_ok:
        for dim, floor in CRITICAL_FLOORS.items():
            if dimensions.get(dim, {}).get("score", 100) < floor:
                risks.insert(0, f"Blocked: {_LABELS.get(dim, dim)} below the safety floor")

    return QualityReview(
        post_id=str(post.pk),
        dimensions=dimensions,
        production_score=production,
        impact_score=impact,
        overall=overall,
        min_required=min_required,
        passed=passed,
        confidence=confidence,
        why=why[:5],
        risks=risks[:4],
    )


def build_scorecard(post, *, user=None, seed=None) -> dict:
    """Template-friendly scorecard dict for the approval UI."""
    return review_post(post, user=user, seed=seed).to_dict()


# ── Business-impact critics ─────────────────────────────────────────────────


def _review_customer(post, profile) -> tuple[int, str]:
    """Does the copy speak to THIS business's audience and their problems?"""
    if profile is None:
        return 60, "No customer profile yet — add your audience for a sharper review."
    audience_text = " ".join(
        str(x)
        for x in (
            getattr(profile, "target_audience", "") or "",
            getattr(profile, "customer_problems", "") or "",
            getattr(profile, "buy_triggers", "") or "",
        )
    )
    audience_tokens = _tokens(audience_text)
    if not audience_tokens:
        return 62, "Add your audience + their problems so Kova can tune content to them."
    post_tokens = _tokens(post.content_text or "")
    overlap = post_tokens & audience_tokens
    score = min(100, 60 + len(overlap) * 8)
    if overlap:
        note = "Speaks to your audience: " + ", ".join(list(overlap)[:3])
    else:
        note = "Doesn't yet reference your audience's needs."
        score = 55
    return score, note


def _review_sales(post) -> tuple[int, str]:
    """Will this actually drive a purchase or booking?"""
    text = (post.content_text or "").lower()
    score = 45
    reasons = []
    if (post.cta_url or "").strip() or (post.cta_type or "none") != "none":
        score += 25
        reasons.append("clear CTA")
    else:
        reasons.append("no CTA")
    if any(w in text for w in _OFFER_WORDS):
        score += 15
        reasons.append("offer/urgency")
    if any(re.search(rf"\b{re.escape(w)}\b", text) for w in _ACTION_WORDS):
        score += 12
        reasons.append("action verb")
    score = min(100, score)
    if score >= 75:
        note = "Strong on conversion (" + ", ".join(reasons) + ")."
    else:
        note = "Weak on conversion — add an offer + a single clear action."
    return score, note


def _review_strategy(post, profile) -> tuple[int, str]:
    """Does this advance the owner's goals and use patterns that have worked?"""
    score = 60
    notes = []
    dna = post.content_dna or {}
    prefs = getattr(profile, "dna_preferences", None) or {} if profile else {}
    promoted = prefs.get("promoted") or []
    promoted_pillars = {(p.get("combo") or {}).get("pillar") for p in promoted if isinstance(p, dict)}
    pillar = dna.get("pillar")
    if pillar and pillar in promoted_pillars:
        score += 18
        notes.append(f"uses your winning pillar ({pillar})")

    goals = getattr(profile, "goals", None) or [] if profile else []
    has_cta = bool((post.cta_url or "").strip()) or (post.cta_type or "none") != "none"
    if has_cta and any(g in ("drive_sales", "generate_leads", "book_appointments") for g in goals):
        score += 15
        notes.append("advances your sales/leads goal")

    score = min(100, score)
    note = (
        ("Aligned: " + ", ".join(notes) + ".")
        if notes
        else "Neutral on strategy — not tied to a goal or proven pattern."
    )
    return score, note


# ── Why this will succeed ───────────────────────────────────────────────────


def _why_will_succeed(post, dimensions, overall, profile, qa) -> tuple[int, list[str], list[str]]:
    predicted = post.predicted_engagement_score
    confidence = int(predicted) if predicted else _confidence_from_overall(overall)

    why: list[str] = []
    if predicted and predicted >= 70:
        why.append(f"Kova predicts strong performance ({int(predicted)}/100).")
    if dimensions["customer"]["score"] >= 75:
        why.append(dimensions["customer"]["note"])
    if dimensions["strategy"]["score"] >= 75 and dimensions["strategy"]["note"].startswith("Aligned"):
        why.append(dimensions["strategy"]["note"])
    if dimensions["sales"]["score"] >= 75:
        why.append(dimensions["sales"]["note"])
    if (post.ai_reasoning or "").strip() and not post.ai_reasoning.startswith(("QA GATE", "Publish error", "SAFETY")):
        why.append(post.ai_reasoning.strip()[:160])
    if not why:
        why.append("Solid, on-brand content — a dependable post for staying consistent.")

    risks: list[str] = []
    for data in dimensions.values():
        if data["score"] < 70:
            risks.append(f"{data['label']} is weak ({data['score']}) — {data['note'] or 'needs work'}".rstrip(" —"))
    for issue in (qa.issues or [])[:2]:
        if issue and issue not in " ".join(risks):
            risks.append(issue)

    return confidence, why, risks


def _confidence_from_overall(overall: int) -> int:
    # Map the quality score to a slightly conservative confidence band.
    return max(35, min(95, overall - 3))


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if len(w) > 3 and w not in _STOPWORDS}
