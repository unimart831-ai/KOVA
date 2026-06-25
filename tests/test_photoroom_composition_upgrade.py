"""Tests for Photoroom composition, beautifier, and Basic cutout upgrades."""

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from apps.products.photoroom_api import beautify_mode_for_category
from apps.products.photoroom_composition import (
    build_composition_prompt,
    build_market_day_composition_prompt,
    compose_via_native_api,
)
from apps.products.photoroom_plus import PLUS_VARIANT_CATALOG
from apps.products.photoroom_preflight import PhotoQualityReport, build_repair_plan


def _product(name: str):
    p = MagicMock()
    p.name = name
    p.pk = "00000000-0000-0000-0000-000000000001"
    return p


def test_beautify_nocutout_in_catalog():
    spec = PLUS_VARIANT_CATALOG["beautify_nocutout"]
    assert spec.params["removeBackground"] == "false"
    assert spec.params["beautify.mode"] == "{beautify_mode}"


def test_build_composition_prompt_includes_product_names():
    products = [_product("Kitenge dress"), _product("Leather bag")]
    prompt = build_composition_prompt(products, layout="bundle")
    assert "Kitenge dress" in prompt
    assert "Leather bag" in prompt
    assert "bundle" in prompt.lower() or "gift set" in prompt.lower()


def test_market_day_composition_prompt_uses_stall_context():
    prompt = build_market_day_composition_prompt({
        "stall_title": "Mama Grace Mitumba",
        "market_context": "Nairobi CBD",
    })
    assert "Mama Grace" in prompt
    assert "market" in prompt.lower()


@override_settings(PHOTOROOM_BEAUTIFY_NOCUTOUT_ENABLED=True)
def test_repair_plan_includes_beautify_nocutout_for_food():
    report = PhotoQualityReport(lighting="dark", sharpness="soft")
    plan = build_repair_plan(report, plan_tier="kova", category="food")
    assert "beautify_nocutout" in plan


@override_settings(PHOTOROOM_BEAUTIFY_NOCUTOUT_ENABLED=True)
def test_repair_plan_beautify_nocutout_before_smart_crop():
    report = PhotoQualityReport(
        lighting="dark",
        crop="very_tight",
        sharpness="soft",
    )
    plan = build_repair_plan(report, plan_tier="kova", category="beauty", commerce_source="snap")
    assert plan.index("beautify_nocutout") < plan.index("smart_crop")


def test_compose_via_native_api_passes_additional_images():
    with patch("apps.products.photoroom_composition.photoroom_edit") as mock_edit:
        from apps.products.photoroom_api import PhotoroomEditResult

        mock_edit.return_value = PhotoroomEditResult(
            content=b"\xff\xd8\xff" + b"x" * 6000,
            api="v2/edit+composition",
        )
        result = compose_via_native_api(
            ["https://example.com/a.jpg", "https://example.com/b.jpg"],
            prompt="Combine products professionally",
            output_size="1080x1080",
        )
        assert result is not None
        mock_edit.assert_called_once()
        _args, kwargs = mock_edit.call_args
        assert kwargs.get("additional_image_urls") == ["https://example.com/b.jpg"]


def test_beautify_mode_food_and_beauty():
    assert beautify_mode_for_category("food") == "ai.food"
    assert beautify_mode_for_category("beauty") == "ai.auto"


def test_basic_route_includes_studio_brand():
    from apps.products.photoroom_basic import BASIC_ROUTE_VARIANT_IDS

    assert "studio_brand" in BASIC_ROUTE_VARIANT_IDS
