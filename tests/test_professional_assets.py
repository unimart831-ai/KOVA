"""Tests for professional assets and templates."""

from __future__ import annotations

import pytest

from apps.accounts.models import User, UserProfile
from apps.content.blueprint_pipeline import attach_blueprint_to_seed
from apps.content.models import ContentSeed
from apps.content.professional_templates import apply_professional_template_to_blueprint
from apps.products.professional_assets import create_case_study, create_portfolio_item
from apps.products.models import BusinessAsset


@pytest.fixture
def pro_user(db):
    u = User.objects.create_user(username="pro", email="pro@kova.ai", password="x")
    UserProfile.objects.filter(user=u).update(business_model="professional", company_name="Acme Legal")
    return u


def test_create_portfolio_asset(pro_user):
    asset = create_portfolio_item(
        pro_user,
        title="Brand refresh",
        client="Nairobi Fintech",
        outcome="2x inbound leads",
    )
    assert asset.asset_type == BusinessAsset.AssetType.PORTFOLIO
    assert asset.metadata["client"] == "Nairobi Fintech"


def test_professional_template_on_blueprint(pro_user):
    asset = create_case_study(
        pro_user,
        title="Tax dispute win",
        client="SME client",
        pain="penalty notice",
        outcome="resolved in 30 days",
    )
    seed = ContentSeed.objects.create(user=pro_user, idea="Share case study")
    data = attach_blueprint_to_seed(seed, asset=asset, platforms=["linkedin"])
    assert data["metadata"].get("professional_template")
    assert "linkedin" in {p["platform"] for p in data["platforms"]}
