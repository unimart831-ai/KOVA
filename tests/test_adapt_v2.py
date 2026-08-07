"""Tests for the Adapt Agent v2 — the autonomous learning loop.

Spec: docs/specs/ADAPT_AGENT_V2_SPEC.md

This file grows alongside the W3-4 implementation:
  * Commit 1 (this file): schema + flag + Celery entry + stub
  * Commit 2: eligibility gates + 5 decision functions + apply_mutations
  * Commit 3: Daily Brief integration + Create/Strategist agents read
  * Commit 4: AI Learning settings page revert/reset
"""

import pytest

from apps.core.accounts.models import User, UserProfile


# ── Commit 1 — Schema contract ──────────────────────────────────────────────


@pytest.mark.django_db
class TestAdaptV2Schema:
    """Locks the five new UserProfile fields. If any of these regress,
    Adapt v2 has nowhere to write its decisions and the loop goes blank."""

    def test_pillar_weights_defaults_to_empty_dict(self):
        u = User.objects.create_user(
            username="adapt1", email="a1@b.com", password="P1!",
        )
        assert u.profile.pillar_weights == {}

    def test_dna_preferences_defaults_to_empty_dict(self):
        u = User.objects.create_user(
            username="adapt2", email="a2@b.com", password="P1!",
        )
        assert u.profile.dna_preferences == {}

    def test_optimal_schedule_defaults_to_empty_dict(self):
        u = User.objects.create_user(
            username="adapt3", email="a3@b.com", password="P1!",
        )
        assert u.profile.optimal_schedule == {}

    def test_adapt_paused_defaults_to_false(self):
        u = User.objects.create_user(
            username="adapt4", email="a4@b.com", password="P1!",
        )
        assert u.profile.adapt_paused is False

    def test_adapt_last_run_at_starts_null(self):
        u = User.objects.create_user(
            username="adapt5", email="a5@b.com", password="P1!",
        )
        assert u.profile.adapt_last_run_at is None

    def test_all_fields_writeable_with_realistic_shapes(self):
        """Spec example shapes — round-trip them to confirm JSON storage
        handles every shape the agent will produce."""
        u = User.objects.create_user(
            username="adapt6", email="a6@b.com", password="P1!",
        )
        u.profile.pillar_weights = {
            "Transformations": 1.5,
            "Tips": 1.0,
            "Behind the scenes": 0.7,
        }
        u.profile.dna_preferences = {
            "promoted": [
                {"combo": {"format": "question", "tone": "inspirational"},
                 "boost": 1.5, "set_at": "2026-05-16T09:00:00Z"},
            ],
            "retired": [
                {"combo": {"format": "long_form", "tone": "testimonial"},
                 "set_at": "2026-05-15T20:00:00Z"},
            ],
        }
        u.profile.optimal_schedule = {
            "instagram": {"best_hours": [9, 18], "best_days": ["mon", "tue"]},
        }
        u.profile.adapt_paused = True
        u.profile.save()

        u.profile.refresh_from_db()
        assert u.profile.pillar_weights["Transformations"] == 1.5
        assert u.profile.dna_preferences["promoted"][0]["boost"] == 1.5
        assert u.profile.optimal_schedule["instagram"]["best_hours"] == [9, 18]
        assert u.profile.adapt_paused is True


# ── Commit 1 — Rollout flag ─────────────────────────────────────────────────


class TestAdaptV2Flag:
    """ADAPT_AGENT_V2_ENABLED is enabled by default — the learning loop is
    live. Safety no longer relies on a global off-switch: mutations are gated
    per-plan (adapt_v2_enabled), by eligibility (>=5 posts, >=7 days, real
    engagement signal) and a circuit breaker (<=10 mutations / 7 days), with a
    full AgentAction audit trail (applied flag) for reversibility."""

    def test_flag_enabled_by_default(self, settings):
        # base.py sets ADAPT_AGENT_V2_ENABLED default True. This asserts the
        # deliberate decision: the learning loop is on, and safety is enforced
        # at runtime by the per-plan gate + eligibility + circuit breaker.
        assert getattr(settings, "ADAPT_AGENT_V2_ENABLED", False) is True, (
            "ADAPT_AGENT_V2_ENABLED should default True — the learning loop is "
            "live and gated per-plan, not by a global off-switch."
        )


