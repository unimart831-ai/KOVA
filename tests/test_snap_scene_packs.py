"""Tests for Snap scene packs, credit estimator, and multi-angle gate."""

from apps.products.photoroom_plus import (
    multi_angle_polish_credit_enabled,
    select_plus_variants,
)
from apps.products.photoroom_preflight import PhotoQualityReport, build_repair_plan
from apps.products.scene_packs import (
    SCENE_PACK_FASHION_FLAT,
    SCENE_PACK_FOOD_DELIVERY,
    SCENE_PACK_MARKETPLACE_WHITE,
    normalize_scene_pack,
    scene_pack_export_budget,
    store_product_scene_pack,
)
from apps.products.snap_pipeline import estimate_polish_credits


class _Product:
    def __init__(self, name="Test", tags=None, offering_type="product", marketplace_metadata=None):
        self.name = name
        self.tags = tags or []
        self.offering_type = offering_type
        self.marketplace_metadata = marketplace_metadata or {}


def test_normalize_scene_pack_defaults_invalid():
    assert normalize_scene_pack(None) == "auto"
    assert normalize_scene_pack("unknown") == "auto"
    assert normalize_scene_pack("food_delivery") == "food_delivery"


def test_store_product_scene_pack_on_metadata():
    product = _Product()
    store_product_scene_pack(product, "brand_studio")
    assert product.marketplace_metadata["scene_pack"] == "brand_studio"
    store_product_scene_pack(product, "auto")
    assert product.marketplace_metadata.get("scene_pack") == "brand_studio"


def test_select_plus_variants_food_delivery_pack():
    p = _Product(name="Jollof Rice", tags=["food"])
    specs = select_plus_variants(
        p,
        {},
        plan_tier="growth",
        max_count=6,
        scene_pack=SCENE_PACK_FOOD_DELIVERY,
    )
    ids = [s.id for s in specs]
    assert ids[0] in {
        "food_surface_marble",
        "food_surface_rustic",
        "food_surface_delivery",
    }
    assert any(vid.startswith("food_surface_") for vid in ids)


def test_select_plus_variants_marketplace_white_pack():
    p = _Product(name="USB Cable", tags=["electronics"])
    specs = select_plus_variants(
        p,
        {},
        plan_tier="growth",
        max_count=4,
        scene_pack=SCENE_PACK_MARKETPLACE_WHITE,
    )
    assert specs[0].id == "studio_white"


def test_select_plus_variants_fashion_flat_pack_starter():
    p = _Product(name="Summer Dress", tags=["fashion"])
    specs = select_plus_variants(
        p,
        {},
        plan_tier="starter",
        max_count=5,
        scene_pack=SCENE_PACK_FASHION_FLAT,
    )
    ids = [s.id for s in specs]
    assert ids[0] == "flat_lay"
    assert "ghost_mannequin" not in ids


def test_select_plus_variants_fashion_flat_pack_pro():
    p = _Product(name="Summer Dress", tags=["fashion"])
    specs = select_plus_variants(
        p,
        {},
        plan_tier="pro",
        max_count=6,
        scene_pack=SCENE_PACK_FASHION_FLAT,
    )
    ids = [s.id for s in specs]
    assert ids[0] == "flat_lay"
    assert "ghost_mannequin" in ids


def test_scene_pack_marketplace_white_export_budget():
    story, marketplace = scene_pack_export_budget(SCENE_PACK_MARKETPLACE_WHITE, "growth")
    assert story == 0
    assert marketplace == 2


def test_estimate_polish_credits_snap_repair_breakdown():
    class _User:
        profile = None

    est = estimate_polish_credits(
        _User(),
        scene_pack="auto",
        plan_tier="starter",
        photo_count=1,
        commerce_source="snap",
    )
    report = PhotoQualityReport(crop="comfortable")
    expected_repairs = min(
        len(build_repair_plan(report, plan_tier="starter", commerce_source="snap")),
        2,
    )
    assert est["repairs"] == expected_repairs
    assert est["total"] >= est["repairs"] + est["scenes"]
    assert "credits:" in est["breakdown_label"]


def test_estimate_polish_credits_includes_multi_angle_for_growth():
    class _User:
        profile = None

    single = estimate_polish_credits(
        _User(),
        plan_tier="growth",
        photo_count=1,
    )
    multi = estimate_polish_credits(
        _User(),
        plan_tier="growth",
        photo_count=2,
    )
    assert single["multi_angle"] == 0
    assert multi["multi_angle"] == 1
    assert multi["total"] == single["total"] + 1


def test_multi_angle_polish_credit_enabled_gate():
    assert multi_angle_polish_credit_enabled("starter") is False
    assert multi_angle_polish_credit_enabled("growth") is True
    assert multi_angle_polish_credit_enabled("pro") is True


def test_resolve_scene_vertical_mitumba_from_stall_brief():
    from apps.products.scene_packs import resolve_scene_vertical

    p = _Product(name="Blue Shirt", tags=["fashion"])
    vertical = resolve_scene_vertical(
        p,
        {"product_category": "women's fashion"},
        stall_context={"category_hint": "mitumba bale"},
    )
    assert vertical == "apparel_mitumba"


def test_jewelry_vertical_auto_pack_via_vision_category():
    p = _Product(name="Bracelet", tags=[])
    specs = select_plus_variants(
        p,
        {"product_category": "jewelry"},
        plan_tier="growth",
        max_count=5,
    )
    ids = [s.id for s in specs]
    assert ids[0] == "studio_dark"
    assert "ai_creative_marble" in ids
