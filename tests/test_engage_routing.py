"""Tests for the Engage Agent v2 routing infrastructure.

Spec: docs/specs/ENGAGE_AGENT_V2_SPEC.md.

This file covers Commit 1 of the W2 implementation:
  * `engage_routing.route_reply()` — the pure routing decision
  * `engage_routing.safety_check()` — the 7 hard rails
  * `engage_routing.is_level_allowed` / `clamp_level_to_plan` — tier gating
  * The data migration that maps auto_engage → engage_autonomy_level
  * `_generate_single_reply()` returning a structured payload

Wire-up tests (Commit 2: auto_respond + form gating) and undo tests
(Commit 3) live in separate files when those commits land.
"""

import pytest

from apps.accounts.models import User, UserProfile
from apps.agents.engage_routing import (
    RoutingAction,
    SafetyContext,
    clamp_level_to_plan,
    is_level_allowed,
    max_level_for_plan,
    route_reply,
    safety_check,
)


# ── route_reply — the core decision matrix ──────────────────────────────────


class TestRouteReply:
    @pytest.mark.parametrize("level,confidence,expected", [
        # OFF — never auto-sends, never even drafts (always queue for review).
        # Note: our enum maps OFF to never-auto-send AND never-draft, so it
        # falls through to escalate. The expected outcome there is "queued
        # for review" — represented in the test below by DRAFT_FOR_REVIEW
        # when safety_flags are present, otherwise ESCALATE.
        ("off",        0.99, RoutingAction.ESCALATE),
        ("off",        0.50, RoutingAction.ESCALATE),

        # SUGGEST — always drafts, never auto-sends.
        ("suggest",    0.99, RoutingAction.DRAFT_FOR_REVIEW),
        ("suggest",    0.10, RoutingAction.DRAFT_FOR_REVIEW),

        # GRADUATED — auto-send at >= 0.85, draft 0.50-0.85, escalate < 0.50
        ("graduated",  0.95, RoutingAction.AUTO_SEND),
        ("graduated",  0.85, RoutingAction.AUTO_SEND),
        ("graduated",  0.84, RoutingAction.DRAFT_FOR_REVIEW),
        ("graduated",  0.50, RoutingAction.DRAFT_FOR_REVIEW),
        ("graduated",  0.49, RoutingAction.ESCALATE),

        # AGGRESSIVE — auto-send at >= 0.70, draft 0.40-0.70, escalate < 0.40
        ("aggressive", 0.80, RoutingAction.AUTO_SEND),
        ("aggressive", 0.70, RoutingAction.AUTO_SEND),
        ("aggressive", 0.69, RoutingAction.DRAFT_FOR_REVIEW),
        ("aggressive", 0.40, RoutingAction.DRAFT_FOR_REVIEW),
        ("aggressive", 0.39, RoutingAction.ESCALATE),
    ])
    def test_routing_matrix(self, level, confidence, expected):
        assert route_reply(autonomy_level=level, confidence=confidence) == expected

    def test_safety_flags_force_draft_even_at_max_confidence(self):
        assert route_reply(
            autonomy_level="aggressive",
            confidence=1.0,
            safety_flags=["intent_complaint"],
        ) == RoutingAction.DRAFT_FOR_REVIEW

    def test_llm_no_reply_action_skips_entirely(self):
        assert route_reply(
            autonomy_level="graduated",
            confidence=0.99,
            suggested_action="no_reply",
        ) == RoutingAction.SKIP

    def test_llm_escalate_action_escalates_even_at_max_confidence(self):
        assert route_reply(
            autonomy_level="graduated",
            confidence=1.0,
            suggested_action="escalate",
        ) == RoutingAction.ESCALATE

    def test_garbage_confidence_clamps_safely(self):
        # NaN, negative, > 1.0, string — all clamp to 0.0 (escalate path)
        assert route_reply(autonomy_level="graduated", confidence=-5.0) == RoutingAction.ESCALATE
        assert route_reply(autonomy_level="graduated", confidence=5.0) == RoutingAction.AUTO_SEND  # clamped to 1.0
        assert route_reply(autonomy_level="graduated", confidence="not a number") == RoutingAction.ESCALATE

    def test_unknown_autonomy_level_defaults_to_suggest(self):
        # Defence-in-depth: garbage in DB shouldn't auto-send
        assert route_reply(autonomy_level="bogus", confidence=0.99) == RoutingAction.DRAFT_FOR_REVIEW


# ── safety_check — the 7 hard rails ─────────────────────────────────────────


