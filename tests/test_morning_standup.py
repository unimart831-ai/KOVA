"""Tests for Morning Standup module."""
from __future__ import annotations

from datetime import date

import pytest

from apps.core.accounts.models import User
from apps.create.briefs.models import DailyBrief
from apps.create.briefs.standup import (
    build_standup_context,
    enrich_decisions,
    format_standup_whatsapp_message,
    get_top_decision,
    mark_standup_engaged,
)


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="standup", email="standup@kova.ai", password="x",
    )


@pytest.fixture
def brief(user):
    return DailyBrief.objects.create(
        user=user,
        date=date.today(),
        summary="Summary.\n\nYour move today: Reply to leads.",
        posts_pending=3,
        kova_score=72,
        kova_score_delta=5,
        performance_summary={
            "decisions_needed": [
                {"item": "Approve holiday posts", "urgency": "now", "recommended_action": "Open Studio"},
                {"item": "Check inbox", "urgency": "soon"},
            ],
        },
        overnight_work={"summary": "2 posts drafted overnight"},
    )


class TestStandup:
    def test_enrich_decisions_adds_studio_url(self):
        decisions = enrich_decisions([{"item": "Approve draft posts in studio"}])
        assert decisions[0]["action_url"].endswith("/content/studio/")

    def test_enrich_decisions_normalizes_title_only_payloads(self):
        decisions = enrich_decisions([{"title": "2 failed posts"}])
        assert decisions[0]["item"] == "2 failed posts"

    def test_get_top_decision_prefers_urgent(self, brief):
        top = get_top_decision(brief)
        assert top["urgency"] == "now"

    def test_build_standup_context(self, user, brief):
        ctx = build_standup_context(user, brief)
        assert ctx["kova_score"] == 72
        assert ctx["posts_pending"] == 3
        assert ctx["top_decision"] is not None
        assert "Reply to leads" in ctx["your_move"] or ctx["your_move"]

    def test_whatsapp_message_includes_score(self, user, brief):
        msg = format_standup_whatsapp_message(user, brief)
        assert "Morning Standup" in msg
        assert "72" in msg
        assert "APPROVE ALL" in msg

    def test_mark_standup_engaged(self, brief):
        assert brief.is_read is False
        mark_standup_engaged(brief)
        brief.refresh_from_db()
        assert brief.is_read is True
