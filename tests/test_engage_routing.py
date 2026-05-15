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


# ── auto_respond — the wiring (Commit 2) ────────────────────────────────────


@pytest.fixture
def engage_user(db):
    """A Growth-tier user with a connected social account and a candidate
    interaction. Returns (user, interaction)."""
    from apps.platforms.models import SocialAccount
    from apps.engage.models import Interaction

    u = User.objects.create_user(
        username="engage", email="engage@b.com", password="P1!",
    )
    # Completed onboarding so the redirect middleware doesn't intercept
    # client.post calls in TestUndoView / TestCorrectionView
    u.onboarding_completed = True
    u.save(update_fields=["onboarding_completed"])
    # Growth plan so GRADUATED is allowed
    u.profile.plan = "growth"
    u.profile.engage_autonomy_level = "graduated"
    u.profile.save(update_fields=["plan", "engage_autonomy_level"])

    account = SocialAccount.objects.create(
        user=u, platform="instagram", platform_user_id="ig123",
        username="testbiz", display_name="Test Biz",
        access_token="dummy", is_active=True,
    )

    interaction = Interaction.objects.create(
        user=u, social_account=account, platform="instagram",
        interaction_type=Interaction.InteractionType.COMMENT,
        author_name="Customer", content="What time are you open today?",
        ai_suggested_reply="Open till 11pm 🙏",
        ai_confidence=0.92, ai_intent="hours", safety_flags=[],
        platform_interaction_id="igcomment_123",
    )
    return u, account, interaction


@pytest.mark.django_db
class TestAutoRespondRouting:
    """Phase 1 W2 Commit 2 — auto_respond now uses engage_routing instead
    of always queuing for review. With the global flag off, AUTO_SEND
    decisions fall back to DRAFT_FOR_REVIEW so we test the routing logic
    without actually hitting platform APIs."""

    def test_high_confidence_auto_sends_when_flag_on(self, engage_user, settings, monkeypatch):
        from apps.engage.models import Interaction
        u, account, interaction = engage_user

        settings.ENGAGE_GRADUATED_AUTONOMY_ENABLED = True

        # Stub the actual platform send so we don't hit Instagram in tests.
        monkeypatch.setattr(
            "apps.agents.engage_agent._send_reply_to_platform",
            lambda i: {"ok": True, "platform_reply_id": "stub_reply_id", "error": ""},
        )

        from apps.agents.engage_agent import auto_respond
        counts = auto_respond(u)
        assert counts["auto_sent"] == 1
        interaction.refresh_from_db()
        assert interaction.status == Interaction.Status.AI_REPLIED
        assert interaction.ai_reply_sent == "Open till 11pm 🙏"
        assert interaction.responded_at is not None

    def test_high_confidence_falls_back_to_draft_when_flag_off(self, engage_user, settings):
        from apps.engage.models import Interaction
        u, account, interaction = engage_user

        settings.ENGAGE_GRADUATED_AUTONOMY_ENABLED = False

        from apps.agents.engage_agent import auto_respond
        counts = auto_respond(u)
        assert counts["auto_sent"] == 0
        assert counts["drafted"] == 1
        interaction.refresh_from_db()
        assert interaction.status == Interaction.Status.FLAGGED
        # Did NOT auto-send (no ai_reply_sent)
        assert interaction.ai_reply_sent == ""

    def test_low_confidence_escalates(self, engage_user, settings):
        from apps.engage.models import Interaction
        u, _, interaction = engage_user
        interaction.ai_confidence = 0.30
        interaction.save(update_fields=["ai_confidence"])

        settings.ENGAGE_GRADUATED_AUTONOMY_ENABLED = True

        from apps.agents.engage_agent import auto_respond
        counts = auto_respond(u)
        assert counts["escalated"] == 1
        assert counts["auto_sent"] == 0

    def test_safety_flag_blocks_auto_send(self, engage_user, settings, monkeypatch):
        u, _, interaction = engage_user
        interaction.safety_flags = ["intent_complaint"]
        interaction.save(update_fields=["safety_flags"])

        settings.ENGAGE_GRADUATED_AUTONOMY_ENABLED = True
        # If the platform send WERE called, this would crash the test.
        # Stays uncalled because safety flag forces DRAFT_FOR_REVIEW.
        monkeypatch.setattr(
            "apps.agents.engage_agent._send_reply_to_platform",
            lambda i: pytest.fail("Should not have auto-sent with safety flag"),  # noqa
        )

        from apps.agents.engage_agent import auto_respond
        counts = auto_respond(u)
        assert counts["auto_sent"] == 0
        assert counts["drafted"] == 1

    def test_off_level_skips_everything(self, engage_user, settings):
        u, _, _ = engage_user
        u.profile.engage_autonomy_level = "off"
        u.profile.save(update_fields=["engage_autonomy_level"])
        settings.ENGAGE_GRADUATED_AUTONOMY_ENABLED = True

        from apps.agents.engage_agent import auto_respond
        counts = auto_respond(u)
        assert counts == {"auto_sent": 0, "drafted": 0, "escalated": 0, "skipped": 0}

    def test_emergency_pause_halts_everything(self, engage_user, settings):
        u, _, _ = engage_user
        u.profile.emergency_pause = True
        u.profile.save(update_fields=["emergency_pause"])
        settings.ENGAGE_GRADUATED_AUTONOMY_ENABLED = True

        from apps.agents.engage_agent import auto_respond
        counts = auto_respond(u)
        assert counts == {"auto_sent": 0, "drafted": 0, "escalated": 0, "skipped": 0}

    def test_plan_downgrade_clamps_autonomy_level(self, engage_user, settings, monkeypatch):
        """A Growth user set to GRADUATED, then downgraded to Starter, must
        not keep auto-sending. clamp_level_to_plan downgrades them
        in-memory at routing time."""
        u, _, _ = engage_user
        # User had graduated set when on Growth; admin downgrades to starter
        u.profile.plan = "starter"
        u.profile.save(update_fields=["plan"])
        settings.ENGAGE_GRADUATED_AUTONOMY_ENABLED = True
        monkeypatch.setattr(
            "apps.agents.engage_agent._send_reply_to_platform",
            lambda i: pytest.fail("Should not have auto-sent after plan downgrade"),
        )

        from apps.agents.engage_agent import auto_respond
        counts = auto_respond(u)
        # Effective level becomes SUGGEST, so draft (not auto-send)
        assert counts["auto_sent"] == 0
        assert counts["drafted"] == 1

    def test_dm_never_auto_sends_v2(self, engage_user, settings, monkeypatch):
        """DM auto-send is deliberately deferred. Even at confidence 1.0
        with the flag on, _send_reply_to_platform returns False for DMs."""
        from apps.engage.models import Interaction
        u, _, interaction = engage_user
        interaction.interaction_type = Interaction.InteractionType.DM
        interaction.ai_confidence = 1.0
        interaction.save(update_fields=["interaction_type", "ai_confidence"])

        settings.ENGAGE_GRADUATED_AUTONOMY_ENABLED = True

        from apps.agents.engage_agent import auto_respond
        counts = auto_respond(u)
        # _send_reply_to_platform returns False for DMs -> drafted (fallback)
        assert counts["auto_sent"] == 0
        assert counts["drafted"] == 1


