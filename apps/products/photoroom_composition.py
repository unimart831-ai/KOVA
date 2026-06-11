"""
Photoroom Photo Composition — multi-product hero images for batch showcase / bundles.

Uses v2/edit (AI scene on a composed layout) with a local Pillow fallback when the API
cannot accept multiple inputs. See https://www.photoroom.com/api/composition
"""

from __future__ import annotations

import logging
import uuid
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from apps.agents.graphics import _get_brand_palette
from apps.products.photoroom import save_studio_polish_image
from apps.products.photoroom_plus import photoroom_edit

logger = logging.getLogger(__name__)

COMPOSITION_FOLDER = "composition_heroes"
MAX_PRODUCTS = 8


def composition_enabled() -> bool:
    if not getattr(settings, "PHOTOROOM_COMPOSITION_ENABLED", True):
        return False
    return bool(getattr(settings, "PHOTOROOM_API_KEY", ""))


def _pick_product_image_url(product) -> str | None:
    polished = [
        u for u in (product.additional_images or [])
        if u and "studio_polish" in u and "promo_frame" not in u
    ]
    if polished:
        return polished[0]
    if product.image:
        try:
            return product.image.url
        except Exception:
            pass
    extra = product.additional_images or []
    return extra[0] if extra else None


def _cutout_product_bytes(image_url: str, *, output_size: str) -> bytes | None:
    """Single-product cutout on white for grid composition."""
    params = {
        "removeBackground": "true",
        "background.color": "FFFFFF",
        "outputSize": output_size,
        "padding": "0.08",
        "shadow.mode": "ai.soft",
        "export.format": "jpeg",
        "referenceBox": "originalImage",
    }
    result = photoroom_edit(image_url, params)
    return result.content if result.ok else None


def _compose_grid_local(cutouts: list[bytes], *, width: int, height: int, bg_rgb: tuple[int, int, int]) -> bytes | None:
    """Arrange cutouts on a story canvas (fallback when multi-upload API is unavailable)."""
    from PIL import Image

    if not cutouts:
        return None

    canvas = Image.new("RGB", (width, height), bg_rgb)
    n = len(cutouts)
    cols = 2 if n <= 4 else 3
    rows = (n + cols - 1) // cols
    margin = int(width * 0.04)
    cell_w = (width - margin * (cols + 1)) // cols
    cell_h = (height - margin * (rows + 1)) // rows

    for idx, raw in enumerate(cutouts):
        try:
            img = Image.open(BytesIO(raw)).convert("RGBA")
        except Exception:
            continue
        img.thumbnail((cell_w, cell_h), Image.Resampling.LANCZOS)
        col = idx % cols
        row = idx // cols
        x = margin + col * (cell_w + margin) + (cell_w - img.width) // 2
        y = margin + row * (cell_h + margin) + (cell_h - img.height) // 2
        canvas.paste(img, (x, y), img)

    buf = BytesIO()
    canvas.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def _polish_composite(composite_bytes: bytes, *, prompt: str, output_size: str) -> bytes | None:
    """Optional AI pass — unified lighting/background on the grid composite."""
    filename = f"composite_{uuid.uuid4().hex[:8]}.jpg"
    params = {
        "removeBackground": "false",
        "background.prompt": prompt,
        "outputSize": output_size,
        "padding": "0.06",
        "shadow.mode": "ai.soft",
        "export.format": "jpeg",
        "referenceBox": "originalImage",
    }
    from apps.products.photoroom_plus import AI_BG_MODEL_HEADER

    headers = {"pr-ai-background-model-version": AI_BG_MODEL_HEADER}
    result = photoroom_edit(
        "",
        params,
        extra_headers=headers,
        file_bytes=composite_bytes,
        file_name=filename,
    )
    return result.content if result.ok else None


def compose_product_hero(
    products,
    *,
    prompt: str = "",
    output_size: str | None = None,
    user=None,
    brand_template=None,
) -> str | None:
    """
    Build a multi-product hero image URL for batch showcase reels / collection posts.

    Returns a public URL to the saved hero, or None.
    """
    if not composition_enabled():
        return None

    output_size = output_size or getattr(settings, "PHOTOROOM_STORY_SIZE", "1080x1920")
    try:
        w, h = [int(x) for x in output_size.split("x")]
    except ValueError:
        w, h = 1080, 1920

    image_urls: list[str] = []
    for product in products[:MAX_PRODUCTS]:
        url = _pick_product_image_url(product)
        if url:
            image_urls.append(url)
    if len(image_urls) < 2:
        return None

    profile_user = user or (products[0].user if products else None)
    if brand_template is None and profile_user:
        from apps.products.photoroom_brand_template import build_photoroom_brand_template

        brand_template = build_photoroom_brand_template(
            getattr(profile_user, "profile", None),
            profile_user.pk,
        )

    if brand_template and brand_template.enabled:
        primary = brand_template.studio_color_hex.lstrip("#")
    else:
        brand = _get_brand_palette(getattr(profile_user, "profile", None) if profile_user else None)
        primary = brand.get("primary", "#F8F6F3").lstrip("#")
    try:
        bg_rgb = tuple(int(primary[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        bg_rgb = (248, 246, 243)

    scene_prompt = prompt or (
        "Professional e-commerce hero photograph showing multiple products arranged evenly "
        "on a clean studio surface with soft natural lighting and cohesive shadows, "
        "market stall collection showcase"
    )

    cutout_size = "800x800"
    cutouts: list[bytes] = []
    for url in image_urls:
        cut = _cutout_product_bytes(url, output_size=cutout_size)
        if cut:
            cutouts.append(cut)

    if len(cutouts) < 2:
        logger.warning("Composition: fewer than 2 cutouts succeeded")
        return None

    composite = _compose_grid_local(cutouts, width=w, height=h, bg_rgb=bg_rgb)
    if not composite:
        return None

    polished = _polish_composite(composite, prompt=scene_prompt, output_size=output_size)
    final_bytes = polished or composite

    owner_id = products[0].pk if products else uuid.uuid4()
    hero_url = save_studio_polish_image(owner_id, final_bytes, suffix="batch_hero")
    logger.info("Composition hero saved: %s (%d products)", hero_url, len(cutouts))
    return hero_url


def save_composition_hero_for_session(session_id, hero_url: str) -> str:
    """Persist hero reference on batch session folder for debugging/reuse."""
    filename = f"{COMPOSITION_FOLDER}/{session_id}/hero_{uuid.uuid4().hex[:10]}.txt"
    default_storage.save(filename, ContentFile(hero_url.encode("utf-8")))
    return hero_url