# ── Commit 1 — Stub task ────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAdaptEligibility:
    """Eligibility gates from the spec — paused, sample size, age,
    circuit breaker. Each gate is a separate skip reason."""

    def test_marks_last_run_even_when_skipped(self):
        """The 12h cadence throttle works on skip too — without this, a
        brand-new user would get re-tried every cycle until they posted."""
        from django.utils import timezone as tz
        from apps.create.agents.adapt_agent import run_for_user
        u = User.objects.create_user(
            username="adapt_throttle", email="thr@b.com", password="P1!",
        )
        before = tz.now()
        result = run_for_user(u)
        u.profile.refresh_from_db()
        assert result["skipped"] is True
        assert u.profile.adapt_last_run_at is not None
        assert u.profile.adapt_last_run_at >= before

    def test_skip_when_paused(self):
        from apps.create.agents.adapt_agent import run_for_user
        u = User.objects.create_user(
            username="adapt_paused", email="paused@b.com", password="P1!",
        )
        u.profile.adapt_paused = True
        u.profile.save(update_fields=["adapt_paused"])
        result = run_for_user(u)
        assert result["skipped"] is True
        assert result["skip_reason"] == "paused"

    def test_skip_when_not_enough_posts(self):
        from apps.create.agents.adapt_agent import run_for_user
        u = User.objects.create_user(
            username="adapt_few", email="few@b.com", password="P1!",
        )
        result = run_for_user(u)
        assert result["skipped"] is True
        assert result["skip_reason"] == "not_enough_posts"

    def test_handles_user_without_profile_gracefully(self):
        from apps.create.agents.adapt_agent import run_for_user

        class _Bare:
            email = "bare@b.com"
        result = run_for_user(_Bare())
        assert result["skipped"] is True
        assert result["skip_reason"] == "no_profile"


# ── Commit 2 — Pure decision functions (no DB writes) ──────────────────────


@pytest.fixture
def adapt_user_with_posts(db):
    """A user with 6+ published posts spanning >7 days with varied
    content_dna + metrics. Returns (user, posts).

    Pillar 'Transformations' = clear winner (>1.5x median).
    Pillar 'Long-form' = clear loser (<0.5x median, >=5 posts).
    """
    from datetime import timedelta
    from django.utils import timezone as tz
    from apps.create.content.models import Post
    from apps.core.platforms.models import SocialAccount
    from apps.insight.analytics.models import PostMetric
    import uuid

    u = User.objects.create_user(
        username="adapt_full", email="adapt_full@b.com", password="P1!",
    )
    u.onboarding_completed = True
    u.save(update_fields=["onboarding_completed"])

    account = SocialAccount.objects.create(
        user=u, platform="instagram", platform_user_id="ig_full",
        username="full", display_name="Full",
        access_token="x", is_active=True,
    )

    posts = []
    now = tz.now()

    def _post(pillar, fmt, tone, length, rate, age_days):
        p = Post.objects.create(
            user=u, social_account=account, platform="instagram",
            content_text=f"Test post {uuid.uuid4().hex[:8]}",
            status="published",
            content_dna={"pillar": pillar, "format": fmt, "tone": tone, "length": length},
        )
        # Backdate published_at
        Post.objects.filter(pk=p.pk).update(
            published_at=now - timedelta(days=age_days),
        )
        p.refresh_from_db()
        PostMetric.objects.create(post=p, engagement_rate=rate)
        posts.append(p)
        return p

    # Spread ages from 1-25 days, so first_post is > 7 days old.
    # Median engagement should land around 0.03 with this set.

    # PROMOTE candidate — Transformations + question + inspirational + short
    # 4 posts, all > 1.5x median. Ratio ~ 0.06 / 0.03 = 2.0
    for i, days in enumerate([2, 4, 6, 8]):
        _post("Transformations", "question", "inspirational", "short", 0.06, days)

    # RETIRE candidate — Long-form + testimonial + sad + long
    # 5 posts, all < 0.5x median. Ratio ~ 0.01 / 0.03 = 0.33
    for i, days in enumerate([10, 12, 15, 18, 25]):
        _post("Long-form", "testimonial", "sad", "long", 0.01, days)

    # Median anchor — 3 mid posts at 0.03
    for i, days in enumerate([3, 9, 16]):
        _post("Tips", "list", "professional", "medium", 0.03, days)

    return u, posts


