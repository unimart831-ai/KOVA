"""Virtual model routing — wear / hold / adorn across product categories."""

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from apps.products.photoroom_plus import PLUS_VARIANT_CATALOG, resolve_variant_params, select_plus_variants
from apps.products.photoroom_virtual_models import (
    STRATEGY_ADORN,
    STRATEGY_HOLD,
    STRATEGY_WEAR,
    build_catalog_variant_params,
    build_shot_plan,
    catalog_variant_for_strategy,
    resolve_virtual_model_strategy,
    virtual_model_enabled,
)


def _product(name: str, **kwargs):
    p = MagicMock()
    p.name = name
    p.description = kwargs.get("description", "")
    p.tags = kwargs.get("tags", [])
    p.offering_type = kwargs.get("offering_type", "product")
    p.image = kwargs.get("image", MagicMock(url="https://example.com/p.jpg"))
    p.pk = kwargs.get("pk", "00000000-0000-0000-0000-000000000001")
    p.user = kwargs.get("user", MagicMock())
    return p


@pytest.mark.parametrize(
    "name,tags,expected",
    [
        ("Women's kitenge dress", ["fashion"], STRATEGY_WEAR),
        ("Men's leather jacket", [], STRATEGY_WEAR),
        ("Samsung Galaxy A15", ["phone"], STRATEGY_HOLD),
        ("Gold necklace set", ["jewelry"], STRATEGY_ADORN),
        ("Vitamin C serum", ["skincare"], STRATEGY_ADORN),
        ("Wooden serving tray", [], STRATEGY_HOLD),
    ],
)
def test_resolve_virtual_model_strategy(name, tags, expected):
    product = _product(name, tags=tags)
    category = __import__(
        "apps.products.photoroom_plus", fromlist=["detect_product_category"]
    ).detect_product_category(product, {})
    assert resolve_virtual_model_strategy(category, product) == expected


def test_catalog_variant_for_strategy():
    assert catalog_variant_for_strategy(STRATEGY_WEAR) == "virtual_model"
    assert catalog_variant_for_strategy(STRATEGY_HOLD) == "virtual_model_hold"
    assert catalog_variant_for_strategy(STRATEGY_ADORN) == "virtual_model_adorn"


@override_settings(PHOTOROOM_VIRTUAL_MODEL_ENABLED=True, PHOTOROOM_API_KEY="test-key")
def test_virtual_model_enabled_with_key():
    assert virtual_model_enabled() is True


def test_wear_shot_plan_uses_native_virtual_model():
    product = _product("Ladies summer dress", tags=["women"])
    plan = build_shot_plan(product, max_shots=3)
    assert len(plan) == 3
    assert all(s.variant_id == "virtual_model" for s in plan)
    assert all(s.strategy == STRATEGY_WEAR for s in plan)
    assert plan[0].model in ("avery", "ava", "sophia", "maya", "elena", "luna")


def test_hold_shot_plan_for_electronics():
    product = _product("Wireless earbuds", tags=["electronics", "audio"])
    plan = build_shot_plan(product, category="electronics", max_shots=2)
    assert len(plan) == 2
    assert all(s.variant_id == "virtual_model_hold" for s in plan)
    assert all(s.prompt for s in plan)
    assert "earbuds" in plan[0].prompt.lower()


def test_adorn_shot_plan_for_beauty():
    product = _product("Glow serum", tags=["beauty"])
    plan = build_shot_plan(product, category="beauty", max_shots=2)
    assert all(s.variant_id == "virtual_model_adorn" for s in plan)
    assert "beauty campaign" in plan[0].prompt.lower()


def test_build_catalog_variant_params_wear():
    product = _product("Dress")
    params = build_catalog_variant_params("virtual_model", product, {}, layout_index=0)
    assert params["virtualModel.mode"] == "ai.auto"
    assert params["virtualModel.model.preset.name"]
    assert params["virtualModel.pose"]


def test_build_catalog_variant_params_hold():
    product = _product("Phone charger")
    params = build_catalog_variant_params("virtual_model_hold", product, {}, layout_index=0)
    assert params["editWithAI.mode"] == "ai.auto"
    assert "editWithAI.prompt" in params
    assert len(params["editWithAI.prompt"]) > 80


@override_settings(PHOTOROOM_VIRTUAL_MODEL_ENABLED=True)
def test_select_plus_variants_includes_hold_for_electronics():
    product = _product("Bluetooth speaker", tags=["electronics"])
    specs = select_plus_variants(product, {}, plan_tier="kova", max_count=12)
    ids = {s.id for s in specs}
    assert "virtual_model_hold" in ids


@override_settings(PHOTOROOM_VIRTUAL_MODEL_ENABLED=True)
def test_select_plus_variants_includes_adorn_for_jewelry():
    product = _product("Silver ring", tags=["jewelry"])
    specs = select_plus_variants(product, {}, plan_tier="kova", max_count=12)
    ids = {s.id for s in specs}
    assert "virtual_model_adorn" in ids


@override_settings(PHOTOROOM_VIRTUAL_MODEL_ENABLED=True)
def test_select_plus_variants_includes_wear_for_apparel():
    product = _product("Kitenge top", tags=["women", "fashion"])
    specs = select_plus_variants(product, {}, plan_tier="kova", max_count=12)
    ids = {s.id for s in specs}
    assert "virtual_model" in ids


def test_resolve_variant_params_virtual_model_dynamic():
    product = _product("Men's casual shirt", tags=["men", "shirt"])
    spec = PLUS_VARIANT_CATALOG["virtual_model"]
    params = resolve_variant_params(spec, product, {}, {}, layout_index=0)
    assert params["virtualModel.model.preset.name"] == "jackson"
    assert params["virtualModel.scene.preset.name"] == "studio"


def test_new_catalog_entries_exist():
    assert "virtual_model_hold" in PLUS_VARIANT_CATALOG
    assert "virtual_model_adorn" in PLUS_VARIANT_CATALOG
