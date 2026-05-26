"""Tests for WhatsApp reply-to-act on daily brief."""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from apps.accounts.models import User, UserProfile
from apps.briefs.models import DailyBrief, BriefWhatsAppLog
from apps.briefs.whatsapp_commands import (
    _dispatch_command,
    find_user_by_whatsapp_id,
)
from apps.content.models import Post
from apps.platforms.models import SocialAccount


@pytest.fixture
def pro_user(db):
    u = User.objects.create_user(
        username="pro", email="pro@kova.ai", password="x",
        full_name="Pro User", phone_number="0712345678",
        brief_whatsapp_enabled=True,
    )
    UserProfile.objects.filter(user=u).update(plan="pro")
    return u


@pytest.fixture
def today_brief(pro_user):
    return DailyBrief.objects.create(
        user=pro_user,
        date=date.today(),
        summary="Para 1.\n\nPara 2.\n\nYour move today: Check inbox.",
        posts_pending=2,
        kova_score=80,
        kova_score_delta=3,
        suggested_posts=[
            {"idea": "First idea", "platform": "instagram"},
            {"idea": "Second idea", "platform": "facebook"},
        ],
    )


class TestFindUserByWhatsappId:
    def test_matches_kenyan_local_phone(self, pro_user):
        assert find_user_by_whatsapp_id("254712345678") == pro_user

    def test_unknown_number(self, db):
        assert find_user_by_whatsapp_id("254799999999") is None


class TestDispatchCommand:
    def test_help(self, pro_user):
        text, cmd, ok, _ = _dispatch_command(pro_user, "help")
        assert cmd == "help"
        assert ok is True
        assert "APPROVE" in text

    def test_score_with_brief(self, pro_user, today_brief):
        text, cmd, ok, meta = _dispatch_command(pro_user, "score")
        assert cmd == "score"
        assert "80" in text
        assert meta["kova_score"] == 80

    def test_standup_command(self, pro_user, today_brief):
        text, cmd, ok, _ = _dispatch_command(pro_user, "standup")
        assert cmd == "standup"
        assert ok is True
        assert "Morning Standup" in text
        assert "APPROVE ALL" in text

    @patch("apps.briefs.whatsapp_commands._send_owner_reply", return_value=True)
    def test_approve_no_pending(self, _reply, pro_user, today_brief):
        text, cmd, ok, _ = _dispatch_command(pro_user, "approve")
        assert "Nothing to approve" in text

    def test_idea_out_of_range(self, pro_user, today_brief):
        text, cmd, ok, _ = _dispatch_command(pro_user, "idea 9")
        assert ok is False
        assert "Only 2 idea" in text

    @patch("apps.briefs.actions.create_seed_from_brief_idea")
    def test_idea_queues_seed(self, mock_seed, pro_user, today_brief):
        from apps.content.models import ContentSeed

        mock_seed.return_value = ContentSeed(user=pro_user, idea="Second idea")
        text, cmd, ok, meta = _dispatch_command(pro_user, "idea 2")
        assert cmd == "idea_2"
        assert ok is True
        mock_seed.assert_called_once()

    def test_approve_first_post(self, pro_user, today_brief):
        sa = SocialAccount.objects.create(
            user=pro_user, platform="instagram", username="test",
            platform_user_id="ig1", is_active=True,
        )
        post = Post.objects.create(
            user=pro_user,
            social_account=sa,
            content_text="Test post content",
            status=Post.Status.PENDING_APPROVAL,
        )
        text, cmd, ok, result = _dispatch_command(pro_user, "approve")
        assert ok is True
        assert result["approved"] == 1
        post.refresh_from_db()
        assert post.status == Post.Status.APPROVED


class TestBriefWhatsAppLog:
    @patch("apps.briefs.whatsapp_commands._send_owner_action_buttons", return_value=True)
    @patch("apps.briefs.whatsapp_commands._send_owner_reply", return_value=True)
    def test_handle_owner_command_logs(self, _reply, _buttons, pro_user, today_brief):
        from apps.briefs.whatsapp_commands import handle_owner_brief_command

        msg = {
            "from": "254712345678",
            "type": "text",
            "text": {"body": "help"},
        }
        assert handle_owner_brief_command(msg) is True
        assert BriefWhatsAppLog.objects.filter(user=pro_user, command="help").exists()

    @patch("apps.briefs.whatsapp_commands._send_owner_action_buttons", return_value=True)
    @patch("apps.briefs.whatsapp_commands._send_owner_reply", return_value=True)
    def test_button_reply_id_maps_to_approve(self, mock_reply, _buttons, pro_user, today_brief):
        from apps.briefs.whatsapp_commands import handle_owner_brief_command

        msg = {
            "from": "254712345678",
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "brief_approve", "title": "Approve"},
            },
        }
        assert handle_owner_brief_command(msg) is True
        assert BriefWhatsAppLog.objects.filter(user=pro_user, command="approve").exists()
