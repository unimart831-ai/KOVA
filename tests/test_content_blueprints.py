"""Tests for content blueprint schema foundation."""
from __future__ import annotations

import pytest

from apps.accounts.models import User
from apps.content.blueprints import (
    build_blueprint_from_asset,
    validate_blueprint,
)
from apps.products.models import BusinessAsset


@pytest.fixture
def asset(db):
    user = User.objects.create_user(username="u", email="u@kova.ai", password="x")
    return BusinessAsset.objects.create(
        user=user,
        asset_type=BusinessAsset.AssetType.PRODUCT,
        title="Blue dress",
        description="Size M",
        metadata={"price": "2500", "currency": "KES"},
        status=BusinessAsset.Status.PUBLISHED,
        source=BusinessAsset.Source.SNAP,
    )


class TestContentBlueprints:
    def test_build_from_asset(self, asset):
        blueprint = build_blueprint_from_asset(asset)
        assert blueprint.objective == "sell"
        assert blueprint.title == "Blue dress"
        platforms = {p.platform for p in blueprint.platforms}
        assert "instagram" in platforms
        assert blueprint.to_dict()["asset_id"] == str(asset.id)

    def test_validate_blueprint(self, asset):
        data = build_blueprint_from_asset(asset).to_dict()
        ok, errors = validate_blueprint(data)
        assert ok is True
        assert errors == []

    def test_validate_rejects_empty(self):
        ok, errors = validate_blueprint({})
        assert ok is False
        assert errors