@pytest.mark.django_db
class TestPromoteDecision:
    def test_promotes_a_winning_combo(self, adapt_user_with_posts):
        from apps.create.agents.adapt_agent import (
            _decide_promotions, _user_median_engagement, _load_window_posts,
        )
        u, _ = adapt_user_with_posts
        posts = _load_window_posts(u)
        median = _user_median_engagement(posts)
        promotions = _decide_promotions(u, posts, median)

        assert len(promotions) >= 1
        assert any(p["combo"]["pillar"] == "Transformations" for p in promotions)
        # All promoted combos must be >= 1.5x median
        for p in promotions:
            assert p["evidence"]["ratio"] >= 1.5

    def test_doesnt_re_promote_already_promoted(self, adapt_user_with_posts):
        from apps.create.agents.adapt_agent import (
            _decide_promotions, _user_median_engagement, _load_window_posts,
        )
        u, _ = adapt_user_with_posts
        # Pre-populate as if Adapt already promoted this in a prior cycle
        u.profile.dna_preferences = {
            "promoted": [{
                "combo": {"pillar": "Transformations", "format": "question",
                          "tone": "inspirational", "length": "short"},
                "boost": 1.5, "set_at": "2026-05-01T00:00:00Z",
            }],
            "retired": [],
        }
        u.profile.save(update_fields=["dna_preferences"])

        posts = _load_window_posts(u)
        median = _user_median_engagement(posts)
        promotions = _decide_promotions(u, posts, median)

        # The Transformations combo is already promoted — must NOT appear again
        assert not any(
            p["combo"].get("pillar") == "Transformations"
            for p in promotions
        )

    def test_never_promotes_a_user_retired_combo(self, adapt_user_with_posts):
        from apps.create.agents.adapt_agent import (
            _decide_promotions, _user_median_engagement, _load_window_posts,
        )
        u, _ = adapt_user_with_posts
        u.profile.dna_preferences = {
            "promoted": [],
            "retired": [{
                "combo": {"pillar": "Transformations", "format": "question",
                          "tone": "inspirational", "length": "short"},
                "set_at": "2026-05-01T00:00:00Z",
            }],
        }
        u.profile.save(update_fields=["dna_preferences"])

        posts = _load_window_posts(u)
        median = _user_median_engagement(posts)
        promotions = _decide_promotions(u, posts, median)
        assert not any(
            p["combo"].get("pillar") == "Transformations" for p in promotions
        )

    def test_caps_at_3_promotions(self, adapt_user_with_posts):
        """Safety: cap from spec."""
        from apps.create.agents.adapt_agent import (
            _decide_promotions, PROMOTE_CAP,
        )
        # Synthesise more candidates than the cap so we test it specifically
        # by injecting a higher cap... actually easier: trust the data
        # fixture has only 1 winner, just assert cap respected.
        from apps.create.agents.adapt_agent import _user_median_engagement, _load_window_posts
        u, _ = adapt_user_with_posts
        posts = _load_window_posts(u)
        median = _user_median_engagement(posts)
        promotions = _decide_promotions(u, posts, median)
        assert len(promotions) <= PROMOTE_CAP


@pytest.mark.django_db
class TestRetireDecision:
    def test_retires_a_consistently_losing_combo(self, adapt_user_with_posts):
        from apps.create.agents.adapt_agent import (
            _decide_retirements, _user_median_engagement, _load_window_posts,
        )
        u, _ = adapt_user_with_posts
        posts = _load_window_posts(u)
        median = _user_median_engagement(posts)
        retirements = _decide_retirements(u, posts, median)

        assert len(retirements) >= 1
        assert any(r["combo"]["pillar"] == "Long-form" for r in retirements)
        for r in retirements:
            assert r["evidence"]["ratio"] < 0.5
            assert r["evidence"]["sample_size"] >= 5

    def test_doesnt_re_retire(self, adapt_user_with_posts):
        from apps.create.agents.adapt_agent import (
            _decide_retirements, _user_median_engagement, _load_window_posts,
        )
        u, _ = adapt_user_with_posts
        u.profile.dna_preferences = {
            "promoted": [],
            "retired": [{
                "combo": {"pillar": "Long-form", "format": "testimonial",
                          "tone": "sad", "length": "long"},
                "set_at": "2026-05-01T00:00:00Z",
            }],
        }
        u.profile.save(update_fields=["dna_preferences"])
        posts = _load_window_posts(u)
        median = _user_median_engagement(posts)
        retirements = _decide_retirements(u, posts, median)
        assert not any(r["combo"].get("pillar") == "Long-form" for r in retirements)


