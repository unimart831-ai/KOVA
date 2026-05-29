"""
Photoroom Virtual Model API — generates AI model photos wearing garments.

Uses documented v2/edit preset fields:
virtualModel.model.preset.name, virtualModel.scene.preset.name, virtualModel.pose
"""
from __future__ import annotations

import logging
import uuid

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

VIRTUAL_MODEL_FOLDER = "virtual_models"

# Kova preset keys → Photoroom API preset names (see Virtual Model docs)
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


def virtual_model_enabled() -> bool:
    """Check if virtual model generation is available."""
    if not getattr(settings, "PHOTOROOM_VIRTUAL_MODEL_ENABLED", False):
        return False
    return bool(getattr(settings, "PHOTOROOM_API_KEY", ""))


def build_virtual_model_params(
    model_preset: str = "female_confident",
    scene: str = "studio_white",
    output_size: str = "1080x1350",
) -> dict[str, str]:
    """Build doc-aligned virtualModel.* form params."""
    api_model = MODEL_API_PRESETS.get(
        model_preset, MODEL_API_PRESETS["female_confident"],
    )
    scene_name = SCENE_API_PRESETS.get(scene, scene)
    if scene_name not in SCENE_API_PRESETS.values():
        scene_name = "random"

    return {
        "removeBackground": "false",
        "referenceBox": "originalImage",
        "virtualModel.mode": "ai.auto",
        "virtualModel.model.preset.name": api_model["model"],
        "virtualModel.scene.preset.name": scene_name,
        "virtualModel.pose": api_model["pose"],
        "virtualModel.size": "SQUARE_HD",
        "outputSize": output_size,
        "export.format": "png",
    }


def generate_virtual_model_shot(
    garment_image_url: str,
    model_preset: str = "female_confident",
    scene: str = "studio_white",
    output_size: str = "1080x1350",
) -> str | None:
    """
    Generate a virtual model wearing a garment.

    Returns storage path to the saved image, or None on failure.
    """
    from apps.products.photoroom_plus import photoroom_edit

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


def generate_fashion_pack(product, garment_image_url: str = None) -> list[str]:
    """
    Generate a full fashion photography pack for a product:
    - 2 model shots (different poses)
    - 1 lifestyle scene

    Returns list of saved image paths.
    """
    if not virtual_model_enabled():
        return []

    if not garment_image_url:
        if product.image:
            try:
                garment_image_url = product.image.url
            except Exception:
                return []
        else:
            return []

    results = []
    gender = _detect_garment_gender(product)

    shot_configs = [
        (f"{gender}_confident", "street"),
        (f"{gender}_casual", "urban_street"),
        (f"{gender}_professional", "office"),
    ]

    for model_preset, scene in shot_configs:
        if model_preset not in MODEL_API_PRESETS:
            model_preset = f"{gender}_confident"

        path = generate_virtual_model_shot(
            garment_image_url=garment_image_url,
            model_preset=model_preset,
            scene=scene,
        )
        if path:
            results.append(path)

    if results:
        try:
            from apps.agents.models import AgentAction

            AgentAction.objects.create(
                user=product.user,
                agent_type="create",
                action_type="commerce.virtual_model",
                description=f"Generated {len(results)} virtual model shots for {product.name}",
                status=AgentAction.ActionStatus.COMPLETED,
                input_data={"product_id": str(product.pk)},
                output_data={"paths": results, "credits_used": len(results)},
            )
        except Exception:
            pass

    return results


def _detect_garment_gender(product) -> str:
    """Detect likely gender target from product name/description/tags."""
    text = f"{product.name} {product.description or ''} {' '.join(product.tags or [])}".lower()

    female_keywords = {"women", "woman", "ladies", "female", "dress", "skirt", "bra", "blouse", "gown"}
    male_keywords = {"men", "man", "male", "shirt", "trouser", "suit", "boxer"}

    female_score = sum(1 for k in female_keywords if k in text)
    male_score = sum(1 for k in male_keywords if k in text)

    if female_score > male_score:
        return "female"
    if male_score > female_score:
        return "male"
    return "female"
