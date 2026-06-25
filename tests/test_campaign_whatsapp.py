"""Tests for WhatsApp campaign approve + commerce share."""

import pytest

from apps.briefs.whatsapp_commands import _dispatch_command
from apps.content.campaigns import ensure_campaign_for_seed
from apps.content.models import ContentSeed, MarketingCampaign, Post
from apps.content.campaign_whatsapp import (
    approve_campaign_via_whatsapp,
    campaigns_pending_review,
    format_commerce_share_message,
)
from apps.platforms.models import SocialAccount


@pytest.fixture
def fb_account(user):
    return SocialAccount.objects.create(
        user=user,
        platform="facebook",
        platform_user_id="fb-wa",
        username="testfb",
        is_active=True,
    )


@pytest.mark.django_db
class TestCampaignWhatsApp:
    def _campaign_with_pending(self, user, fb_account):
        seed = ContentSeed.objects.create(user=user, idea="Weekend sale", status="completed")
        campaign = ensure_campaign_for_seed(seed, title="Weekend sale")
        campaign.status = MarketingCampaign.Status.REVIEW
        campaign.save(update_fields=["status", "updated_at"])
        Post.objects.create(
            user=user,
            seed=seed,
            social_account=fb_account,
            platform="facebook",
            content_text="Buy now",
            status=Post.Status.PENDING_APPROVAL,
        )
        return campaign

    def test_campaigns_pending_review(self, user, fb_account):
        self._campaign_with_pending(user, fb_account)
        rows = campaigns_pending_review(user)
        assert len(rows) == 1
        assert rows[0]["pending"] == 1

    def test_approve_campaign_via_whatsapp(self, user, fb_account):
        campaign = self._campaign_with_pending(user, fb_account)
        msg, ok, meta = approve_campaign_via_whatsapp(user, index=1)
        assert ok is True
        assert "Approved" in msg
        assert meta["approved"] == 1
        post = Post.objects.get(seed=campaign.content_seed_id)
        assert post.status == Post.Status.APPROVED

    def test_share_message_includes_urls(self, user, fb_account):
        self._campaign_with_pending(user, fb_account)
        msg, ok, meta = format_commerce_share_message(user, index=1)
        assert ok is True
        assert "/c/" in msg
        assert "/shop/" in msg
        assert meta["campaign_id"]

    def test_dispatch_campaigns_command(self, user, fb_account):
        self._campaign_with_pending(user, fb_account)
        text, cmd, ok, _ = _dispatch_command(user, "campaigns")
        assert cmd == "campaigns"
        assert ok is True
        assert "Weekend sale" in text

    def test_dispatch_approve_campaign_command(self, user, fb_account):
        self._campaign_with_pending(user, fb_account)
        text, cmd, ok, _ = _dispatch_command(user, "approve campaign")
        assert cmd == "approve_campaign_1"
        assert ok is True
        assert "Approved" in text

    def test_dispatch_share_command(self, user, fb_account):
        self._campaign_with_pending(user, fb_account)
        text, cmd, ok, _ = _dispatch_command(user, "share")
        assert cmd == "share_1"
        assert ok is True
        assert "Campaign page" in text