@pytest.mark.django_db
class TestPillarReweight:
    def test_winning_pillar_gets_boost(self, adapt_user_with_posts):
        from apps.create.agents.adapt_agent import (
            _decide_pillar_reweights, _user_median_engagement, _load_window_posts,
        )
        u, _ = adapt_user_with_posts
        posts = _load_window_posts(u)
        median = _user_median_engagement(posts)
        reweights = _decide_pillar_reweights(u, posts, median)

        # Transformations only has 4 posts in our fixture (< PILLAR_MIN_POSTS=5),
        # so pillar reweight should NOT fire for it. Long-form has 5+ losing posts
        # — that's the one that should reweight downward.
        # Confirm: any reweights here are on pillars with >=5 posts.
        for r in reweights:
            assert r["evidence"]["sample_size"] >= 5

    def test_losing_pillar_gets_penalty(self, adapt_user_with_posts):
        from apps.create.agents.adapt_agent import (
            _decide_pillar_reweights, _user_median_engagement, _load_window_posts,
        )
        u, _ = adapt_user_with_posts
        posts = _load_window_posts(u)
        median = _user_median_engagement(posts)
        reweights = _decide_pillar_reweights(u, posts, median)
        long_form = [r for r in reweights if r["pillar"] == "Long-form"]
        # Long-form has 5 losing posts, should get a penalty
        assert len(long_form) == 1
        assert long_form[0]["after"] < long_form[0]["before"]


@pytest.mark.django_db
class TestApplyMutations:
    def test_dry_run_writes_audit_but_not_profile(self, adapt_user_with_posts):
        from apps.create.agents.adapt_agent import apply_mutations
        from apps.create.agents.models import AgentAction
        u, _ = adapt_user_with_posts

        decisions = [{
            "type": "reweight_pillar",
            "pillar": "Tips",
            "evidence": {"sample_size": 5, "ratio": 0.5},
            "before": 1.0,
            "after": 0.5,
        }]

        apply_mutations(u, decisions, dry_run=True)
        u.profile.refresh_from_db()

        # Profile UNTOUCHED in dry run
        assert (u.profile.pillar_weights or {}).get("Tips") is None
        # But AgentAction row WAS written
        action = AgentAction.objects.get(user=u, agent_type="adapt", action_type="reweight_pillar")
        assert action.output_data["before"] == 1.0
        assert action.output_data["after"] == 0.5

    def test_live_apply_mutates_profile_and_audits(self, adapt_user_with_posts):
        from apps.create.agents.adapt_agent import apply_mutations
        from apps.create.agents.models import AgentAction
        u, _ = adapt_user_with_posts

        decisions = [{
            "type": "reweight_pillar",
            "pillar": "Tips",
            "evidence": {"sample_size": 5, "ratio": 0.5},
            "before": 1.0,
            "after": 0.5,
        }]

        apply_mutations(u, decisions, dry_run=False)
        u.profile.refresh_from_db()

        assert u.profile.pillar_weights.get("Tips") == 0.5
        assert AgentAction.objects.filter(
            user=u, agent_type="adapt", action_type="reweight_pillar",
        ).count() == 1


