"""
Photoroom Virtual Model API — generates AI model photos wearing garments.
Eliminates need for photography studio for fashion/apparel SMEs.

Uses Photoroom v2/edit with virtual model parameters.
"""
from __future__ import annotations

import logging
import uuid
from io import BytesIO

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

PHOTOROOM_EDIT_URL = "https://image-api.photoroom.com/v2/edit"
VIRTUAL_MODEL_FOLDER = "virtual_models"

MODEL_PRESETS = {
    "female_confident": {
        "gender": "female",
        "pose": "confident_standing",
        "description": "Confident African woman, urban style",
    },
    "female_casual": {
        "gender": "female",
        "pose": "casual_walking",
        "description": "Casual relaxed pose, everyday style",
    },
    "female_professional": {
        "gender": "female",
        "pose": "professional_standing",
        "description": "Professional business setting",
    },
    "male_confident": {
        "gender": "male",
        "pose": "confident_standing",
        "description": "Confident African man, urban style",
    },
    "male_casual": {
        "gender": "male",
        "pose": "casual_standing",
        "description": "Casual relaxed pose, everyday style",
    },
    "male_professional": {
        "gender": "male",
        "pose": "professional_standing",
        "description": "Professional business setting",
    },
}

SCENE_PRESETS = {
    "studio_white": "Clean white studio background",
    "studio_gray": "Neutral gray studio background",
    "urban_street": "Urban African street scene",
    "market_scene": "Vibrant African market setting",
    "office": "Modern office environment",
    "outdoor_park": "Natural outdoor park setting",
}


def virtual_model_enabled() -> bool:
    """Check if virtual model generation is available."""
    if not getattr(settings, "PHOTOROOM_VIRTUAL_MODEL_ENABLED", False):
        return False
    return bool(getattr(settings, "PHOTOROOM_API_KEY", ""))


def generate_virtual_model_shot(
    garment_image_url: str,
    model_preset: str = "female_confident",
    scene: str = "studio_white",
    output_size: str = "1080x1350",
) -> str | None:
    """
    Generate a virtual model wearing a garment.

    Args:
        garment_image_url: URL of the flat-lay garment photo
        model_preset: Key from MODEL_PRESETS
        scene: Key from SCENE_PRESETS or custom description
        output_size: Output dimensions (WxH)

    Returns:
        Storage path to the saved image, or None on failure.
    """
    from apps.products.photoroom_plus import photoroom_edit

    preset = MODEL_PRESETS.get(model_preset, MODEL_PRESETS["female_confident"])
    scene_desc = SCENE_PRESETS.get(scene, scene)

    params = {
        "removeBackground": "false",
        "referenceBox": "originalImage",
        "virtualModel.mode": "ai.auto",
        "virtualModel.prompt": f"{preset['description']}, {scene_desc}",
        "virtualModel.size": "SQUARE_HD",
        "outputSize": output_size,
        "padding": "0.05",
        "shadow.mode": "ai.soft",
        "export.format": "png",
    }

    try:
        image_bytes = photoroom_edit(garment_image_url, params)
        if not image_bytes or len(image_bytes) < 5000:
            return None

        filename = f"{VIRTUAL_MODEL_FOLDER}/{uuid.uuid4().hex}.png"
        saved_path = default_storage.save(filename, ContentFile(image_bytes))
        logger.info("Virtual model image saved: %s", saved_path)
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
        (f"{gender}_confident", "studio_white"),
        (f"{gender}_casual", "urban_street"),
        (f"{gender}_professional", "office"),
    ]

    for model_preset, scene in shot_configs:
        if model_preset not in MODEL_PRESETS:
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
