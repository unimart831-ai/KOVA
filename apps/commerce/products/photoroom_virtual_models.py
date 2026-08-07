"""
Photoroom Virtual Model — category-aware model shots for every product type.

- **wear** (apparel): native ``virtualModel.*`` API — model wearing the garment.
- **hold** (electronics, home, food, general): Edit With AI — model presenting the product.
- **adorn** (jewelry, beauty): Edit With AI — model wearing or applying the product.

See https://docs.photoroom.com/image-editing-api-plus-plan/virtual-model
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

VIRTUAL_MODEL_FOLDER = "virtual_models"
VIRTUAL_MODEL_CATALOG_IDS = frozenset({
    "virtual_model",
    "virtual_model_hold",
    "virtual_model_adorn",
})

STRATEGY_WEAR = "wear"
STRATEGY_HOLD = "hold"
STRATEGY_ADORN = "adorn"

# All 12 Photoroom Virtual Model presets
PHOTOROOM_MODELS_FEMALE = ("avery", "ava", "sophia", "maya", "elena", "luna")
PHOTOROOM_MODELS_MALE = ("jackson", "sam", "jordan", "marcus", "kai", "noah")
PHOTOROOM_MODELS_ALL = PHOTOROOM_MODELS_FEMALE + PHOTOROOM_MODELS_MALE

PHOTOROOM_SCENES = (
    "coloredstudio",
    "studio",
    "street",
    "latincity",
    "businessdistrict",
    "countryside",
    "beach",
    "bedroom",
    "loftapartment",
    "random",
)

PHOTOROOM_POSES = (
    "standing",
    "walkingforward",
    "crossedarms",
    "handinpocket",
    "seated",
    "armsbehindback",
    "leaning",
    "random",
)

# Legacy Kova preset keys → Photoroom API (backward compatible)
MODEL_API_PRESETS: dict[str, dict[str, str]] = {
    "female_confident": {"model": "avery", "pose": "standing"},
    "female_casual": {"model": "ava", "pose": "walkingforward"},
    "female_professional": {"model": "sophia", "pose": "crossedarms"},
    "male_confident": {"model": "jackson", "pose": "standing"},
    "male_casual": {"model": "sam", "pose": "handinpocket"},
    "male_professional": {"model": "jordan", "pose": "crossedarms"},
}

SCENE_API_PRESETS: dict[str, str] = {
    "studio_white": "coloredstudio",
    "studio_gray": "studio",
    "urban_street": "street",
    "market_scene": "latincity",
    "office": "businessdistrict",
    "outdoor_park": "countryside",
    "beach": "beach",
    "bedroom": "bedroom",
}

WEAR_SHOT_ROTATION: tuple[tuple[str, str, str], ...] = (
    ("avery", "street", "standing"),
    ("jackson", "studio", "crossedarms"),
    ("ava", "latincity", "walkingforward"),
    ("sophia", "businessdistrict", "handinpocket"),
    ("maya", "beach", "standing"),
    ("jordan", "coloredstudio", "crossedarms"),
    ("elena", "countryside", "seated"),
    ("marcus", "street", "handinpocket"),
)

HOLD_SCENE_CONTEXTS: tuple[tuple[str, str], ...] = (
    (
        "street",
        "on a vibrant urban street with soft natural daylight, authentic East African city commerce energy",
    ),
    (
        "studio",
        "in a clean modern studio with soft key light and minimal backdrop, premium e-commerce campaign style",
    ),
    (
        "market",
        "at a lively open-air market stall with warm ambient light, approachable seller-presenter vibe",
    ),
    (
        "home",
        "in a tasteful contemporary living space with natural window light, lifestyle advertising quality",
    ),
)

ADORN_SCENE_CONTEXTS: tuple[tuple[str, str], ...] = (
    (
        "studio_portrait",
        "tight beauty portrait with soft diffused studio light, elegant and aspirational",
    ),
    (
        "vanity",
        "at a marble vanity or spa counter with warm flattering light, premium beauty campaign",
    ),
    (
        "outdoor",
        "outdoors in golden-hour light with shallow depth of field, editorial fashion mood",
    ),
)


@dataclass(frozen=True)
class VirtualModelShot:
    variant_id: str
    model: str
    scene: str
    pose: str
    layout_index: int
    label: str
    strategy: str
    prompt: str = ""
    seed: int = 0


def virtual_model_enabled() -> bool:
    if not getattr(settings, "PHOTOROOM_VIRTUAL_MODEL_ENABLED", False):
        return False
    return bool(getattr(settings, "PHOTOROOM_API_KEY", ""))


def resolve_virtual_model_strategy(
    category: str,
    product=None,
    analysis: dict | None = None,
) -> str:
    """Pick wear / hold / adorn from detected product category."""
    from apps.commerce.products.photoroom_plus import detect_product_category

    cat = (category or "").strip().lower()
    if not cat and product is not None:
        cat = detect_product_category(product, analysis)
    if cat in ("apparel", "apparel_mitumba"):
        return STRATEGY_WEAR
    if cat in ("jewelry", "beauty"):
        return STRATEGY_ADORN
    return STRATEGY_HOLD


def catalog_variant_for_strategy(strategy: str) -> str:
    return {
        STRATEGY_WEAR: "virtual_model",
        STRATEGY_HOLD: "virtual_model_hold",
        STRATEGY_ADORN: "virtual_model_adorn",
    }.get(strategy, "virtual_model_hold")


def _detect_gender_target(product, analysis: dict | None = None) -> str:
    """Infer female / male / neutral audience from product copy."""
    parts = [
        getattr(product, "name", "") or "",
        getattr(product, "description", "") or "",
        " ".join(getattr(product, "tags", None) or []),
    ]
    if analysis:
        parts.extend([
            analysis.get("description") or "",
            analysis.get("visual_style") or "",
            analysis.get("target_audience") or "",
        ])
    text = " ".join(parts).lower()

    female_keywords = {
        "women", "woman", "ladies", "female", "dress", "skirt", "bra", "blouse",
        "gown", "her", "girl", "feminine", "lipstick", "mascara", "necklace",
    }
    male_keywords = {
        "men", "man", "male", "shirt", "trouser", "suit", "boxer", "his", "boy",
        "masculine", "cologne",
    }
    female_score = sum(1 for k in female_keywords if k in text)
    male_score = sum(1 for k in male_keywords if k in text)
    if female_score > male_score:
        return "female"
    if male_score > female_score:
        return "male"
    return "female"


def _clean_product_name(product) -> str:
    from apps.commerce.products.commerce_autopilot import sanitize_product_name

    return sanitize_product_name(getattr(product, "name", "") or "") or "the product"


def _hold_interaction(category: str) -> str:
    interactions = {
        "electronics": (
            "confidently holding it in both hands at chest height, angled to show key features "
            "and screen or branding clearly"
        ),
        "home": (
            "presenting it naturally in a styled interior — holding or placing it as the hero prop"
        ),
        "food": (
            "presenting it on a serving tray or offering it toward the camera with inviting warmth"
        ),
        "general": "holding it confidently toward the camera with natural, authentic posture",
    }
    return interactions.get(category, interactions["general"])


def _adorn_interaction(category: str) -> str:
    if category == "jewelry":
        return (
            "wearing the jewelry piece elegantly — close portrait showing it on the appropriate "
            "body area (neck, wrist, ears, or finger) without obscuring the product design"
        )
    return (
        "in a beauty campaign pose — holding or lightly applying the product near face or hands "
        "while keeping packaging and product details sharp and accurate"
    )


def build_hold_prompt(
    product,
    analysis: dict | None,
    *,
    scene_key: str,
    scene_description: str,
    category: str = "general",
) -> str:
    """Edit With AI prompt — model presenting a non-wearable product."""
    from apps.commerce.products.photoroom_plus import EDIT_WITH_AI_PRODUCT_STAGING_BASE

    name = _clean_product_name(product)
    interaction = _hold_interaction(category)
    return (
        f"{EDIT_WITH_AI_PRODUCT_STAGING_BASE} "
        f"Feature a natural, professional model {interaction}. "
        f"The product is {name}. Setting: {scene_description}. "
        f"The product must remain the unmistakable hero — fully visible, sharp, true colors, "
        f"no duplicates, no text overlays, no watermarks."
    )


def build_adorn_prompt(
    product,
    analysis: dict | None,
    *,
    scene_description: str,
    category: str = "beauty",
) -> str:
    """Edit With AI prompt — model wearing jewelry or using beauty product."""
    from apps.commerce.products.photoroom_plus import EDIT_WITH_AI_PRODUCT_STAGING_BASE

    name = _clean_product_name(product)
    interaction = _adorn_interaction(category)
    return (
        f"{EDIT_WITH_AI_PRODUCT_STAGING_BASE} "
        f"Feature an aspirational model {interaction}. "
        f"The product is {name}. Setting: {scene_description}. "
        f"Macro-level clarity on the product — accurate materials, color, and branding. "
        f"No text, logos added in post, or extra competing products."
    )


def build_shot_plan(
    product,
    analysis: dict | None = None,
    *,
    category: str | None = None,
    max_shots: int | None = None,
) -> list[VirtualModelShot]:
    """Ordered virtual-model shots tailored to product category."""
    from apps.commerce.products.photoroom_plus import detect_product_category

    cat = (category or detect_product_category(product, analysis)).lower()
    strategy = resolve_virtual_model_strategy(cat, product, analysis)
    variant_id = catalog_variant_for_strategy(strategy)
    gender = _detect_gender_target(product, analysis)
    cap = max_shots or int(getattr(settings, "PHOTOROOM_VIRTUAL_MODEL_PACK_SHOTS", 3))
    cap = max(1, min(cap, 6))

    shots: list[VirtualModelShot] = []
    base_seed = int(getattr(settings, "EDIT_WITH_AI_SEED_DEFAULT", 2016886668))

    if strategy == STRATEGY_WEAR:
        rotation = list(WEAR_SHOT_ROTATION)
        if gender == "male":
            rotation = [
                t for t in rotation if t[0] in PHOTOROOM_MODELS_MALE
            ] + [t for t in rotation if t[0] not in PHOTOROOM_MODELS_MALE]
        else:
            rotation = [
                t for t in rotation if t[0] in PHOTOROOM_MODELS_FEMALE
            ] + [t for t in rotation if t[0] not in PHOTOROOM_MODELS_FEMALE]
        for idx, (model, scene, pose) in enumerate(rotation[:cap]):
            shots.append(VirtualModelShot(
                variant_id=variant_id,
                model=model,
                scene=scene,
                pose=pose,
                layout_index=idx,
                label=f"Virtual model — {model} ({scene})",
                strategy=strategy,
                seed=base_seed + idx * 17,
            ))
        return shots

    if strategy == STRATEGY_ADORN:
        contexts = ADORN_SCENE_CONTEXTS
        models = PHOTOROOM_MODELS_FEMALE if gender != "male" else PHOTOROOM_MODELS_MALE
        for idx, (scene_key, scene_desc) in enumerate(contexts[:cap]):
            prompt = build_adorn_prompt(
                product, analysis, scene_description=scene_desc, category=cat,
            )
            shots.append(VirtualModelShot(
                variant_id=variant_id,
                model=models[idx % len(models)],
                scene=scene_key,
                pose="standing",
                layout_index=idx,
                label=f"Model wearing — {scene_key.replace('_', ' ')}",
                strategy=strategy,
                prompt=prompt,
                seed=base_seed + idx * 23,
            ))
        return shots

    # hold
    contexts = HOLD_SCENE_CONTEXTS
    models = (
        PHOTOROOM_MODELS_FEMALE + PHOTOROOM_MODELS_MALE
        if gender == "female"
        else PHOTOROOM_MODELS_MALE + PHOTOROOM_MODELS_FEMALE
    )
    for idx, (scene_key, scene_desc) in enumerate(contexts[:cap]):
        prompt = build_hold_prompt(
            product,
            analysis,
            scene_key=scene_key,
            scene_description=scene_desc,
            category=cat,
        )
        shots.append(VirtualModelShot(
            variant_id=variant_id,
            model=models[idx % len(models)],
            scene=scene_key,
            pose="standing",
            layout_index=idx,
            label=f"Model presenting — {scene_key}",
            strategy=strategy,
            prompt=prompt,
            seed=base_seed + idx * 31,
        ))
    return shots


def shot_for_layout(
    product,
    analysis: dict | None,
    variant_id: str,
    layout_index: int = 0,
    *,
    category: str | None = None,
) -> VirtualModelShot:
    """Resolve the shot plan entry for a catalog variant + layout index."""
    plan = build_shot_plan(product, analysis, category=category, max_shots=6)
    matching = [s for s in plan if s.variant_id == variant_id]
    if matching:
        return matching[layout_index % len(matching)]
    if plan:
        return plan[layout_index % len(plan)]
    return VirtualModelShot(
        variant_id=variant_id,
        model="avery",
        scene="street",
        pose="standing",
        layout_index=layout_index,
        label="Virtual model",
        strategy=STRATEGY_WEAR,
    )


def build_virtual_model_params(
    model_preset: str = "female_confident",
    scene: str = "studio_white",
    output_size: str = "1080x1350",
    *,
    model: str | None = None,
    pose: str | None = None,
    scene_api: str | None = None,
) -> dict[str, str]:
    """Build doc-aligned virtualModel.* form params."""
    if model and pose and scene_api:
        api_model, api_pose, scene_name = model, pose, scene_api
    else:
        api_preset = MODEL_API_PRESETS.get(
            model_preset, MODEL_API_PRESETS["female_confident"],
        )
        api_model = api_preset["model"]
        api_pose = api_preset["pose"]
        scene_name = SCENE_API_PRESETS.get(scene, scene)
        if scene_name not in SCENE_API_PRESETS.values():
            scene_name = "random"

    return {
        "removeBackground": "false",
        "referenceBox": "originalImage",
        "virtualModel.mode": "ai.auto",
        "virtualModel.model.preset.name": api_model,
        "virtualModel.scene.preset.name": scene_name,
        "virtualModel.pose": api_pose,
        "virtualModel.size": "SQUARE_HD",
        "outputSize": output_size,
        "export.format": "png",
    }


def build_wear_params_for_shot(shot: VirtualModelShot, output_size: str | None = None) -> dict[str, str]:
    size = output_size or str(getattr(settings, "PHOTOROOM_OUTPUT_SIZE", "1080x1350"))
    return build_virtual_model_params(
        model=shot.model,
        pose=shot.pose,
        scene_api=shot.scene,
        output_size=size,
    )


def build_edit_with_ai_model_params(shot: VirtualModelShot) -> dict[str, str]:
    from apps.commerce.products.photoroom_plus import _export_defaults

    return {
        "removeBackground": "false",
        "referenceBox": "originalImage",
        "editWithAI.mode": "ai.auto",
        "editWithAI.prompt": shot.prompt,
        "editWithAI.seed": str(shot.seed),
        **_export_defaults(),
    }


def build_catalog_variant_params(
    variant_id: str,
    product,
    analysis: dict | None,
    layout_index: int = 0,
) -> dict[str, str]:
    """Full Photoroom params for a virtual-model catalog variant."""
    from apps.commerce.products.photoroom_plus import detect_product_category

    category = detect_product_category(product, analysis)
    shot = shot_for_layout(product, analysis, variant_id, layout_index, category=category)
    if shot.strategy == STRATEGY_WEAR:
        return build_wear_params_for_shot(shot)
    return build_edit_with_ai_model_params(shot)


def _product_image_url(product) -> str | None:
    if not product.image:
        return None
    try:
        return product.image.url
    except Exception:
        return None


def _save_virtual_model_bytes(image_bytes: bytes) -> str:
    ext = "jpg" if image_bytes[:3] == b"\xff\xd8\xff" else "png"
    filename = f"{VIRTUAL_MODEL_FOLDER}/{uuid.uuid4().hex}.{ext}"
    return default_storage.save(filename, ContentFile(image_bytes))


def generate_virtual_model_shot(
    garment_image_url: str,
    model_preset: str = "female_confident",
    scene: str = "studio_white",
    output_size: str = "1080x1350",
    *,
    shot: VirtualModelShot | None = None,
) -> str | None:
    """Generate one virtual-model image; returns storage path or None."""
    from apps.commerce.products.photoroom_plus import photoroom_edit

    if shot and shot.strategy == STRATEGY_WEAR:
        params = build_wear_params_for_shot(shot, output_size)
    elif shot:
        params = build_edit_with_ai_model_params(shot)
    else:
        params = build_virtual_model_params(
            model_preset=model_preset,
            scene=scene,
            output_size=output_size,
        )

    try:
        result = photoroom_edit(garment_image_url, params)
        if not result.ok or not result.content or len(result.content) < 5000:
            if result.sandbox_limited:
                logger.warning("Virtual model skipped: %s", result.error)
            return None

        filename = f"{VIRTUAL_MODEL_FOLDER}/{uuid.uuid4().hex}.png"
        saved_path = default_storage.save(filename, ContentFile(result.content))
        logger.info(
            "Virtual model image saved: %s (uncertainty=%s)",
            saved_path,
            result.uncertainty_score,
        )
        return saved_path

    except requests.Timeout:
        logger.error("Photoroom Virtual Model timed out")
        return None
    except Exception:
        logger.exception("Photoroom Virtual Model unexpected error")
        return None


def _record_pack_action(product, paths: list[str], shots: list[VirtualModelShot]) -> None:
    try:
        from apps.create.agents.models import AgentAction

        AgentAction.objects.create(
            user=product.user,
            agent_type="create",
            action_type="commerce.virtual_model",
            description=f"Generated {len(paths)} virtual model shots for {product.name}",
            status=AgentAction.ActionStatus.COMPLETED,
            input_data={"product_id": str(product.pk)},
            output_data={
                "paths": paths,
                "credits_used": len(paths),
                "strategies": list({s.strategy for s in shots}),
            },
        )
    except Exception:
        pass


def generate_virtual_model_pack(
    product,
    analysis: dict | None = None,
    brand_colors: dict | None = None,
    *,
    garment_image_url: str | None = None,
    max_shots: int | None = None,
    save_to_product: bool = False,
    check_credits: bool = True,
    record_polish: bool = True,
    brand_template=None,
) -> list[str]:
    """
    Generate a category-aware virtual model pack (wear / hold / adorn).

    Returns public URLs when ``save_to_product`` uses studio polish paths, else storage paths.
    """
    if not virtual_model_enabled():
        return []

    source_url = garment_image_url or _product_image_url(product)
    if not source_url:
        return []

    from apps.core.billing.visual_credits import check_visual_credit_limit, record_studio_polish
    from apps.commerce.products.photoroom import save_studio_polish_image
    from apps.commerce.products.photoroom_plus import PLUS_VARIANT_CATALOG, run_plus_variant
    from apps.commerce.products.photoroom_review import review_flags_for_output

    plan = build_shot_plan(product, analysis, max_shots=max_shots)
    if not plan:
        return []

    results: list[str] = []
    for shot in plan:
        if check_credits:
            ok, _ = check_visual_credit_limit(product.user)
            if not ok:
                break

        spec = PLUS_VARIANT_CATALOG.get(shot.variant_id)
        if not spec:
            continue

        try:
            edit_result = run_plus_variant(
                source_url,
                spec,
                product,
                analysis,
                brand_colors,
                brand_template=brand_template,
                layout_index=shot.layout_index,
            )
        except Exception as exc:
            logger.warning("Virtual model pack shot failed (%s): %s", shot.variant_id, exc)
            continue

        if not edit_result or not edit_result.ok or not edit_result.content:
            continue

        suffix = f"{shot.variant_id}_{shot.layout_index + 1}"
        try:
            if save_to_product:
                url = save_studio_polish_image(product.pk, edit_result.content, suffix=suffix)
            else:
                path = _save_virtual_model_bytes(edit_result.content)
                from apps.create.content.tasks import _public_url_for_file
                url = _public_url_for_file(path)
        except Exception as exc:
            logger.error("Virtual model save failed: %s", exc)
            continue

        if record_polish:
            record_studio_polish(
                product.user,
                product_id=product.pk,
                provider="photoroom_plus",
                output_data={
                    "variant": shot.variant_id,
                    "label": shot.label,
                    "url": url,
                    "uncertainty_score": edit_result.uncertainty_score,
                    "phase": "virtual_model",
                    "slide_role": "proof",
                    "virtual_model_strategy": shot.strategy,
                    "api": edit_result.api if edit_result else "v2/edit",
                    **review_flags_for_output(
                        shot.variant_id,
                        uncertainty_score=edit_result.uncertainty_score,
                    ),
                },
            )
        results.append(url)

    if results:
        _record_pack_action(product, results, plan[: len(results)])

    return results


def generate_fashion_pack(product, garment_image_url: str | None = None) -> list[str]:
    """Backward-compatible alias — apparel-focused pack, returns storage paths."""
    if not virtual_model_enabled():
        return []

    urls = generate_virtual_model_pack(
        product,
        garment_image_url=garment_image_url,
        save_to_product=False,
        check_credits=True,
        record_polish=True,
    )
    # Legacy callers expect storage paths; convert URLs back when possible
    paths: list[str] = []
    for item in urls:
        if item.startswith("http"):
            paths.append(item.split("/media/", 1)[-1] if "/media/" in item else item)
        else:
            paths.append(item)
    return paths


def append_virtual_model_pack(
    product,
    source_url: str,
    analysis: dict | None,
    brand_colors: dict | None,
    *,
    brand_template=None,
    credit_budget: int = 3,
    product_category: str | None = None,
) -> tuple[list[str], list[str], int]:
    """
    Pipeline hook — append virtual model URLs during studio polish.

    Returns (urls, variant_ids, credits_used).
    """
    if not virtual_model_enabled():
        return [], [], 0
    if credit_budget <= 0:
        return [], [], 0

    max_shots = min(
        credit_budget,
        int(getattr(settings, "PHOTOROOM_VIRTUAL_MODEL_PACK_SHOTS", 3)),
    )
    urls = generate_virtual_model_pack(
        product,
        analysis=analysis,
        brand_colors=brand_colors,
        garment_image_url=source_url,
        max_shots=max_shots,
        save_to_product=True,
        check_credits=True,
        record_polish=True,
        brand_template=brand_template,
    )
    if not urls:
        return [], [], 0

    from apps.commerce.products.photoroom_plus import detect_product_category

    cat = product_category or detect_product_category(product, analysis)
    strategy = resolve_virtual_model_strategy(cat, product, analysis)
    variant_id = catalog_variant_for_strategy(strategy)
    return urls, [variant_id] * len(urls), len(urls)