class TestSafetyCheck:
    def test_no_flags_for_clean_reply(self):
        ctx = SafetyContext(
            reply_text="Open till 11pm tonight 🙏",
            intent="hours",
            post_has_cta_url=True,
            brand_has_engaged_before=True,
        )
        assert safety_check(ctx) == []

    def test_complaint_intent_flagged(self):
        flags = safety_check(SafetyContext(
            reply_text="Sorry to hear that.", intent="complaint",
        ))
        assert "intent_complaint" in flags

    def test_pricing_without_cta_flagged(self):
        flags = safety_check(SafetyContext(
            reply_text="It costs KES 3,500.",
            intent="pricing",
            post_has_cta_url=False,
        ))
        assert "pricing_without_sanctioned_cta" in flags

    def test_pricing_with_cta_does_not_flag(self):
        flags = safety_check(SafetyContext(
            reply_text="It costs KES 3,500.",
            intent="pricing",
            post_has_cta_url=True,
        ))
        assert "pricing_without_sanctioned_cta" not in flags

    def test_spam_intent_flagged(self):
        flags = safety_check(SafetyContext(reply_text="Hi.", intent="spam"))
        assert "intent_spam" in flags

    def test_long_reply_flagged(self):
        flags = safety_check(SafetyContext(
            reply_text="x" * 401, intent="other",
        ))
        assert "reply_too_long" in flags

    def test_cold_first_contact_flagged(self):
        flags = safety_check(SafetyContext(
            reply_text="Hello!", intent="praise",
            is_first_message_in_conversation=True,
            brand_has_engaged_before=False,
        ))
        assert "cold_first_contact" in flags

    @pytest.mark.parametrize("text", [
        "Can I get a refund please?",
        "I want to return this.",
        "I need my money back",
        "The product is broken.",
        "It arrived defective.",
    ])
    def test_refund_keyword_flagged(self, text):
        flags = safety_check(SafetyContext(reply_text=text, intent="other"))
        assert "refund_keyword" in flags

    def test_unfamiliar_language_flagged(self):
        flags = safety_check(SafetyContext(
            reply_text="Hello",
            intent="other",
            contact_language="fr",
            brand_known_languages=["en", "sw"],
        ))
        assert "unfamiliar_language" in flags

    def test_familiar_language_does_not_flag(self):
        flags = safety_check(SafetyContext(
            reply_text="Habari?",
            intent="other",
            contact_language="sw",
            brand_known_languages=["en", "sw"],
        ))
        assert "unfamiliar_language" not in flags


# ── Plan tier gating ────────────────────────────────────────────────────────


class TestPlanTierGating:
    @pytest.mark.parametrize("plan,expected_max", [
        ("starter", "suggest"),
        ("growth", "graduated"),
        ("pro", "graduated"),
        ("agency", "aggressive"),
    ])
    def test_max_level_per_plan(self, plan, expected_max):
        assert max_level_for_plan(plan) == expected_max

    def test_starter_cannot_set_graduated(self):
        assert is_level_allowed("graduated", "starter") is False

    def test_growth_can_set_graduated_not_aggressive(self):
        assert is_level_allowed("graduated", "growth") is True
        assert is_level_allowed("aggressive", "growth") is False

    def test_agency_can_set_everything(self):
        for level in ("off", "suggest", "graduated", "aggressive"):
            assert is_level_allowed(level, "agency") is True

    def test_clamp_downgrades_when_plan_is_too_low(self):
        assert clamp_level_to_plan("aggressive", "starter") == "suggest"
        assert clamp_level_to_plan("aggressive", "growth") == "graduated"

    def test_clamp_passes_through_allowed_level(self):
        assert clamp_level_to_plan("graduated", "growth") == "graduated"
        assert clamp_level_to_plan("aggressive", "agency") == "aggressive"


# ── Data migration: auto_engage → engage_autonomy_level ─────────────────────


@pytest.mark.django_db
class TestAutoEngageMigration:
    """The spec mandates auto_engage=True maps to SUGGEST (not GRADUATED)
    and auto_engage=False maps to OFF. We can't test the historical
    migration directly here, but we can test the steady-state semantics
    (the field exists, the default is SUGGEST, choices are correct)."""

    def test_default_engage_autonomy_level_is_suggest(self):
        u = User.objects.create_user(
            username="el", email="el@b.com", password="P1!",
        )
        assert u.profile.engage_autonomy_level == "suggest"

    def test_engage_autonomy_level_choices_match_spec(self):
        choices = dict(UserProfile.EngageAutonomyLevel.choices)
        assert "off" in choices
        assert "suggest" in choices
        assert "graduated" in choices
        assert "aggressive" in choices


# ── _generate_single_reply now returns a structured payload ────────────────


@pytest.mark.django_db
class TestSingleReplyPayload:
    def test_parse_payload_handles_valid_json(self):
        from apps.agents.engage_agent import _parse_reply_payload
        out = _parse_reply_payload('{"reply":"Hi!", "confidence":0.92, "intent":"praise", "action":"reply", "reasoning":"clear"}')
        assert out["reply"] == "Hi!"
        assert out["confidence"] == 0.92
        assert out["intent"] == "praise"

    def test_parse_payload_falls_back_for_non_json(self):
        from apps.agents.engage_agent import _parse_reply_payload
        out = _parse_reply_payload("Just a string, not JSON")
        # Falls back to low-confidence draft path
        assert out["reply"] == "Just a string, not JSON"
        assert out["confidence"] == 0.3
        assert out["action"] == "reply"

    def test_parse_payload_strips_code_fences(self):
        from apps.agents.engage_agent import _parse_reply_payload
        raw = '```json\n{"reply":"Open till 11pm", "confidence":0.88, "intent":"hours", "action":"reply", "reasoning":"in profile"}\n```'
        out = _parse_reply_payload(raw)
        assert out["reply"] == "Open till 11pm"
        assert out["confidence"] == 0.88

    def test_parse_payload_clamps_confidence(self):
        from apps.agents.engage_agent import _parse_reply_payload
        out = _parse_reply_payload('{"reply":"Hi", "confidence":5.0, "intent":"praise", "action":"reply"}')
        assert out["confidence"] == 1.0

    def test_parse_payload_sanitizes_unknown_intent(self):
        from apps.agents.engage_agent import _parse_reply_payload
        out = _parse_reply_payload('{"reply":"Hi", "confidence":0.5, "intent":"bogus", "action":"reply"}')
        assert out["intent"] == "other"

    def test_empty_response_returns_skip_payload(self):
        from apps.agents.engage_agent import _parse_reply_payload
        out = _parse_reply_payload("")
        assert out["action"] == "no_reply"
        assert out["confidence"] == 0.0