# ── BrandProfileForm tier-gating ────────────────────────────────────────────


@pytest.mark.django_db
class TestSettingsFormTierGating:
    """Plan-tier-gating in the settings form. Starter users can't see
    GRADUATED; Growth can't see AGGRESSIVE; Agency sees all."""

    def _make_user(self, plan="starter"):
        u = User.objects.create_user(
            username=f"tier_{plan}", email=f"{plan}@b.com", password="P1!",
        )
        u.profile.plan = plan
        u.profile.save(update_fields=["plan"])
        return u

    def test_starter_only_sees_off_and_suggest(self):
        from apps.accounts.forms import BrandProfileForm
        u = self._make_user("starter")
        form = BrandProfileForm(instance=u.profile)
        choices = dict(form.fields["engage_autonomy_level"].choices)
        assert set(choices.keys()) == {"off", "suggest"}

    def test_growth_sees_through_graduated(self):
        from apps.accounts.forms import BrandProfileForm
        u = self._make_user("growth")
        form = BrandProfileForm(instance=u.profile)
        choices = dict(form.fields["engage_autonomy_level"].choices)
        assert set(choices.keys()) == {"off", "suggest", "graduated"}
        assert "aggressive" not in choices

    def test_agency_sees_all_levels(self):
        from apps.accounts.forms import BrandProfileForm
        u = self._make_user("agency")
        form = BrandProfileForm(instance=u.profile)
        choices = dict(form.fields["engage_autonomy_level"].choices)
        assert set(choices.keys()) == {"off", "suggest", "graduated", "aggressive"}

    def test_starter_post_with_graduated_rejected(self):
        """Defence in depth: even if the form is tampered, the server-side
        clean rejects an out-of-plan level."""
        from apps.accounts.forms import BrandProfileForm
        u = self._make_user("starter")
        # Build a minimal valid form data POST
        form = BrandProfileForm(
            instance=u.profile,
            data={
                "company_name": "T",
                "engage_autonomy_level": "graduated",
                "posting_frequency": 5,
                "content_language": "en",
                "default_cta_type": "none",
                "industry": "",
                "industry_other": "",
                "country": "",
                "city": "",
                "brand_voice": "",
                "target_audience": "",
                "brand_restrictions": "",
                "visual_style": "auto",
                "brand_logo_url": "",
                "default_cta_url": "",
                "cta_phone": "",
                "cta_email": "",
                "cta_whatsapp": "",
                "auto_approve_posts": False,
                "tone_selection": [],
                "content_pillars_text": "",
                "brand_voice_examples_text": "",
                "brand_colors_text": "",
                "key_offerings_text": "",
                "goals_selection": [],
            },
        )
        assert not form.is_valid()
        assert "engage_autonomy_level" in form.errors


