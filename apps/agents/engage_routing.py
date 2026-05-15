"""Engage Agent v2 — graduated-autonomy routing & safety rails.

The single decision point that turns (autonomy_level, confidence, safety
flags) into one of three actions: auto-send, draft-for-review, escalate.

Spec: docs/specs/ENGAGE_AGENT_V2_SPEC.md.

Used by:
    apps/engage/tasks.py  — for inbound social comment/DM handling
    apps/agents/engage_agent.py — for the auto_respond cycle
    apps/whatsapp/tasks.py  — eventually, to unify with the WhatsApp path

The routing is intentionally pure (no DB writes, no LLM calls) so it's
easy to test, easy to reason about, and reusable across the comment / DM
/ WhatsApp handlers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable


# ── Public action enum ──────────────────────────────────────────────────────


class RoutingAction(str, Enum):
    AUTO_SEND = "auto_send"             # graduated/aggressive + high confidence
    DRAFT_FOR_REVIEW = "draft_for_review"  # AI suggests, user approves
    ESCALATE = "escalate"               # AI confidence too low; needs human
    SKIP = "skip"                       # No reply at all (no_reply intent, spam)


# ── Confidence thresholds (mirror the spec table) ───────────────────────────
#
# Each autonomy level maps to two thresholds: (auto_send_min, draft_min).
# A reply with confidence below the draft_min is escalated.

_THRESHOLDS: dict[str, tuple[float, float]] = {
    "off":        (10.0, 10.0),  # nothing auto-routes — always queue for review
    "suggest":    (10.0, 0.0),   # always draft for review, never auto-send
    "graduated":  (0.85, 0.50),  # social default (stricter than WhatsApp's 0.80)
    "aggressive": (0.70, 0.40),  # Agency only — more permissive
}


# ── Safety rails — hard floors that always block auto-send ──────────────────
#
# Each rail returns a string tag when it fires. The tags get persisted onto
# Interaction.safety_flags so we can audit false positives.

_REFUND_RE = re.compile(r"\b(refund|return|money\s*back|broken|defective)\b", re.IGNORECASE)
_PRICE_RE = re.compile(r"\b(price|cost|how much|kshs?|usd|fee)\b", re.IGNORECASE)

REPLY_LENGTH_LIMIT = 400   # chars — anything longer signals LLM uncertainty


@dataclass
class SafetyContext:
    """Inputs the safety rails inspect. Pass what you have; leave others empty."""
    reply_text: str = ""
    intent: str = ""                       # hours | booking | pricing | complaint | praise | spam | other
    post_has_cta_url: bool = False
    is_first_message_in_conversation: bool = False
    brand_has_engaged_before: bool = True  # default True so absence doesn't trip the rail
    contact_language: str = ""             # e.g. "sw", "en"; "" means unknown
    brand_known_languages: Iterable[str] = ()


def safety_check(ctx: SafetyContext) -> list[str]:
    """Run all hard safety rails. Returns the list of flags that fired."""
    flags: list[str] = []
    text = (ctx.reply_text or "").strip()

    if ctx.intent == "complaint":
        flags.append("intent_complaint")
    if ctx.intent == "pricing" and not ctx.post_has_cta_url:
        flags.append("pricing_without_sanctioned_cta")
    if ctx.intent == "spam":
        flags.append("intent_spam")

    if len(text) > REPLY_LENGTH_LIMIT:
        flags.append("reply_too_long")

    if ctx.is_first_message_in_conversation and not ctx.brand_has_engaged_before:
        flags.append("cold_first_contact")

    # Inbound message keyword regex (refund / return / broken / defective)
    # — these need a human, not autonomy.
    if _REFUND_RE.search(text):
        flags.append("refund_keyword")

    # Cross-language risk — contact wrote in a language Kova has never seen
    # from this brand. Auto-replying could be culturally mistuned.
    if ctx.contact_language and ctx.brand_known_languages:
        if ctx.contact_language not in set(ctx.brand_known_languages):
            flags.append("unfamiliar_language")

    return flags


# ── The core routing decision ───────────────────────────────────────────────


def route_reply(
    *,
    autonomy_level: str,
    confidence: float,
    safety_flags: Iterable[str] = (),
    suggested_action: str = "reply",
) -> RoutingAction:
    """Decide where an Engage Agent reply goes.

    Args:
        autonomy_level: one of "off" / "suggest" / "graduated" / "aggressive"
            (the user's UserProfile.engage_autonomy_level)
        confidence: LLM-reported confidence in the reply, [0.0, 1.0]
        safety_flags: list of safety-rail tags from safety_check(). Non-empty
            list forces the reply into draft-for-review regardless of
            confidence / autonomy.
        suggested_action: the LLM's own opt-out — "reply" / "escalate" /
            "no_reply". Honored when the LLM declines to answer.

    Returns:
        RoutingAction (AUTO_SEND / DRAFT_FOR_REVIEW / ESCALATE / SKIP).
    """
    # LLM opt-out is always respected.
    if suggested_action == "no_reply":
        return RoutingAction.SKIP
    if suggested_action == "escalate":
        return RoutingAction.ESCALATE

    # Safety rails always block auto-send. The user reviews in their inbox.
    flags = list(safety_flags or [])
    if flags:
        return RoutingAction.DRAFT_FOR_REVIEW

    # Clamp confidence into [0, 1].
    try:
        c = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        c = 0.0

    level = (autonomy_level or "suggest").lower()
    auto_send_min, draft_min = _THRESHOLDS.get(level, _THRESHOLDS["suggest"])

    if c >= auto_send_min:
        return RoutingAction.AUTO_SEND
    if c >= draft_min:
        return RoutingAction.DRAFT_FOR_REVIEW
    return RoutingAction.ESCALATE


# ── Plan tier gating ────────────────────────────────────────────────────────
#
# Caps which autonomy levels each plan tier is allowed to select. Enforced
# at form-validation time and at autonomy-routing time as a defence in
# depth (so a stale session can't auto-send beyond what the plan allows).

_MAX_LEVEL_BY_PLAN: dict[str, str] = {
    "starter":  "suggest",
    "growth":   "graduated",
    "pro":      "graduated",
    "agency":   "aggressive",
}

_LEVEL_RANK = {"off": 0, "suggest": 1, "graduated": 2, "aggressive": 3}


def max_level_for_plan(plan: str) -> str:
    """Highest engage_autonomy_level a given plan tier is allowed to set."""
    return _MAX_LEVEL_BY_PLAN.get((plan or "").lower(), "suggest")


def is_level_allowed(level: str, plan: str) -> bool:
    """Whether a plan tier is allowed to select this autonomy level."""
    requested = _LEVEL_RANK.get((level or "").lower(), -1)
    cap = _LEVEL_RANK.get(max_level_for_plan(plan), -1)
    return 0 <= requested <= cap


def clamp_level_to_plan(level: str, plan: str) -> str:
    """If `level` exceeds what `plan` allows, downgrade to the plan cap.

    Used as defence-in-depth in `route_reply`'s callers — a user whose plan
    was downgraded mid-cycle can't keep auto-sending at the higher level.
    """
    if is_level_allowed(level, plan):
        return (level or "suggest").lower()
    return max_level_for_plan(plan)