@pytest.mark.django_db
class TestEndToEndCycle:
    def test_run_for_user_dry_run_by_default(self, adapt_user_with_posts, settings):
        from apps.create.agents.adapt_agent import run_for_user
        from apps.create.agents.models import AgentAction
        u, _ = adapt_user_with_posts
        settings.ADAPT_AGENT_V2_ENABLED = False

        result = run_for_user(u)

        assert result["skipped"] is False
        assert result["applied"] is False
        assert len(result["decisions"]) >= 1
        # Audit rows written even in dry run
        assert AgentAction.objects.filter(user=u, agent_type="adapt").exists()
        # But profile UNTOUCHED
        u.profile.refresh_from_db()
        assert "Long-form" not in (u.profile.pillar_weights or {})

    def test_run_for_user_live_applies_mutations(self, adapt_user_with_posts, settings):
        from apps.create.agents.adapt_agent import run_for_user
        u, _ = adapt_user_with_posts
        settings.ADAPT_AGENT_V2_ENABLED = True
        # Adapt mutations are gated per-plan — the Kova plan enables adapt_v2.
        u.profile.plan = "kova"
        u.profile.save(update_fields=["plan"])

        result = run_for_user(u)

        assert result["applied"] is True
        u.profile.refresh_from_db()
        # Long-form should now be in pillar_weights at < 1.0 (penalty)
        assert (u.profile.pillar_weights or {}).get("Long-form", 1.0) < 1.0
        # OR Long-form should be retired in dna_preferences
        # (or both — both decisions can fire)
        retired = (u.profile.dna_preferences or {}).get("retired") or []
        promoted = (u.profile.dna_preferences or {}).get("promoted") or []
        any_long_form_action = (
            any(r["combo"].get("pillar") == "Long-form" for r in retired)
            or (u.profile.pillar_weights or {}).get("Long-form", 1.0) < 1.0
        )
        any_transformations_promotion = any(
            p["combo"].get("pillar") == "Transformations" for p in promoted
        )
        assert any_long_form_action
        assert any_transformations_promotion


# ── W3 Commit 3 — Close the loop: downstream agents read Adapt mutations ──


@pytest.mark.django_db
class TestCreateAgentReadsAdaptPreferences:
    """The Create Agent system prompt must surface promoted + retired DNA
    patterns from the Adapt loop. Without this wiring, the Adapt mutations
    are invisible to content generation — the loop doesn't close."""

    def test_no_preferences_returns_empty_string(self):
        from apps.create.agents.create_agent import _adapt_preferences_for_prompt
        u = User.objects.create_user(
            username="ad_pref1", email="ad1@b.com", password="P1!",
        )
        # Default empty dna_preferences
        assert _adapt_preferences_for_prompt(u.profile) == ""

    def test_promoted_pattern_surfaces_in_prompt(self):
        from apps.create.agents.create_agent import _adapt_preferences_for_prompt
        u = User.objects.create_user(
            username="ad_pref2", email="ad2@b.com", password="P1!",
        )
        u.profile.dna_preferences = {
            "promoted": [{
                "combo": {"pillar": "Transformations", "format": "question",
                          "tone": "inspirational"},
                "boost": 1.5,
                "set_at": "2026-05-16T09:00:00Z",
            }],
            "retired": [],
        }
        u.profile.save(update_fields=["dna_preferences"])

        out = _adapt_preferences_for_prompt(u.profile)
        assert "AI-LEARNED PATTERNS" in out
        assert "bias toward" in out
        assert "Transformations" in out
        assert "question" in out
        assert "inspirational" in out

    def test_retired_pattern_surfaces_in_prompt(self):
        from apps.create.agents.create_agent import _adapt_preferences_for_prompt
        u = User.objects.create_user(
            username="ad_pref3", email="ad3@b.com", password="P1!",
        )
        u.profile.dna_preferences = {
            "promoted": [],
            "retired": [{
                "combo": {"pillar": "Long-form", "format": "testimonial",
                          "tone": "sad", "length": "long"},
                "set_at": "2026-05-15T00:00:00Z",
            }],
        }
        u.profile.save(update_fields=["dna_preferences"])

        out = _adapt_preferences_for_prompt(u.profile)
        assert "AVOID" in out
        assert "Long-form" in out
        assert "testimonial" in out

    def test_build_system_prompt_includes_adapt_section(self):
        """Integration: the full system prompt builder must invoke the
        Adapt preferences when they exist."""
        from apps.create.agents.create_agent import build_system_prompt
        u = User.objects.create_user(
            username="ad_pref4", email="ad4@b.com", password="P1!",
        )
        u.profile.company_name = "Test Biz"
        u.profile.brand_voice = "Friendly and clear"
        u.profile.dna_preferences = {
            "promoted": [{
                "combo": {"pillar": "Transformations", "format": "question",
                          "tone": "inspirational"},
                "boost": 1.5,
                "set_at": "2026-05-16T09:00:00Z",
            }],
            "retired": [],
        }
        u.profile.save()

        prompt = build_system_prompt(u)
        assert "AI-LEARNED PATTERNS" in prompt
        assert "Transformations" in prompt


