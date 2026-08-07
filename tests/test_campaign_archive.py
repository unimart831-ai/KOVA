"""Tests for campaign expiry and auto-archive."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.create.content.campaign_archive import (
    archive_expired_campaigns,
    default_campaign_expiry,
    is_campaign_publicly_live,
)
from apps.create.content.campaign_pages import resolve_public_campaign
from apps.create.content.campaigns import ensure_campaign_for_seed
from apps.create.content.models import ContentSeed, MarketingCampaign


@pytest.mark.django_db
class TestCampaignArchive:
    def test_offer_campaign_gets_short_expiry(self, user):
        seed = ContentSeed.objects.create(user=user, idea="Flash sale")
        campaign = ensure_campaign_for_seed(
            seed,
            title="Flash sale",
            proposal_meta={"angle": "flash", "intent": "offer"},
        )
        assert campaign.expires_at is not None
        delta = campaign.expires_at - timezone.now()
        assert 6 <= delta.days <= 8

    def test_archive_expired_campaigns(self, user):
        seed = ContentSeed.objects.create(user=user, idea="Ended offer")
        campaign = ensure_campaign_for_seed(seed, title="Ended")
        campaign.expires_at = timezone.now() - timedelta(hours=1)
        campaign.status = MarketingCampaign.Status.PUBLISHED
        campaign.save(update_fields=["expires_at", "status", "updated_at"])

        result = archive_expired_campaigns()
        assert result["archived"] == 1
        campaign.refresh_from_db()
        assert campaign.status == MarketingCampaign.Status.ARCHIVED

    def test_public_page_hidden_when_archived(self, user):
        seed = ContentSeed.objects.create(user=user, idea="Hidden")
        campaign = ensure_campaign_for_seed(seed, title="Hidden")
        campaign.status = MarketingCampaign.Status.ARCHIVED
        campaign.save(update_fields=["status", "updated_at"])

        assert resolve_public_campaign(campaign.slug) is None
        assert is_campaign_publicly_live(campaign) is False

    def test_default_expiry_by_objective(self):
        exp = default_campaign_expiry(objective="awareness")
        assert (exp - timezone.now()).days >= 29
