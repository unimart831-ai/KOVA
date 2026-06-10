"""
Restaurant / food delivery preset pack — locked AI surface prompts + beautify.

See docs/KOVA_PHOTOROOM_STRATEGY.md Phase 2.
"""

from __future__ import annotations

# Locked seeds — reproducible food surfaces (do not rotate per Snap).
FOOD_SURFACE_SEEDS: dict[str, int] = {
    "food_surface_marble": 117879368,
    "food_surface_rustic": 55994449,
    "food_surface_delivery": 48672244,
}

FOOD_SURFACE_VARIANT_IDS: tuple[str, ...] = (
    "food_surface_marble",
    "food_surface_rustic",
    "food_surface_delivery",
)

FOOD_COMMERCE_SOURCES = frozenset({"snap", "batch_snap", "snap_to_sell"})


def build_food_surface_prompt(variant_id: str, product, analysis: dict | None) -> str:
    """Locked delivery-app-style surfaces for restaurant / food vendors."""
    from apps.products.photoroom_plus import _clean_name, _commerce_prompt

    name = _clean_name(product)
    analysis = analysis or {}
    angle = analysis.get("campaign_angle") or analysis.get("visual_style") or ""
    mood = f" Mood: {angle}." if angle else ""

    prompts = {
        "food_surface_marble": (
            f"{name} on a clean white marble counter with soft warm side light, "
            f"subtle reflection beneath the dish, premium food-delivery hero photography, "
            f"minimal props kept small and out of the way"
        ),
        "food_surface_rustic": (
            f"{name} on a rustic wooden table with warm natural daylight, "
            f"simple complementary ingredients arranged neatly at the edges, "
            f"authentic home-style food photography"
        ),
        "food_surface_delivery": (
            f"{name} on a warm neutral branded delivery surface with soft even studio light, "
            f"clean modern food-app listing aesthetic, appetizing and fresh, "
            f"uncluttered background"
        ),
    }
    base = prompts.get(variant_id, prompts["food_surface_delivery"])
    return _commerce_prompt(f"{base}.{mood}")


def food_preset_active_for(commerce_source: str | None) -> bool:
    """Food preset pack applies in Snap and Batch Snap flows."""
    return (commerce_source or "") in FOOD_COMMERCE_SOURCES


def should_boost_food_beautify(category: str, commerce_source: str | None) -> bool:
    return category == "food" and food_preset_active_for(commerce_source)
