"""Sprint L — CSV export, authority post, consult labels, attribution confidence, product voice."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User, UserProfile
from apps.accounts.product_voice import kova_voice_for_user, copy_for
from apps.briefs.asset_attribution import attribution_confidence_score
from apps.content.models import ContentSeed
from apps.leads.models import Lead
from apps.leads.professional_funnel import consult_funnel_stage_label, process_professional_consult_lead
from apps.products.models import BusinessAsset, CommercePayment, Product
from apps.products.professional_assets import create_authority_post_from_asset


@pytest.fixture
def pro_user(db):
    u = User.objects.create_user(username="prol", email="prol@kova.ai", password="x")
    UserProfile.objects.filter(user=u).update(business_model="professional", company_name="Acme")
    return u


@pytest.mark.django_db
def test_attribution_confidence_score_with_revenue(pro_user):
    product = Product.objects.create(user=pro_user, name="Win", price=1000)
    BusinessAsset.objects.create(
        user=pro_user, product=product, asset_type=BusinessAsset.AssetType.CASE_STUDY, title="Win",
    )
    CommercePayment.objects.create(
        user=pro_user,
        product=product,
        transaction_ref="l-1",
        checkout_request_id="ws_l_1",
        phone_number="254712345678",
        amount=Decimal("1000"),
        status=CommercePayment.Status.COMPLETED,
        completed_at=timezone.now(),
    )
    since = timezone.now() - timedelta(days=7)
    result = attribution_confidence_score(pro_user, since)
    assert result["score"] >= 20
    assert result["label"] in ("Building", "Growing", "Strong")
    assert result["factors"]


@pytest.mark.django_db
def test_consult_funnel_stage_label(pro_user):
    lead = Lead.objects.create(
        user=pro_user,
        name="Client",
        phone="254700000099",
        source=Lead.Source.SOCIAL_COMMENT,
        metadata={"pipeline": "professional_consult", "consult_funnel_stage": "booking_intent"},
    )
    assert consult_funnel_stage_label(lead) == "Booking intent"


@pytest.mark.django_db
def test_export_asset_breakdown_csv(client, pro_user):
    client.force_login(pro_user)
    url = reverse("analytics:export_asset_breakdown")
    resp = client.get(url + "?days=7")
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert b"Asset type" in resp.content


@pytest.mark.django_db
@patch("apps.products.professional_assets.fire_task")
def test_create_authority_post_from_asset(mock_fire, pro_user):
    asset = BusinessAsset.objects.create(
        user=pro_user,
        asset_type=BusinessAsset.AssetType.PORTFOLIO,
        title="Brand refresh",
        metadata={"client": "Co Ltd"},
    )
    seed = create_authority_post_from_asset(pro_user, asset)
    assert seed.user == pro_user
    assert seed.blueprint
    assert ContentSeed.objects.filter(pk=seed.pk).exists()
    mock_fire.assert_called_once()


@pytest.mark.django_db
def test_showcase_create_post_action(client, pro_user):
    asset = BusinessAsset.objects.create(
        user=pro_user,
        asset_type=BusinessAsset.AssetType.CASE_STUDY,
        title="Tax case",
    )
    client.force_login(pro_user)
    with patch("apps.products.professional_assets.fire_task"):
        resp = client.post(reverse("products:showcase"), {
            "action": "create_post",
            "asset_id": str(asset.pk),
        })
    assert resp.status_code == 302
    assert "studio" in resp.url


@pytest.mark.django_db
def test_kova_voice_professional_copy(pro_user):
    voice = kova_voice_for_user(pro_user)
    assert voice["kova_subhead"] == "You approve in 5 minutes."
    assert "consultation" in voice["kova_copy"]["today"].lower()
    assert copy_for("service", "sell")


@pytest.mark.django_db
def test_lead_list_shows_consult_label(client, pro_user):
    Lead.objects.create(
        user=pro_user,
        name="Hot lead",
        phone="254711111111",
        source=Lead.Source.SOCIAL_COMMENT,
        temperature=Lead.Temperature.HOT,
    )
    lead = Lead.objects.get(user=pro_user)
    process_professional_consult_lead(
        lead, pro_user, interaction=type("Ix", (), {"ai_intent": "booking"})(),
    )
    client.force_login(pro_user)
    resp = client.get(reverse("leads:list"))
    assert resp.status_code == 200
    assert b"Booking intent" in resp.content
