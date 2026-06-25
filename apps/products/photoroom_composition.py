"""
Photoroom Photo Composition — multi-product hero images via Edit With AI + reference images.

Native path: v2/edit with editWithAI.additionalImages.* (up to 4 extra products + main).
Fallback: per-product cutouts → local grid → optional AI polish.

See https://www.photoroom.com/api/composition
"""

from __future__ import annotations

import logging
import uuid
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from apps.products.photoroom import save_studio_polish_image
from apps.products.photoroom_plus import EDIT_WITH_AI_PRODUCT_STAGING_BASE, photoroom_edit

logger = logging.getLogger(__name__)

COMPOSITION_FOLDER = "composition_heroes"
MAX_PRODUCTS = 8
MAX_NATIVE_REFERENCES = 5  # 1 main + 4 additional per Photoroom docs


def composition_enabled() -> bool:
    if not getattr(settings, "PHOTOROOM_COMPOSITION_ENABLED", True):
        return False
    return bool(getattr(settings, "PHOTOROOM_API_KEY", ""))


def native_composition_enabled() -> bool:
    return composition_enabled() and bool(
        getattr(settings, "PHOTOROOM_COMPOSITION_NATIVE", True),
    )


def _pick_product_image_url(product) -> str | None:
    """Prefer studio-polished hero; fall back to primary or first extra."""
    polished = [
        u for u in (product.additional_images or [])
        if u
        and "studio_polish" in u
        and "promo_frame" not in u
        and "channel_" not in u
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


def _product_names_blob(products) -> str:
    from apps.products.commerce_autopilot import sanitize_product_name

    names = [
        sanitize_product_name(getattr(p, "name", "") or "item")
        for p in products[:MAX_PRODUCTS]
    ]
    names = [n for n in names if n]
    if not names:
        return "these products"
    if len(names) <= 3:
        return ", ".join(names)
    return f"{', '.join(names[:3])} and {len(names) - 3} more items"


def build_composition_prompt(
    products,
    *,
    custom_prompt: str = "",
    layout: str = "collection",
    brand_name: str = "",
    stall_context: dict | None = None,
) -> str:
    """
    Edit With AI prompt for multi-product composition.

    layout: collection | bundle | market_day | catalog
    """
    if custom_prompt.strip():
        return custom_prompt.strip()

    names = _product_names_blob(products)
    brand = (brand_name or "").strip()
    brand_bit = f" for {brand}" if brand else ""

    layout_prompts = {
        "bundle": (
            f"Combine all provided product images into one premium e-commerce bundle hero{brand_bit}. "
            f"Products: {names}. Arrange them as a cohesive gift set or kit on a clean studio surface "
            f"with matched soft shadows, natural light, and balanced spacing. Each product must stay "
            f"sharp, color-accurate, and fully recognizable. No text, watermarks, or duplicate items."
        ),
        "market_day": (
            f"Create a vibrant market-day stall hero photograph combining all provided products{brand_bit}. "
            f"Products: {names}. Arrange them invitingly on a clean branded surface with warm natural "
            f"light and cohesive shadows — authentic East African market energy, professional advertising quality."
        ),
        "catalog": (
            f"Create a catalog collection hero image combining all provided products{brand_bit}. "
            f"Products: {names}. Editorial e-commerce layout on a minimal studio backdrop, even spacing, "
            f"soft diffused light, each item clearly visible and color-true."
        ),
        "collection": (
            f"Create a single professional marketing photograph that combines all provided product images "
            f"into one cohesive hero scene{brand_bit}. Products: {names}. Use AI composition to position "
            f"each item with realistic scale, unified lighting, soft shadows, and a clean lifestyle or "
            f"studio backdrop. Every product must remain the clear focal subject — sharp, unobstructed, "
            f"accurate colors. No added text or logos."
        ),
    }

    prompt = layout_prompts.get(layout, layout_prompts["collection"])

    ctx = stall_context or {}
    if ctx.get("stall_title"):
        prompt += f" Stall: {ctx['stall_title'][:80]}."
    if ctx.get("market_context"):
        prompt += f" Setting hint: {str(ctx['market_context'])[:100]}."

    return f"{EDIT_WITH_AI_PRODUCT_STAGING_BASE} {prompt}"


def build_catalog_composition_prompt(products, *, brand_name: str = "") -> str:
    return build_composition_prompt(
        products,
        layout="catalog",
        brand_name=brand_name,
    )


def build_market_day_composition_prompt(stall_context: dict | None = None) -> str:
    """Backward-compatible alias used by batch Snap."""
    ctx = stall_context or {}
    return build_composition_prompt(
        [],
        custom_prompt="",
        layout="market_day",
        brand_name=ctx.get("stall_title") or "",
        stall_context=ctx,
    )


def compose_via_native_api(
    image_urls: list[str],
    *,
    prompt: str,
    output_size: str,
    seed: int | None = None,
) -> bytes | None:
    """
    Photoroom native multi-reference composition via Edit With AI.

    Main image = first URL; up to 4 additional reference images.
    """
    if len(image_urls) < 2:
        return None

    main_url = image_urls[0]
    additional = image_urls[1:MAX_NATIVE_REFERENCES]

    seed_val = seed or int(getattr(settings, "EDIT_WITH_AI_SEED_DEFAULT", 2016886668))

    params = {
        "removeBackground": "false",
        "referenceBox": "originalImage",
        "editWithAI.mode": "ai.auto",
        "editWithAI.prompt": prompt,
        "editWithAI.seed": str(seed_val),
        "outputSize": output_size,
        "padding": "0.08",
        "shadow.mode": "ai.soft",
        "export.format": "jpeg",
    }

    result = photoroom_edit(
        main_url,
        params,
        additional_image_urls=additional,
    )
    if result.ok and result.content and len(result.content) >= 5000:
        logger.info(
            "Native composition OK (%d refs, api=%s, uncertainty=%s)",
            len(additional) + 1,
            result.api,
            result.uncertainty_score,
        )
        return result.content

    logger.warning(
        "Native composition failed (%s) — will use grid fallback",
        result.error or "empty_output",
    )
    return None


def _cutout_product_bytes(image_url: str, *, output_size: str) -> bytes | None:
    """Single-product cutout on white for grid fallback."""
    params = {
        "removeBackground": "true",
        "background.color": "FFFFFF",
        "outputSize": output_size,
        "padding": "0.08",
        "shadow.mode": "ai.soft",
        "export.format": "png",
        "referenceBox": "originalImage",
    }
    result = photoroom_edit(image_url, params)
    return result.content if result.ok else None


def _compose_grid_local(
    cutouts: list[bytes],
    *,
    width: int,
    height: int,
    bg_rgb: tuple[int, int, int],
) -> bytes | None:
    """Arrange cutouts on canvas when native multi-reference compose is unavailable."""
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
    """AI polish pass on grid composite."""
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


def _compose_grid_fallback(
    image_urls: list[str],
    *,
    prompt: str,
    output_size: str,
    bg_rgb: tuple[int, int, int],
) -> bytes | None:
    w, h = 1080, 1920
    try:
        w, h = [int(x) for x in output_size.split("x")]
    except ValueError:
        pass

    cutout_size = "800x800"
    cutouts: list[bytes] = []
    for url in image_urls:
        cut = _cutout_product_bytes(url, output_size=cutout_size)
        if cut:
            cutouts.append(cut)

    if len(cutouts) < 2:
        return None

    composite = _compose_grid_local(cutouts, width=w, height=h, bg_rgb=bg_rgb)
    if not composite:
        return None

    return _polish_composite(composite, prompt=prompt, output_size=output_size) or composite


def compose_product_hero(
    products,
    *,
    prompt: str = "",
    output_size: str | None = None,
    user=None,
    brand_template=None,
    layout: str = "collection",
    record_credits: bool = True,
) -> str | None:
    """
    Build a multi-product hero image URL for batch showcase / catalog / bundles.

    Tries native Edit With AI multi-reference first, then grid fallback.
    """
    if not composition_enabled():
        return None

    output_size = output_size or getattr(settings, "PHOTOROOM_STORY_SIZE", "1080x1920")

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

    profile = getattr(profile_user, "profile", None) if profile_user else None
    brand_name = (getattr(profile, "company_name", None) or "").strip()

    if brand_template and brand_template.enabled:
        primary = brand_template.studio_color_hex.lstrip("#")
    else:
        from apps.agents.graphics import _get_brand_palette

        brand = _get_brand_palette(profile)
        primary = brand.get("primary", "#F8F6F3").lstrip("#")
    try:
        bg_rgb = tuple(int(primary[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        bg_rgb = (248, 246, 243)

    scene_prompt = build_composition_prompt(
        products,
        custom_prompt=prompt,
        layout=layout,
        brand_name=brand_name,
    )

    final_bytes: bytes | None = None
    method = "none"

    if native_composition_enabled():
        final_bytes = compose_via_native_api(
            image_urls,
            prompt=scene_prompt,
            output_size=output_size,
        )
        if final_bytes:
            method = "native"

    if not final_bytes:
        final_bytes = _compose_grid_fallback(
            image_urls,
            prompt=scene_prompt,
            output_size=output_size,
            bg_rgb=bg_rgb,
        )
        if final_bytes:
            method = "grid_fallback"

    if not final_bytes:
        return None

    owner_id = products[0].pk if products else uuid.uuid4()
    hero_url = save_studio_polish_image(owner_id, final_bytes, suffix="composition_hero")

    if record_credits and profile_user:
        try:
            from apps.billing.visual_credits import record_studio_polish

            record_studio_polish(
                profile_user,
                product_id=str(owner_id),
                provider="photoroom_plus",
                output_data={
                    "variant": "composition_hero",
                    "label": "Multi-product composition",
                    "url": hero_url,
                    "phase": "composition",
                    "composition_method": method,
                    "product_count": len(image_urls),
                    "slide_role": "hero",
                },
            )
        except Exception:
            pass

    logger.info(
        "Composition hero saved: %s (%d products, method=%s)",
        hero_url,
        len(image_urls),
        method,
    )
    return hero_url


def compose_catalog_showcase_hero(products, *, user=None, brand_name: str = "") -> str | None:
    """Square composition hero for catalog carousel cover slide."""
    return compose_product_hero(
        products,
        output_size=getattr(settings, "PHOTOROOM_OUTPUT_SIZE", "1080x1080"),
        user=user,
        layout="catalog",
        prompt=build_catalog_composition_prompt(products, brand_name=brand_name),
    )


def save_composition_hero_for_session(session_id, hero_url: str) -> str:
    """Persist hero reference on batch session folder for debugging/reuse."""
    filename = f"{COMPOSITION_FOLDER}/{session_id}/hero_{uuid.uuid4().hex[:10]}.txt"
    default_storage.save(filename, ContentFile(hero_url.encode("utf-8")))
    return hero_url