# ── W2 Commit 3 — EngageReply, Undo, Correction, Few-Shot ───────────────────


@pytest.mark.django_db
class TestEngageReplyCreation:
    """When auto_respond AUTO_SENDs, an EngageReply row must exist with the
    confidence snapshot and the platform_reply_id needed for later undo."""

    def test_auto_send_creates_engage_reply_with_undo_window(self, engage_user, settings, monkeypatch):
        from datetime import timedelta
        from apps.engage.models import EngageReply
        u, _, interaction = engage_user
        settings.ENGAGE_GRADUATED_AUTONOMY_ENABLED = True

        # Stub the platform send to return a real comment_id
        monkeypatch.setattr(
            "apps.agents.engage_agent._send_reply_to_platform",
            lambda i: {"ok": True, "platform_reply_id": "fb_comment_42", "error": ""},
        )

        from apps.agents.engage_agent import auto_respond
        counts = auto_respond(u)
        assert counts["auto_sent"] == 1

        reply = EngageReply.objects.get(interaction=interaction)
        assert reply.sent_text == "Open till 11pm 🙏"
        assert reply.confidence == 0.92
        assert reply.autonomy_level == "graduated"
        assert reply.platform_reply_id == "fb_comment_42"
        # 5-minute undo window
        import datetime as dt
        from django.utils import timezone as tz
        delta = reply.can_undo_until - reply.sent_at
        # Allow a few seconds slop for the timestamp differential
        assert dt.timedelta(seconds=290) <= delta <= dt.timedelta(seconds=310)
        assert reply.can_undo() is True

    def test_send_failure_creates_no_engage_reply(self, engage_user, settings, monkeypatch):
        from apps.engage.models import EngageReply
        u, _, _ = engage_user
        settings.ENGAGE_GRADUATED_AUTONOMY_ENABLED = True

        monkeypatch.setattr(
            "apps.agents.engage_agent._send_reply_to_platform",
            lambda i: {"ok": False, "platform_reply_id": "", "error": "API 500"},
        )

        from apps.agents.engage_agent import auto_respond
        counts = auto_respond(u)
        # Failed send falls back to drafted, no audit row written
        assert counts["auto_sent"] == 0
        assert counts["drafted"] == 1
        assert EngageReply.objects.count() == 0


@pytest.mark.django_db
class TestUndoWindow:
    """The 5-minute undo window — can_undo() is the source of truth."""

    def _make_reply(self, engage_user, *, minutes_ago=0):
        from datetime import timedelta
        from apps.engage.models import EngageReply
        from django.utils import timezone as tz
        _, _, interaction = engage_user
        reply = EngageReply.objects.create(
            interaction=interaction,
            sent_text="Auto reply",
            confidence=0.9,
            autonomy_level="graduated",
            safety_flags_snapshot=[],
            platform_reply_id="comment_abc",
            can_undo_until=tz.now() + timedelta(minutes=5 - minutes_ago),
        )
        # Backdate sent_at if needed
        if minutes_ago:
            EngageReply.objects.filter(pk=reply.pk).update(
                sent_at=tz.now() - timedelta(minutes=minutes_ago),
            )
            reply.refresh_from_db()
        return reply

    def test_can_undo_within_window(self, engage_user):
        reply = self._make_reply(engage_user, minutes_ago=2)
        assert reply.can_undo() is True

    def test_cannot_undo_after_window(self, engage_user):
        reply = self._make_reply(engage_user, minutes_ago=10)
        assert reply.can_undo() is False

    def test_cannot_undo_when_already_undone(self, engage_user):
        from django.utils import timezone as tz
        reply = self._make_reply(engage_user, minutes_ago=1)
        reply.undone_at = tz.now()
        reply.save(update_fields=["undone_at"])
        assert reply.can_undo() is False