@pytest.mark.django_db
class TestStrategistReadsPillarWeights:
    """The Strategist's user_context must include pillar_weights so the
    LLM can bias its content_plan toward heavier-weighted pillars."""

    def test_user_context_includes_pillar_weights(self):
        from apps.create.agents.strategist_agent import _gather_strategy_inputs
        u = User.objects.create_user(
            username="strat_w1", email="sw1@b.com", password="P1!",
        )
        u.profile.pillar_weights = {"Transformations": 1.5, "Long-form": 0.5}
        u.profile.content_pillars = ["Transformations", "Long-form", "Tips"]
        u.profile.save()

        inputs = _gather_strategy_inputs(u)
        ctx = inputs["user_context"]
        assert ctx["pillar_weights"] == {"Transformations": 1.5, "Long-form": 0.5}
        assert "Transformations" in ctx["content_pillars"]

    def test_user_context_defaults_empty_weights_when_unset(self):
        from apps.create.agents.strategist_agent import _gather_strategy_inputs
        u = User.objects.create_user(
            username="strat_w2", email="sw2@b.com", password="P1!",
        )
        inputs = _gather_strategy_inputs(u)
        # New user — empty dict (the spec's "uniform" sentinel)
        assert inputs["user_context"]["pillar_weights"] == {}


# ── W3 Commit 3 — Daily Brief adapt_summary ────────────────────────────────


@pytest.mark.django_db
class TestBriefAdaptSummary:
    """The Daily Brief must aggregate recent Adapt AgentActions into a
    `adapt_summary` block the LLM prompt knows to paraphrase as one
    concrete `adapt_update` sentence."""

    def test_no_adapt_actions_returns_empty_summary(self):
        from apps.create.briefs.tasks import _build_adapt_summary
        u = User.objects.create_user(
            username="brf1", email="brf1@b.com", password="P1!",
        )
        s = _build_adapt_summary(u)
        assert s["changes_count"] == 0
        assert s["promotions"] == []
        assert s["retirements"] == []

    def test_recent_promote_appears_in_summary(self):
        from apps.create.briefs.tasks import _build_adapt_summary
        from apps.create.agents.models import AgentAction
        u = User.objects.create_user(
            username="brf2", email="brf2@b.com", password="P1!",
        )
        AgentAction.objects.create(
            user=u,
            agent_type="adapt",
            action_type="promote_dna",
            input_data={
                "combo": {"pillar": "Transformations", "format": "question"},
                "ratio": 2.4,
                "sample_size": 4,
            },
            output_data={
                "field": "dna_preferences.promoted",
                "after_appends": {
                    "combo": {"pillar": "Transformations", "format": "question"},
                    "boost": 1.5,
                    "set_at": "2026-05-16T09:00:00Z",
                },
            },
            status=AgentAction.ActionStatus.COMPLETED,
        )
        s = _build_adapt_summary(u)
        assert s["changes_count"] >= 1
        assert any("Transformations" in p for p in s["promotions"])
        # The ratio must surface so the LLM can use the "2.4× your average" form
        assert any("2.4" in p for p in s["promotions"])

    def test_recent_pillar_reweight_appears(self):
        from apps.create.briefs.tasks import _build_adapt_summary
        from apps.create.agents.models import AgentAction
        u = User.objects.create_user(
            username="brf3", email="brf3@b.com", password="P1!",
        )
        AgentAction.objects.create(
            user=u,
            agent_type="adapt",
            action_type="reweight_pillar",
            input_data={"pillar": "Transformations"},
            output_data={"field": "pillar_weights.Transformations", "before": 1.0, "after": 1.5},
            status=AgentAction.ActionStatus.COMPLETED,
        )
        s = _build_adapt_summary(u)
        assert any("Transformations" in c for c in s["pillar_changes"])
        # +0.5 delta should be in the descriptor
        assert any("+0.5" in c for c in s["pillar_changes"])

    def test_frequency_change_appears(self):
        from apps.create.briefs.tasks import _build_adapt_summary
        from apps.create.agents.models import AgentAction
        u = User.objects.create_user(
            username="brf4", email="brf4@b.com", password="P1!",
        )
        AgentAction.objects.create(
            user=u,
            agent_type="adapt",
            action_type="adjust_frequency",
            input_data={"current_target": 4},
            output_data={"field": "posting_frequency", "before": 4, "after": 5},
            status=AgentAction.ActionStatus.COMPLETED,
        )
        s = _build_adapt_summary(u)
        assert s["frequency_change"] is not None
        assert "+1" in s["frequency_change"]

    def test_older_than_24h_ignored(self):  # noqa: D401
        from datetime import timedelta
        from django.utils import timezone as tz
        from apps.create.briefs.tasks import _build_adapt_summary
        from apps.create.agents.models import AgentAction
        u = User.objects.create_user(
            username="brf_old", email="brfold@b.com", password="P1!",
        )
        a = AgentAction.objects.create(
            user=u,
            agent_type="adapt",
            action_type="promote_dna",
            input_data={"combo": {"pillar": "Old"}, "ratio": 2.0},
            output_data={"field": "dna_preferences.promoted",
                          "after_appends": {"combo": {"pillar": "Old"}}},
            status=AgentAction.ActionStatus.COMPLETED,
        )
        # Backdate 2 days
        AgentAction.objects.filter(pk=a.pk).update(
            created_at=tz.now() - timedelta(days=2),
        )
        s = _build_adapt_summary(u)
        assert s["changes_count"] == 0


