"""Tests for daily brief multi-channel delivery."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from apps.accounts.models import User, UserProfile
from apps.briefs.delivery import (
    build_mobile_digest,
    deliver_daily_brief,
    extract_your_move,
)
from apps.briefs.models import DailyBrief


@pytest.fixture
def owner(db):
    u = User.objects.create_user(
        username="owner", email="owner@kova.ai", password="x",
        full_name="Jane Owner", phone_number="0712345678",
    )
    UserProfile.objects.filter(user=u).update(plan="pro")
    return u


def _make_brief(user, **kwargs):
    defaults = {
        "user": user,
        "date": date.today(),
        "summary": (
            "I drafted 3 posts.\n\n"
            "Engagement is steady.\n\n"
            "Your move today: Approve the Instagram carousel before 10am."
        ),
        "posts_pending": 3,
        "kova_score": 72,
        "kova_score_delta": 4,
        "performance_summary": {
            "decisions_needed": [
                {"item": "2 flagged comments", "urgency": "now", "recommended_action": "Review inbox"},
            ],
        },
    }
    defaults.update(kwargs)
    return DailyBrief.objects.create(**defaults)


class TestExtractYourMove:
    def test_finds_your_move_paragraph(self):
        summary = "Para 1.\n\nPara 2.\n\nYour move today: Approve posts."
        assert "Approve posts" in extract_your_move(summary)

    def test_empty_summary(self):
        assert extract_your_move("") == ""


class TestBuildMobileDigest:
    def test_fallback_from_brief_fields(self, owner):
        brief = _make_brief(owner)
        digest = build_mobile_digest(brief)
        assert "3 post" in digest["headline"]
        assert "72" in digest["score_line"]
        assert len(digest["whatsapp_body"]) <= 200

    def test_uses_llm_digest_when_present(self, owner):
        brief = _make_brief(
            owner,
            performance_summary={
                "mobile_digest": {
                    "headline": "Custom headline",
                    "whatsapp_body": "Custom WA body",
                },
            },
        )
        digest = build_mobile_digest(brief)
        assert digest["headline"] == "Custom headline"
        assert digest["whatsapp_body"] == "Custom WA body"


class TestDeliverDailyBrief:
    @patch("apps.briefs.delivery._notify_brief_ready", return_value=True)
    @patch("apps.briefs.delivery._send_brief_email", return_value=True)
    @patch("apps.briefs.delivery._send_brief_whatsapp", return_value=False)
    def test_pro_user_gets_email_and_ws(self, _wa, _email, _ws, owner):
        brief = _make_brief(owner)
        results = deliver_daily_brief(owner, brief)
        assert results["websocket"] is True
        assert results["email"] is True
        _email.assert_called_once()

    @patch("apps.briefs.delivery._notify_brief_ready", return_value=True)
    @patch("apps.briefs.delivery._send_brief_email")
    @patch("apps.briefs.delivery._send_brief_whatsapp")
    def test_starter_skips_email(self, _wa, _email, _ws, owner):
        UserProfile.objects.filter(user=owner).update(plan="starter")
        brief = _make_brief(owner)
        results = deliver_daily_brief(owner, brief)
        assert results["email"] is False
        _email.assert_not_called()

    @patch("apps.briefs.delivery._notify_brief_ready", return_value=True)
    @patch("apps.briefs.delivery._send_brief_email", return_value=True)
    @patch("apps.briefs.delivery._send_brief_whatsapp", return_value=True)
    def test_respects_user_opt_out(self, _wa, _email, _ws, owner):
        owner.brief_email_enabled = False
        owner.brief_whatsapp_enabled = False
        owner.save(update_fields=["brief_email_enabled", "brief_whatsapp_enabled"])
        brief = _make_brief(owner)
        results = deliver_daily_brief(owner, brief)
        assert results["email"] is False
        assert results["whatsapp"] is False
        _email.assert_not_called()
        _wa.assert_not_called()
