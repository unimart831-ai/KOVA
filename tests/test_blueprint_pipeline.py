"""Tests for blueprint → create agent prompt wiring."""

from __future__ import annotations

import pytest

from apps.accounts.models import User
from apps.agents.create_agent import build_generation_prompt
from apps.content.blueprint_pipeline import attach_blueprint_to_seed
from apps.content.models import ContentSeed
from apps.products.models import BusinessAsset, Product


@pytest.fixture
def user(db):
    return User.objects.create_user(username="u", email="u@kova.ai", password="x")


def test_build_generation_prompt_includes_blueprint(user):
    product = Product.objects.create(
        user=user, name="Spa day", offering_type=Product.OfferingType.SERVICE, price=5000,
    )
    asset = BusinessAsset.objects.create(
        user=user,
        asset_type=BusinessAsset.AssetType.SERVICE,
        title="Spa day",
        product=product,
        metadata={"price": "5000", "duration_minutes": 90},
    )
    seed = ContentSeed.objects.create(user=user, product=product, idea="Book spa appointments")
    attach_blueprint_to_seed(seed, asset=asset, platforms=["instagram"])

    prompt = build_generation_prompt(seed, [{"platform": "instagram", "username": "spa"}])
    assert "CONTENT BLUEPRINT" in prompt
    assert "book" in prompt.lower()
    assert "Spa day" in prompt
