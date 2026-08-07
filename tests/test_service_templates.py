"""Tests for service content template packs."""

from __future__ import annotations

import pytest

from apps.core.accounts.models import User
from apps.create.content.service_templates import (
    apply_service_template_to_blueprint,
    pick_service_template,
    service_template_prompt_lines,
)
from apps.commerce.products.models import BusinessAsset


@pytest.fixture
def service_asset(db):
    user = User.objects.create_user(username="s", email="s@kova.ai", password="x")
    return BusinessAsset.objects.create(
        user=user,
        asset_type=BusinessAsset.AssetType.SERVICE,
        title="Deep cleanse facial",
        metadata={"price": "4500", "duration_minutes": 60},
    )


def test_pick_service_template_deterministic(service_asset):
    a = pick_service_template(service_asset, seed="seed-1")
    b = pick_service_template(service_asset, seed="seed-1")
    assert a == b
    assert a in {"transformation", "testimonial", "offer"}


def test_apply_template_enriches_blueprint(service_asset):
    blueprint = {
        "asset_id": str(service_asset.id),
        "asset_type": "service",
        "objective": "book",
        "title": service_asset.title,
        "platforms": [{"platform": "instagram", "format": "feed", "slots": {}}],
        "metadata": {},
    }
    enriched = apply_service_template_to_blueprint(blueprint, "offer", service_asset, service_asset.user)
    assert enriched["metadata"]["service_template"] == "offer"
    assert "suggested_hooks" in enriched["metadata"]
    lines = service_template_prompt_lines(enriched)
    assert "TEMPLATE FAMILY" in lines or "SERVICE TEMPLATE" in lines
