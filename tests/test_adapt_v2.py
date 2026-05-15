"""Tests for the Adapt Agent v2 — the autonomous learning loop.

Spec: docs/specs/ADAPT_AGENT_V2_SPEC.md

This file grows alongside the W3-4 implementation:
  * Commit 1 (this file): schema + flag + Celery entry + stub
  * Commit 2: eligibility gates + 5 decision functions + apply_mutations
  * Commit 3: Daily Brief integration + Create/Strategist agents read
  * Commit 4: AI Learning settings page revert/reset
"""

import pytest

from apps.accounts.models import User, UserProfile


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
    """The ADAPT_AGENT_V2_ENABLED flag must default False so prod doesn't
    silently start mutating profiles on the first 12h cycle after deploy."""

    def test_flag_defaults_false(self, settings):
        # In test env we control it; this asserts the design intent —
        # never let this default flip to True without the rollout work.
        assert getattr(settings, "ADAPT_AGENT_V2_ENABLED", "unset") in (False, "unset"), (
            "ADAPT_AGENT_V2_ENABLED must default False — the spec requires a "
            "dry-run week before mutations apply."
        )


# ── Commit 1 — Stub task ────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAdaptStubTask:
    """The Commit-1 stub. Confirms run_for_user is callable, updates
    adapt_last_run_at, and reports skipped=True with the expected reason."""

    def test_stub_marks_last_run_at_and_skips(self):
        from django.utils import timezone as tz
        from apps.agents.adapt_agent import run_for_user

        u = User.objects.create_user(
            username="adapt_stub", email="stub@b.com", password="P1!",
        )
        before = tz.now()
        result = run_for_user(u)
        u.profile.refresh_from_db()

        assert result["skipped"] is True
        assert "stub" in result["skip_reason"]
        assert result["applied"] is False
        assert result["decisions"] == []
        assert u.profile.adapt_last_run_at is not None
        assert u.profile.adapt_last_run_at >= before

    def test_stub_handles_user_without_profile_gracefully(self):
        """Defence: if the profile FK is somehow missing, the stub must
        not crash the Celery worker mid-cycle."""
        from apps.agents.adapt_agent import run_for_user

        class _Bare:
            email = "bare@b.com"
        # The stub reads getattr(user, "profile", None) — feeding a
        # bare object exercises that branch without touching the DB.
        result = run_for_user(_Bare())
        assert result["skipped"] is True
        assert result["skip_reason"] == "no_profile"
