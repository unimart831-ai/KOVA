"""Smoke tests for finish-sweep modules (Phase 0–7 wiring)."""

import pytest

from apps.briefs.asset_suggestions import asset_campaign_opportunities
from apps.content.campaign_approval import client_approval_blocks_publish
from apps.engage.lead_escalation import detect_lead_intent, escalate_flagged_threads
from apps.media.audience_dna import infer_audience_dna
from apps.media.authority_packs import authority_seed_ideas_for_user, is_authority_business


@pytest.mark.django_db
def test_asset_campaign_opportunities_empty(user):
    assert asset_campaign_opportunities(user) == []


@pytest.mark.django_db
def test_infer_audience_dna_from_profile(user):
    profile = user.profile
    profile.target_audience = "Nairobi salon owners"
    profile.save(update_fields=["target_audience"])
    dna = infer_audience_dna(user)
    assert "Nairobi" in dna.primary_audience


@pytest.mark.django_db
def test_authority_pack_for_professional(user):
    profile = user.profile
    profile.business_model = "professional"
    profile.save(update_fields=["business_model"])
    assert is_authority_business(user)
    ideas = authority_seed_ideas_for_user(user)
    assert len(ideas) >= 1
    assert "title" in ideas[0]


def test_detect_lead_intent():
    assert detect_lead_intent("How much is delivery?")
    assert not detect_lead_intent("Nice photo!")


@pytest.mark.django_db
def test_escalate_flagged_threads(user):
    from apps.engage.models import Interaction

    Interaction.objects.create(
        user=user,
        platform="instagram",
        content="What is the price for this?",
        sentiment="neutral",
    )
    count = escalate_flagged_threads(user)
    assert count == 1
    assert Interaction.objects.filter(user=user, status=Interaction.Status.FLAGGED).count() == 1


@pytest.mark.django_db
def test_client_approval_blocks_agency_publish(user):
    from apps.content.models import ContentSeed, MarketingCampaign

    seed = ContentSeed.objects.create(user=user, idea="Test campaign")
    campaign = MarketingCampaign.objects.create(
        user=user,
        content_seed=seed,
        title="Test",
        proposal_meta={"client_approval": {"status": "pending"}},
    )
    blocked, msg = client_approval_blocks_publish(campaign, user)
    assert blocked
    assert "pending" in msg.lower()
