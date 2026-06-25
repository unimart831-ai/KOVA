"""Tests for brief-driven Photoroom professional pipeline."""

import pytest

from apps.media.campaign_visual_brief import CampaignVisualBrief, DEFAULT_SCENE_ROLES
from apps.media.photoroom_brief import (
    merge_brief_into_params,
    prioritize_brief_variants,
    variant_ids_from_brief,
)
from apps.products.photoroom_plus import PLUS_VARIANT_CATALOG


@pytest.mark.django_db
class TestPhotoroomBrief:
    def test_variant_ids_from_brief_electronics(self, user):
        brief = CampaignVisualBrief(
            scenes=list(DEFAULT_SCENE_ROLES),
            business_type="wholesale_retail",
        )
        ids = variant_ids_from_brief(
            brief,
            user=user,
            category="electronics",
            offering="product",
        )
        assert "smart_crop" in ids or "photofix" in ids
        assert "ai_creative_podium" in ids
        assert len(ids) <= 12

    def test_merge_brief_into_params(self):
        params = {"background.prompt": "Table scene", "padding": "0.1"}
        merged = merge_brief_into_params(params, "Premium studio shot of phone")
        assert "Premium studio shot" in merged["background.prompt"]
        assert "Table scene" in merged["background.prompt"]

    def test_prioritize_brief_variants(self):
        specs = [
            PLUS_VARIANT_CATALOG["ai_lifestyle"],
            PLUS_VARIANT_CATALOG["studio_safe"],
            PLUS_VARIANT_CATALOG["relight"],
        ]
        ordered = prioritize_brief_variants(specs, ["relight", "studio_safe"])
        assert ordered[0].id == "relight"
        assert ordered[1].id == "studio_safe"
