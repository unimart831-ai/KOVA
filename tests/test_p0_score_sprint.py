"""P0 score sprint — Growth WA, QR leads, digests, engage trial, token gate."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.billing.engage_trial import (
    can_consume_engage_trial_reply,
    get_engage_trial_usage,
    record_engage_trial_reply,
)
from apps.billing.models import PLAN_LIMITS, get_user_plan_limits
from apps.billing.whatsapp_access import whatsapp_inbox_allowed, whatsapp_full_allowed
from apps.briefs.dashboard import get_money_board_stats
from apps.content.approval import approve_post_for_user
from apps.content.models import Post
from apps.leads.bridges import create_lead_from_qr_scan
from apps.leads.models import Lead
from apps.platforms.models import SocialAccount
from apps.platforms.token_health import get_post_token_block
from apps.accounts.models import User, UserProfile
from apps.qr_attribution.models import QRCode


@pytest.fixture
def growth_user(db):
    u = User.objects.create_user(
        username="p0growth",
        email="p0growth@kova.ai",
        password="TestPass123!",
    )
    UserProfile.objects.filter(user=u).update(plan="growth")
    u.onboarding_completed = True
    u.save(update_fields=["onboarding_completed"])
    return u


@pytest.mark.django_db
class TestGrowthWhatsAppWedge:
    def test_growth_has_inbox_not_full(self):
        growth = PLAN_LIMITS["growth"]
        assert growth["whatsapp_inbox_enabled"] is True
        assert growth["whatsapp_enabled"] is False
        assert whatsapp_inbox_allowed(growth) is True
        assert whatsapp_full_allowed(growth) is False

    def test_growth_can_open_inbox(self, client, growth_user):
        client.force_login(growth_user)
        resp = client.get(reverse("whatsapp:inbox"))
        assert resp.status_code == 200

    def test_growth_blocked_from_broadcasts(self, client, growth_user):
        client.force_login(growth_user)
        resp = client.get(reverse("whatsapp:broadcast_list"))
        assert resp.status_code == 302
        assert "whatsapp" in resp.url


@pytest.mark.django_db
class TestStarterEngageTrial:
    def test_starter_trial_limits(self, user):
        limits = get_user_plan_limits(user)
        assert limits.get("engage_trial_enabled") is True
        assert limits.get("engage_trial_auto_replies_per_week") == 5

    def test_trial_counter(self, user):
        allowed, _ = can_consume_engage_trial_reply(user)
        assert allowed is True
        for _ in range(5):
            record_engage_trial_reply(user)
        allowed, msg = can_consume_engage_trial_reply(user)
        assert allowed is False
        assert "trial" in msg.lower()

    def test_starter_can_open_engage_inbox(self, client, user):
        client.force_login(user)
        resp = client.get(reverse("engage:inbox"))
        assert resp.status_code == 200


@pytest.mark.django_db
class TestQrScanLeadCapture:
    def test_create_lead_from_qr_scan(self, user):
        qr = QRCode.objects.create(user=user, label="Flyer")
        lead = create_lead_from_qr_scan(
            user=user, phone="0712345678", name="Jane", qr_code=qr,
        )
        assert lead is not None
        assert lead.source_type == Lead.Source.QR_SCAN
        assert lead.phone == "0712345678"

    def test_capture_endpoint(self, user):
        qr = QRCode.objects.create(user=user, label="Door")
        client = Client()
        resp = client.post(
            reverse("qr_attribution:scan_capture", kwargs={"token": qr.token}),
            {"phone": "0798765432", "name": "Sam"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert Lead.objects.filter(user=user, phone="0798765432").exists()


@pytest.mark.django_db
class TestMoneyBoardDigest:
    def test_digest_skips_zero_counts(self, user, monkeypatch):
        from apps.briefs import tasks as brief_tasks

        user.money_board_digest_enabled = True
        user.save(update_fields=["money_board_digest_enabled"])

        sent_mail = []
        monkeypatch.setattr(brief_tasks, "send_mail", lambda *a, **k: sent_mail.append(a))

        notifications = []
        monkeypatch.setattr(
            brief_tasks.Notification,
            "create_for_user",
            staticmethod(lambda **kw: notifications.append(kw)),
        )

        assert brief_tasks.send_money_board_digests() == 0
        assert not notifications
        assert not sent_mail

    def test_digest_sends_when_counts_positive(self, user, monkeypatch):
        from apps.briefs import tasks as brief_tasks
        from apps.engage.models import Interaction

        user.money_board_digest_enabled = True
        user.save(update_fields=["money_board_digest_enabled"])
        Interaction.objects.create(
            user=user,
            platform="instagram",
            interaction_type="comment",
            status="new",
            content="Price?",
            author_username="buyer",
        )

        notifications = []
        monkeypatch.setattr(
            brief_tasks.Notification,
            "create_for_user",
            staticmethod(lambda **kw: notifications.append(kw)),
        )
        monkeypatch.setattr(brief_tasks, "send_mail", lambda *a, **k: None)

        assert brief_tasks.send_money_board_digests() == 1
        assert "need reply" in notifications[0]["message"].lower()


@pytest.mark.django_db
class TestTokenExpiryApproveGate:
    def test_blocks_approve_when_token_expiring(self, user):
        account = SocialAccount.objects.create(
            user=user,
            platform="instagram",
            platform_user_id="ig1",
            username="shop",
            access_token="tok",
            is_active=True,
            token_expires_at=timezone.now() + timedelta(hours=6),
        )
        post = Post.objects.create(
            user=user,
            social_account=account,
            platform="instagram",
            status="pending_approval",
            body="Post text",
            media_urls=["https://example.com/a.jpg"],
        )
        assert get_post_token_block(post) is not None
        result = approve_post_for_user(user, post)
        assert result["success"] is False
        assert result["error"] == "token_expiring"


@pytest.mark.django_db
class TestMoneyBoardFilteredLinks:
    def test_stats_include_split_counts(self, user):
        from apps.engage.models import Interaction
        from apps.whatsapp.models import WhatsAppConversation

        Interaction.objects.create(
            user=user,
            platform="instagram",
            interaction_type="comment",
            status="new",
            content="Hi",
            author_username="a",
        )
        wa = SocialAccount.objects.create(
            user=user,
            platform="whatsapp",
            platform_user_id="wa",
            username="biz",
            access_token="t",
            is_active=True,
        )
        WhatsAppConversation.objects.create(
            social_account=wa,
            contact_wa_id="254700000001",
            status=WhatsAppConversation.Status.ESCALATED,
        )
        stats = get_money_board_stats(user)
        assert stats["needs_reply_wa"] == 1
        assert stats["needs_reply_engage"] == 1
