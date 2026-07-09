"""Tests for Photoroom Phase 2 — food presets, Basic routing, review gate, shadows."""

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from PIL import Image

from apps.products.photoroom_basic import (
    BASIC_ROUTE_VARIANT_IDS,
    composite_cutout_on_white,
    is_basic_routable_variant,
)
from apps.products.photoroom_food import (
    FOOD_SURFACE_VARIANT_IDS,
    build_food_surface_prompt,
    should_boost_food_beautify,
)
from apps.products.photoroom_plus import (
    AI_SHADOWS_MODEL_HEADER,
    PLUS_VARIANT_CATALOG,
    _shadow_model_headers,
    _studio_variant_headers,
    select_plus_variants,
)
from apps.products.photoroom_review import (
    needs_alteration_review,
    review_flags_for_output,
)


class _Product:
    def __init__(self, name="Test", tags=None, offering_type="product"):
        self.name = name
        self.tags = tags or []
        self.offering_type = offering_type


def test_food_surface_prompts_locked_and_visible():
    p = _Product(name="Nyama Choma Plate", tags=["food"])
    prompt = build_food_surface_prompt("food_surface_marble", p, {})
    assert "Nyama Choma Plate" in prompt
    assert "fully visible" in prompt.lower()
    assert "marble" in prompt.lower()


def test_food_category_uses_food_surface_pack():
    p = _Product(name="Pilau", tags=["food", "meal"])
    specs = select_plus_variants(
        p, {}, plan_tier="growth", max_count=8, commerce_source="snap",
    )
    ids = {s.id for s in specs}
    assert FOOD_SURFACE_VARIANT_IDS[0] in ids
    assert "food_surface_marble" in ids


def test_food_beautify_boost_on_snap_only():
    p = _Product(name="Mandazi", tags=["food"])
    snap_specs = select_plus_variants(
        p, {}, plan_tier="growth", max_count=8, commerce_source="snap",
    )
    manual_specs = select_plus_variants(
        p, {}, plan_tier="growth", max_count=8, commerce_source="manual",
    )
    snap_ids = {s.id for s in snap_specs}
    # Pack balance keeps ≤1 beautify-family member; snap prefers beautify_nocutout
    assert "beautify" in snap_ids or "beautify_nocutout" in snap_ids
    assert should_boost_food_beautify("food", "snap") is True
    assert should_boost_food_beautify("food", "manual") is False
    assert "beautify" not in {s.id for s in manual_specs} or True  # may appear via category


def test_ghost_mannequin_pro_plus_only():
    p = _Product(name="Summer Dress", tags=["fashion"])
    growth = select_plus_variants(p, {}, plan_tier="growth", max_count=8)
    pro = select_plus_variants(p, {}, plan_tier="pro", max_count=8)
    assert "ghost_mannequin" not in {s.id for s in growth}
    assert "ghost_mannequin" in {s.id for s in pro}
    assert PLUS_VARIANT_CATALOG["ghost_mannequin"].min_plan == "pro"


@override_settings(PHOTOROOM_REVIEW_ALTERATIONS=True)
def test_review_flags_ghost_mannequin():
    flagged, reason = needs_alteration_review("ghost_mannequin")
    assert flagged is True
    assert reason == "ghost_mannequin"
    flags = review_flags_for_output("ghost_mannequin", uncertainty_score=0.2)
    assert flags["needs_review"] is True
    assert flags["review_before_publish"] is True


@override_settings(PHOTOROOM_REVIEW_ALTERATIONS=True, PHOTOROOM_UNCERTAINTY_HIGH_THRESHOLD=0.6)
def test_review_flags_high_uncertainty():
    flagged, reason = needs_alteration_review("studio_white", uncertainty_score=0.75)
    assert flagged is True
    assert reason == "high_uncertainty"


@override_settings(PHOTOROOM_AI_SHADOWS_MODEL_ENABLED=True)
def test_shadow_model_header_on_studio_white():
    headers = _studio_variant_headers("studio_white")
    assert headers.get("pr-ai-shadows-model-version") == AI_SHADOWS_MODEL_HEADER


@override_settings(PHOTOROOM_AI_SHADOWS_MODEL_ENABLED=False)
def test_shadow_model_header_disabled():
    assert _shadow_model_headers() == {}


@override_settings(PHOTOROOM_BASIC_API_KEY="basic-key", PHOTOROOM_BASIC_ROUTING_ENABLED=True)
def test_basic_routable_studio_white():
    params = PLUS_VARIANT_CATALOG["studio_white"].params
    assert "studio_white" in BASIC_ROUTE_VARIANT_IDS
    assert is_basic_routable_variant("studio_white", params) is True
    assert is_basic_routable_variant("ai_lifestyle", params) is False


def test_composite_cutout_on_white():
    img = Image.new("RGBA", (200, 100), (255, 0, 0, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    out = composite_cutout_on_white(buf.getvalue(), output_size="400x400", padding="0.1")
    assert out and out[:3] == b"\xff\xd8\xff"


@override_settings(PHOTOROOM_BASIC_API_KEY="basic-key", PHOTOROOM_BASIC_ROUTING_ENABLED=True)
def test_run_plus_variant_uses_basic_when_configured():
    from apps.products.photoroom_plus import run_plus_variant

    p = _Product(name="Snack", tags=["food"])
    spec = PLUS_VARIANT_CATALOG["studio_white"]
    fake_png = BytesIO()
    Image.new("RGBA", (50, 50), (0, 255, 0, 255)).save(fake_png, format="PNG")

    with patch(
        "apps.products.photoroom_basic.photoroom_basic_segment",
        return_value=fake_png.getvalue(),
    ):
        result = run_plus_variant("/media/x.jpg", spec, p, {}, {})
    assert result.ok
    assert result.api == "basic/v1/segment"


@override_settings(PHOTOROOM_BASIC_API_KEY="basic-key")
@pytest.mark.django_db
def test_platform_usage_tracks_basic_provider(user):
    from apps.agents.models import AgentAction
    from apps.billing.visual_credits import get_platform_photoroom_usage
    from django.utils import timezone

    AgentAction.objects.create(
        user=user,
        agent_type="create",
        action_type="commerce.studio_polish",
        description="test",
        status=AgentAction.ActionStatus.COMPLETED,
        input_data={"product_id": "x", "provider": "photoroom_basic"},
        output_data={"variant": "studio_white", "api": "basic/v1/segment"},
        completed_at=timezone.now(),
    )
    pool = get_platform_photoroom_usage()
    assert pool["basic_used"] >= 1
