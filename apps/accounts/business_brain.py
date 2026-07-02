"""Business Brain — the living intelligence model behind every Kova business.

Onboarding no longer *collects fields*, it *builds understanding*. This module
turns the three conversational answers (what you do / why you started / what
success looks like) plus the business model into a structured Brain across six
DNA layers, and exposes a read-only snapshot used by the First Business Report,
the Daily Brief, and the AI Salesperson.

Design rules:
  - Never block onboarding on the LLM. If extraction fails we still persist the
    raw answers into the right DNA fields (deterministic fallback).
  - Never overwrite a field the user already filled — only enrich empties.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# The six DNA layers, mapped to the UserProfile fields that back them.
BRAIN_LAYERS = {
    "business": ("company_name", "industry", "business_model", "key_offerings", "website_url"),
    "brand": ("brand_voice", "tone_attributes", "founder_story", "brand_restrictions"),
    "customer": ("target_audience", "customer_problems", "buy_triggers", "common_questions"),
    "growth": ("goals", "success_vision", "posting_frequency"),
    "market": ("country", "city", "content_language"),
    "learning": ("pillar_weights", "dna_preferences", "optimal_schedule"),
}


def build_brain_snapshot(profile) -> dict:
    """Return the Business Brain as a nested dict, layer → {field: value}.

    Used for display ("here's what Kova understands") and as grounding context
    for the AI Salesperson. Read-only — never mutates the profile.
    """
    snapshot: dict[str, dict] = {}
    for layer, fields in BRAIN_LAYERS.items():
        snapshot[layer] = {f: getattr(profile, f, None) for f in fields}
    snapshot["completeness"] = brain_completeness(profile)
    return snapshot


# Fields that materially signal "Kova understands this business". Weighted so
# the completeness score reflects real understanding, not just filled inputs.
_COMPLETENESS_WEIGHTS = {
    "company_name": 6,
    "industry": 8,
    "business_model": 8,
    "brand_voice": 12,
    "tone_attributes": 6,
    "founder_story": 10,
    "target_audience": 12,
    "customer_problems": 10,
    "buy_triggers": 8,
    "common_questions": 6,
    "key_offerings": 8,
    "success_vision": 6,
}


def brain_completeness(profile) -> int:
    """0-100 measure of how well the Brain understands this business."""
    earned = 0
    for field, weight in _COMPLETENESS_WEIGHTS.items():
        value = getattr(profile, field, None)
        if _has_value(value):
            earned += weight
    total = sum(_COMPLETENESS_WEIGHTS.values())
    return round(earned / total * 100) if total else 0


def _has_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list | dict | tuple | set)):
        return len(value) > 0
    return bool(value)


def extract_and_apply_brain(
    profile,
    *,
    what: str = "",
    why: str = "",
    success: str = "",
    business_model: str = "",
    use_llm: bool = True,
    commit: bool = True,
) -> list[str]:
    """Build the Brain from conversational answers. Returns updated field names.

    - `what`    → what the business does (extracted into industry/audience/offerings)
    - `why`     → founder story (Brand DNA)
    - `success` → one-year vision (Growth DNA)
    """
    updated: list[str] = []

    def _set_if_empty(field, value):
        if not _has_value(value):
            return
        if _has_value(getattr(profile, field, None)):
            return
        setattr(profile, field, value)
        updated.append(field)

    # Direct answers map straight onto DNA fields — no LLM needed for these.
    if business_model:
        _set_if_empty("business_model", business_model)
    _set_if_empty("founder_story", (why or "").strip())
    _set_if_empty("success_vision", (success or "").strip())

    # LLM-extracted structured understanding from the "what" answer.
    extracted = {}
    if use_llm and (what or "").strip():
        extracted = _llm_extract_understanding(what, why, success, business_model)

    if extracted:
        _apply_extracted(profile, extracted, _set_if_empty)
    else:
        _apply_fallback(profile, what, _set_if_empty)

    if commit and updated:
        profile.save()
    return updated


def _apply_extracted(profile, data: dict, _set_if_empty) -> None:
    """Apply LLM-extracted structured understanding, validating industry."""
    industry = (data.get("industry") or "").strip()
    if industry:
        valid = {v for v, _ in profile.Industry.choices}
        if industry in valid:
            _set_if_empty("industry", industry)

    _set_if_empty("target_audience", (data.get("target_audience") or "").strip())
    _set_if_empty("customer_problems", (data.get("customer_problems") or "").strip())
    _set_if_empty("buy_triggers", (data.get("buy_triggers") or "").strip())
    _set_if_empty("brand_voice", (data.get("brand_voice") or "").strip())

    offerings = _clean_list(data.get("key_offerings"))
    if offerings:
        _set_if_empty("key_offerings", offerings)
    pillars = _clean_list(data.get("content_pillars"))
    if pillars:
        _set_if_empty("content_pillars", pillars)
    tones = _clean_list(data.get("tone_attributes"))
    if tones:
        _set_if_empty("tone_attributes", tones)
    questions = _clean_list(data.get("common_questions"))
    if questions:
        _set_if_empty("common_questions", questions)


def _apply_fallback(profile, what: str, _set_if_empty) -> None:
    """Deterministic fallback when the LLM is unavailable — keep the raw
    description so downstream agents still have signal, and seed a couple of
    universally useful customer questions so the AI Salesperson isn't empty."""
    what = (what or "").strip()
    if what:
        # Use the description as an audience hint and a light brand voice seed.
        _set_if_empty("target_audience", what[:500])
    _set_if_empty(
        "common_questions",
        ["What do you offer?", "What are your prices?", "Do you deliver?"],
    )


def _clean_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()][:8]


def _llm_extract_understanding(what: str, why: str, success: str, business_model: str) -> dict:
    """Extract structured business understanding. Returns {} on any failure so
    the caller falls back gracefully — onboarding must never break on the LLM."""
    try:
        from apps.agents.llm import coerce_llm_dict, generate, parse_llm_json
    except Exception:  # pragma: no cover - import guard
        return {}

    system = (
        "You are Kova's onboarding intelligence. Extract a structured "
        "understanding of a small business from the owner's own words. "
        "Return STRICT JSON only, no prose."
    )
    prompt = (
        "Owner said what they do:\n"
        f'"{what.strip()}"\n\n'
        f'Why they started: "{(why or "").strip()}"\n'
        f'One-year success: "{(success or "").strip()}"\n'
        f"Business model: {business_model or 'unknown'}\n\n"
        "Return JSON with these keys (omit a key if unknown):\n"
        "  industry: one short slug (e.g. salon_beauty, food_restaurant, retail)\n"
        "  target_audience: one sentence describing the ideal customer\n"
        "  customer_problems: one sentence on the problems they solve\n"
        "  buy_triggers: one sentence on why customers choose them\n"
        "  brand_voice: one sentence describing the brand tone\n"
        "  tone_attributes: array of 2-4 lowercase tone words\n"
        "  key_offerings: array of up to 5 products/services\n"
        "  content_pillars: array of 3-5 content themes\n"
        "  common_questions: array of up to 5 questions customers ask\n"
    )
    try:
        resp = generate(prompt, system=system, temperature=0.4, max_tokens=700, json_mode=True)
        return coerce_llm_dict(parse_llm_json(resp.content))
    except Exception as exc:
        logger.warning("Business Brain extraction failed, using fallback: %s", exc)
        return {}
