"""Tests for Today money board aggregate counts."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.briefs.dashboard import get_money_board_stats
from apps.content.models import Post
from apps.engage.models import Interaction
from apps.leads.models import Lead
from apps.platforms.models import SocialAccount
from apps.whatsapp.models import WhatsAppConversation


@pytest.mark.django_db
class TestMoneyBoardStats:
    def test_counts_needs_reply_hot_leads_and_approvals(self, user):
        user.onboarding_completed = True
        user.save(update_fields=["onboarding_completed"])

        Interaction.objects.create(
            user=user,
            platform="instagram",
            interaction_type="comment",
            status="new",
            content="Price?",
            author_username="buyer1",
        )

        wa_account = SocialAccount.objects.create(
            user=user,
            platform="whatsapp",
            platform_user_id="wa1",
            username="biz",
            access_token="tok",
            is_active=True,
        )
        WhatsAppConversation.objects.create(
            social_account=wa_account,
            contact_wa_id="254712345678",
            status=WhatsAppConversation.Status.ESCALATED,
        )

        Lead.objects.create(
            user=user,
            email="hot@example.com",
            status=Lead.Status.NEW,
        )
        Lead.objects.create(
            user=user,
            email="contacted@example.com",
            status=Lead.Status.CONTACTED,
            last_activity_at=timezone.now() - timedelta(days=2),
        )

        Post.objects.create(
            user=user,
            platform="instagram",
            status="pending_approval",
            body="Approve me",
        )

        stats = get_money_board_stats(user)

        assert stats["needs_reply"] == 2
        assert stats["needs_reply_wa"] == 1
        assert stats["needs_reply_engage"] == 1
        assert stats["hot_leads"] == 2
        assert stats["ready_to_approve"] == 1