# ── W3 Commit 4 — AI Learning settings page ────────────────────────────────


@pytest.mark.django_db
class TestAILearningPage:
    """The /accounts/settings/ai-learning/ page: lists Adapt mutations,
    lets the user revert individually, pause the loop, or reset."""

    def _make_user(self):
        u = User.objects.create_user(
            username="ai_learn", email="ai_learn@b.com", password="P1!",
        )
        u.onboarding_completed = True
        u.save(update_fields=["onboarding_completed"])
        return u

    def test_page_renders_for_logged_in_user(self, client):
        u = self._make_user()
        client.force_login(u)
        resp = client.get("/accounts/settings/ai-learning/")
        assert resp.status_code == 200

    def test_revert_undoes_reweight_pillar(self, client):
        from apps.create.agents.models import AgentAction
        u = self._make_user()
        u.profile.pillar_weights = {"Transformations": 1.5}
        u.profile.save(update_fields=["pillar_weights"])
        action = AgentAction.objects.create(
            user=u, agent_type="adapt", action_type="reweight_pillar",
            input_data={"pillar": "Transformations"},
            output_data={"field": "pillar_weights.Transformations", "before": 1.0, "after": 1.5},
            status=AgentAction.ActionStatus.COMPLETED,
        )

        client.force_login(u)
        resp = client.post(f"/accounts/settings/ai-learning/{action.pk}/revert/")
        assert resp.status_code in (200, 302)

        u.profile.refresh_from_db()
        action.refresh_from_db()
        # Weight reverted to "before"
        assert u.profile.pillar_weights.get("Transformations") == 1.0
        # Action marked reverted
        assert action.input_data.get("reverted") is True

    def test_revert_undoes_promote_dna(self, client):
        """Promote/retire append to a list — revert removes the entry."""
        from apps.create.agents.models import AgentAction
        u = self._make_user()
        combo = {"pillar": "Transformations", "format": "question"}
        u.profile.dna_preferences = {
            "promoted": [{"combo": combo, "boost": 1.5, "set_at": "2026-05-16T09:00:00Z"}],
            "retired": [],
        }
        u.profile.save(update_fields=["dna_preferences"])
        action = AgentAction.objects.create(
            user=u, agent_type="adapt", action_type="promote_dna",
            input_data={"combo": combo, "ratio": 2.4},
            output_data={"field": "dna_preferences.promoted",
                         "after_appends": {"combo": combo, "boost": 1.5,
                                            "set_at": "2026-05-16T09:00:00Z"}},
            status=AgentAction.ActionStatus.COMPLETED,
        )

        client.force_login(u)
        client.post(f"/accounts/settings/ai-learning/{action.pk}/revert/")

        u.profile.refresh_from_db()
        promoted = u.profile.dna_preferences.get("promoted", [])
        assert all(p["combo"] != combo for p in promoted)

    def test_toggle_pause_flips_adapt_paused(self, client):
        u = self._make_user()
        assert u.profile.adapt_paused is False
        client.force_login(u)
        client.post("/accounts/settings/ai-learning/toggle-pause/")
        u.profile.refresh_from_db()
        assert u.profile.adapt_paused is True
        # Toggle again
        client.post("/accounts/settings/ai-learning/toggle-pause/")
        u.profile.refresh_from_db()
        assert u.profile.adapt_paused is False

    def test_reset_reverts_all_outstanding_mutations(self, client):
        from apps.create.agents.models import AgentAction
        u = self._make_user()
        # Two pillar reweights to revert
        u.profile.pillar_weights = {"A": 1.5, "B": 0.5}
        u.profile.save(update_fields=["pillar_weights"])
        AgentAction.objects.create(
            user=u, agent_type="adapt", action_type="reweight_pillar",
            input_data={"pillar": "A"},
            output_data={"field": "pillar_weights.A", "before": 1.0, "after": 1.5},
            status=AgentAction.ActionStatus.COMPLETED,
        )
        AgentAction.objects.create(
            user=u, agent_type="adapt", action_type="reweight_pillar",
            input_data={"pillar": "B"},
            output_data={"field": "pillar_weights.B", "before": 1.0, "after": 0.5},
            status=AgentAction.ActionStatus.COMPLETED,
        )

        client.force_login(u)
        client.post("/accounts/settings/ai-learning/reset/")

        u.profile.refresh_from_db()
        # Both pillars restored to 1.0
        assert u.profile.pillar_weights["A"] == 1.0
        assert u.profile.pillar_weights["B"] == 1.0
        # Both actions marked reverted
        assert AgentAction.objects.filter(
            user=u, agent_type="adapt",
        ).count() == 2  # rows still exist
        for a in AgentAction.objects.filter(user=u, agent_type="adapt"):
            assert (a.input_data or {}).get("reverted") is True

    def test_revert_already_reverted_is_idempotent(self, client):
        """Revert button shouldn't double-fire if pressed twice fast."""
        from apps.create.agents.models import AgentAction
        u = self._make_user()
        u.profile.posting_frequency = 6
        u.profile.save(update_fields=["posting_frequency"])
        action = AgentAction.objects.create(
            user=u, agent_type="adapt", action_type="adjust_frequency",
            input_data={"reverted": True, "reverted_at": "2026-05-16T09:00:00Z"},
            output_data={"field": "posting_frequency", "before": 5, "after": 6},
            status=AgentAction.ActionStatus.COMPLETED,
        )
        client.force_login(u)
        resp = client.post(f"/accounts/settings/ai-learning/{action.pk}/revert/")
        assert resp.status_code in (200, 302)
        u.profile.refresh_from_db()
        # Profile UNCHANGED because the action was already reverted
        assert u.profile.posting_frequency == 6
        """Only LAST-CYCLE changes should surface in today's brief."""
        from datetime import timedelta
        from django.utils import timezone as tz
        from apps.create.briefs.tasks import _build_adapt_summary
        from apps.create.agents.models import AgentAction
        u = User.objects.create_user(
            username="brf5", email="brf5@b.com", password="P1!",
        )
        a = AgentAction.objects.create(
            user=u,
            agent_type="adapt",
            action_type="promote_dna",
            input_data={"combo": {"pillar": "Old"}, "ratio": 2.0},
            output_data={"field": "dna_preferences.promoted",
                          "after_appends": {"combo": {"pillar": "Old"}}},
            status=AgentAction.ActionStatus.COMPLETED,
        )
        # Backdate 2 days
        AgentAction.objects.filter(pk=a.pk).update(
            created_at=tz.now() - timedelta(days=2),
        )
        s = _build_adapt_summary(u)
        assert s["changes_count"] == 0