@pytest.mark.django_db
class TestUndoView:
    """The /engage/auto-sent/<pk>/undo/ endpoint."""

    def test_undo_within_window_calls_provider_delete(self, engage_user, client, monkeypatch):
        from datetime import timedelta
        from apps.engage.models import EngageReply, Interaction
        from django.utils import timezone as tz
        u, _, interaction = engage_user
        reply = EngageReply.objects.create(
            interaction=interaction,
            sent_text="Auto reply",
            confidence=0.9,
            autonomy_level="graduated",
            platform_reply_id="comment_xyz",
            can_undo_until=tz.now() + timedelta(minutes=4),
        )
        # Set the interaction to AI_REPLIED so undo bumps it back to FLAGGED
        interaction.status = Interaction.Status.AI_REPLIED
        interaction.save(update_fields=["status"])

        # Stub the provider's delete_comment to succeed
        called = {"hits": 0}
        def fake_delete(**kw):
            called["hits"] += 1
            assert kw["comment_id"] == "comment_xyz"
            return {"success": True}

        class FakeProvider:
            delete_comment = staticmethod(fake_delete)

        monkeypatch.setattr(
            "apps.platforms.providers.registry.get_provider",
            lambda platform: FakeProvider,
        )

        client.force_login(u)
        resp = client.post(f"/engage/auto-sent/{reply.pk}/undo/")

        assert resp.status_code == 200
        assert called["hits"] == 1
        reply.refresh_from_db()
        assert reply.undone_at is not None
        interaction.refresh_from_db()
        assert interaction.status == Interaction.Status.FLAGGED

    def test_undo_after_window_returns_422(self, engage_user, client):
        from datetime import timedelta
        from apps.engage.models import EngageReply
        from django.utils import timezone as tz
        u, _, interaction = engage_user
        reply = EngageReply.objects.create(
            interaction=interaction,
            sent_text="Old reply",
            confidence=0.9,
            autonomy_level="graduated",
            platform_reply_id="comment_old",
            can_undo_until=tz.now() - timedelta(minutes=1),  # already closed
        )
        client.force_login(u)
        resp = client.post(f"/engage/auto-sent/{reply.pk}/undo/")
        assert resp.status_code == 422


@pytest.mark.django_db
class TestCorrectionView:
    """The /engage/auto-sent/<pk>/correct/ endpoint."""

    def test_correction_persists_text_and_reason(self, engage_user, client):
        from datetime import timedelta
        from apps.engage.models import EngageReply
        from django.utils import timezone as tz
        u, _, interaction = engage_user
        reply = EngageReply.objects.create(
            interaction=interaction,
            sent_text="AI's bad reply",
            confidence=0.9,
            autonomy_level="graduated",
            platform_reply_id="c1",
            can_undo_until=tz.now() + timedelta(minutes=4),
        )
        client.force_login(u)

        resp = client.post(f"/engage/auto-sent/{reply.pk}/correct/", {
            "correction_text": "I would have said: We're open till 10pm 🙏",
            "correction_reason": "tone",
        })
        assert resp.status_code == 200
        reply.refresh_from_db()
        assert reply.correction_text.startswith("I would have said")
        assert reply.correction_reason == "tone"
        assert reply.corrected_at is not None

    def test_empty_correction_text_rejected(self, engage_user, client):
        from datetime import timedelta
        from apps.engage.models import EngageReply
        from django.utils import timezone as tz
        u, _, interaction = engage_user
        reply = EngageReply.objects.create(
            interaction=interaction,
            sent_text="Auto reply",
            confidence=0.9,
            autonomy_level="graduated",
            platform_reply_id="c1",
            can_undo_until=tz.now() + timedelta(minutes=4),
        )
        client.force_login(u)
        resp = client.post(f"/engage/auto-sent/{reply.pk}/correct/", {
            "correction_text": "",
            "correction_reason": "tone",
        })
        assert resp.status_code == 400


@pytest.mark.django_db
class TestCorrectionFewShot:
    """Past corrections must feed back into the next Engage Agent prompt."""

    def test_recent_corrections_for_brand_returns_recent_corrections(self, engage_user):
        from datetime import timedelta
        from apps.engage.models import EngageReply
        from django.utils import timezone as tz
        u, _, interaction = engage_user
        EngageReply.objects.create(
            interaction=interaction,
            sent_text="AI said: Hey thanks!",
            confidence=0.9,
            autonomy_level="graduated",
            platform_reply_id="c1",
            can_undo_until=tz.now(),
            correction_text="Tunaomba subira tafadhali",
            correction_reason="tone",
            corrected_at=tz.now(),
        )
        from apps.agents.engage_agent import _recent_corrections_for_brand
        out = _recent_corrections_for_brand(u)
        assert "Tunaomba subira" in out
        assert "Wrong tone" in out  # the get_correction_reason_display

    def test_no_corrections_returns_empty_string(self, engage_user):
        from apps.agents.engage_agent import _recent_corrections_for_brand
        u, _, _ = engage_user
        assert _recent_corrections_for_brand(u) == ""


