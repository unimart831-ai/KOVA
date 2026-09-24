"""Tests for the action-tense brief data builder (Phase 3 W12).

Covers `_build_action_summary` — the helper that aggregates concrete
agent activity over the last 24 hours so the Daily Brief LLM can
write in AI-first-person ("I auto-replied to 7 comments…").
"""
from __future__ import annotations

import pytest

from apps.core.accounts.models import User, UserProfile
from apps.create.briefs.tasks import _build_action_summary


@pytest.fixture
def owner(db):
    u = User.objects.create_user(
        username="owner", email="owner@kova.ai", password="x",
        full_name="Test",
    )
    UserProfile.objects.filter(user=u).update(plan="growth")
    return u


class TestActionSummary:
    def test_empty_shape(self, owner):
        s = _build_action_summary(owner)
        assert s["engage"] == {"auto_sent": 0, "escalated": 0, "drafts_pending": 0}
        assert s["walk_ins"] == 0
        assert s["bookings_completed"] == 0
        assert s["reviews"]["scheduled"] == 0
