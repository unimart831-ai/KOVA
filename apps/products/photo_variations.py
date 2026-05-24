"""
Zero-cost product photo expansion — one upload → multiple scene versions.

Uses local rembg (CPU) to cut out the product, then Pillow presets for
backgrounds, shadows, and promo layouts. No paid image APIs.
"""

from __future__ import annotations

import logging
import textwrap
import uuid
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageDraw, ImageFilter

from apps.agents.carousel import _load_product_image
from apps.agents.graphics import _draw_gradient, _get_brand_palette, _get_font, _hex_to_rgb
from apps.products.commerce_autopilot import sanitize_product_name
from apps.products.image_utils import apply_exif_orientation

logger = logging.getLogger(__name__)

CANVAS_SIZE = (1080, 1080)
JPEG_QUALITY = 92
VARIATION_FOLDER = "product_variations"

PRESET_WHITE_STUDIO = "white_studio"
PRESET_GRAY_STUDIO = "gray_studio"
PRESET_BRAND_GRADIENT = "brand_gradient"
PRESET_SOFT_PASTEL = "soft_pastel"
PRESET_DARK_PREMIUM = "dark_premium"
PRESET_PROMO_FRAME = "promo_frame"

VISUAL_MODE_AS_IS = "as_is"
VISUAL_MODE_QUICK_POLISH = "quick_polish"
VISUAL_MODE_PRO_SCENE = "pro_scene"  # DB value — UI label: Studio polish
VISUAL_MODE_STUDIO_POLISH = "studio_polish"  # alias

PRESET_STUDIO_HERO = "studio_hero"
STUDIO_POLISH_MODES = frozenset({VISUAL_MODE_PRO_SCENE, VISUAL_MODE_STUDIO_POLISH})


def is_studio_polish_mode(mode: str | None) -> bool:
    return mode in STUDIO_POLISH_MODES


def variation_storage_marker(product_id) -> str:
    return f"{VARIATION_FOLDER}/{product_id}/"


def select_presets(product, analysis: dict | None = None) -> list[str]:
    """Pick four presets — rules + optional vision hints, no extra LLM cost."""
    tags_text = " ".join(product.tags or []).lower()
    name = (product.name or "").lower()
    blob = f"{name} {tags_text}"
    beauty_words = (
        "lotion", "cream", "beauty", "skin", "cosmetic", "serum",
        "oil", "balm", "soap", "shampoo", "perfume",
    )

    if any(w in blob for w in beauty_words):
        return [
            PRESET_WHITE_STUDIO,
            PRESET_SOFT_PASTEL,
            PRESET_DARK_PREMIUM,
            PRESET_PROMO_FRAME,
        ]

    visual_style = (analysis or {}).get("visual_style", "").lower()
    if any(w in visual_style for w in ("luxury", "premium", "dark", "gold")):
        return [
            PRESET_WHITE_STUDIO,
            PRESET_DARK_PREMIUM,
            PRESET_BRAND_GRADIENT,
            PRESET_PROMO_FRAME,
        ]

    return [
        PRESET_WHITE_STUDIO,
        PRESET_GRAY_STUDIO,
        PRESET_BRAND_GRADIENT,
        PRESET_PROMO_FRAME,
    ]


def _dominant_hex_colors(rgb_image: Image.Image, count: int = 2) -> list[str]:
    """Extract dominant colors as #RRGGBB strings."""
    sample = rgb_image.copy()
    sample.thumbnail((160, 160))
    if sample.mode != "RGB":
        sample = sample.convert("RGB")
    try:
        quantized = sample.quantize(colors=max(count, 2), method=Image.Quantize.MEDIANCUT)
        palette = quantized.getpalette() or []
        hex_colors: list[str] = []
        for i in range(count):
            idx = i * 3
            if idx + 2 >= len(palette):
                break
            r, g, b = palette[idx], palette[idx + 1], palette[idx + 2]
            hex_colors.append(f"#{r:02x}{g:02x}{b:02x}")
        if hex_colors:
            return hex_colors
    except Exception as exc:
        logger.debug("Color quantize failed: %s", exc)
    return ["#4a90d9", "#1a1a2e"]


def _trim_transparent(image: Image.Image) -> Image.Image:
    if image.mode != "RGBA":
        return image
    bbox = image.getbbox()
    return image.crop(bbox) if bbox else image


def remove_product_background(rgb_image: Image.Image) -> Image.Image:
    """Cut out product with rembg; fall back to opaque full frame."""
    rgb_image = apply_exif_orientation(rgb_image.convert("RGB"))
    buf = BytesIO()
    rgb_image.save(buf, format="JPEG", quality=95)
    raw = buf.getvalue()

    try:
        from rembg import remove

        cutout = remove(raw)
        fg = Image.open(BytesIO(cutout)).convert("RGBA")
        if fg.getbbox():
            return _trim_transparent(fg)
    except Exception as exc:
        logger.warning("rembg unavailable or failed (%s) — using letterboxed photo", exc)

    rgba = rgb_image.convert("RGBA")
    w, h = rgba.size
    inset = int(min(w, h) * 0.06)
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        [(inset, inset), (w - inset, h - inset)],
        radius=int(min(w, h) * 0.04),
        fill=255,
    )
    rgba.putalpha(mask)
    return rgba


def _scale_foreground(foreground: Image.Image, max_w: int, max_h: int) -> Image.Image:
    fg = _trim_transparent(foreground)
    ratio = min(max_w / max(fg.width, 1), max_h / max(fg.height, 1))
    new_size = (max(int(fg.width * ratio), 1), max(int(fg.height * ratio), 1))
    return fg.resize(new_size, Image.Resampling.LANCZOS)


def _make_shadow_layer(foreground: Image.Image, blur: int = 16, opacity: float = 0.32) -> Image.Image:
    alpha = foreground.split()[3]
    shadow = Image.new("RGBA", foreground.size, (0, 0, 0, 0))
    shadow.putalpha(alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    r, g, b, a = shadow.split()
    a = a.point(lambda p: int(p * opacity))
    shadow = Image.merge("RGBA", (r, g, b, a))
    return shadow


def _solid_background(width: int, height: int, color: str) -> Image.Image:
    img = Image.new("RGB", (width, height), _hex_to_rgb(color))
    return img


def _gradient_background(width: int, height: int, top: str, bottom: str) -> Image.Image:
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    _draw_gradient(draw, width, height, top, bottom)
    return img


def _paste_product_centered(
    canvas: Image.Image,
    foreground: Image.Image,
    *,
    scale: float = 1.0,
    shadow: bool = True,
) -> Image.Image:
    """Composite cutout onto canvas with safe margins and drop shadow."""
    width, height = canvas.size
    margin_x = int(width * 0.10)
    margin_top = int(height * 0.08)
    margin_bottom = int(height * 0.12)
    max_w = int((width - margin_x * 2) * scale)
    max_h = int((height - margin_top - margin_bottom) * scale)
    fg = _scale_foreground(foreground, max_w, max_h)

    base = canvas.convert("RGBA")
    x = (width - fg.width) // 2
    y = margin_top + max((height - margin_top - margin_bottom - fg.height) // 2, 0)

    if shadow:
        sh = _make_shadow_layer(fg)
        base.paste(sh, (x, y + 12), sh)

    base.paste(fg, (x, y), fg)
    return base.convert("RGB")


def _render_promo_frame(
    canvas: Image.Image,
    foreground: Image.Image,
    *,
    product_name: str,
    display_price: str,
    shop_hint: str,
    colors: dict,
) -> Image.Image:
    width, height = CANVAS_SIZE
    bg = _gradient_background(width, height, colors["primary"], colors["secondary"])
    margin_x = int(width * 0.06)
    margin_top = int(height * 0.10)
    margin_bottom = int(height * 0.10)
    max_w = int(width * 0.42)
    max_h = height - margin_top - margin_bottom
    fg = _scale_foreground(foreground, max_w, max_h)

    base = bg.convert("RGBA")
    x = margin_x
    y = margin_top + max((height - margin_top - margin_bottom - fg.height) // 2, 0)
    sh = _make_shadow_layer(fg, blur=14, opacity=0.28)
    base.paste(sh, (x, y + 8), sh)
    base.paste(fg, (x, y), fg)

    img = base.convert("RGB")
    draw = ImageDraw.Draw(img)
    text_x = int(width * 0.54)
    text_w = width - text_x - int(width * 0.06)

    title_size = int(height * 0.062)
    font_title = _get_font(title_size, bold=True)
    wrapped_name = textwrap.fill(product_name[:80], width=14)
    draw.multiline_text(
        (text_x, int(height * 0.22)),
        wrapped_name,
        font=font_title,
        fill=_hex_to_rgb(colors["text"]),
        spacing=int(title_size * 0.25),
    )

    if display_price:
        price_size = int(height * 0.085)
        font_price = _get_font(price_size, bold=True)
        draw.text(
            (text_x, int(height * 0.48)),
            display_price,
            font=font_price,
            fill=_hex_to_rgb(colors["accent"]),
        )

    if shop_hint:
        hint_size = int(height * 0.028)
        font_hint = _get_font(hint_size)
        wrapped_hint = textwrap.fill(shop_hint[:120], width=28)
        draw.multiline_text(
            (text_x, int(height * 0.62)),
            wrapped_hint,
            font=font_hint,
            fill=_hex_to_rgb(colors.get("text_muted", "#B0B0B0")),
            spacing=int(hint_size * 0.35),
        )

    draw.rounded_rectangle(
        [(int(width * 0.04), int(height * 0.04)), (width - int(width * 0.04), height - int(height * 0.04))],
        radius=24,
        outline=_hex_to_rgb(colors["accent"]),
        width=3,
    )
    return img


def _render_preset(
    preset_id: str,
    foreground: Image.Image,
    source_rgb: Image.Image,
    *,
    product_name: str,
    display_price: str,
    shop_hint: str,
    dominant_colors: list[str],
    brand_colors: dict,
) -> Image.Image:
    width, height = CANVAS_SIZE

    if preset_id == PRESET_WHITE_STUDIO:
        bg = _solid_background(width, height, "#FFFFFF")
        return _paste_product_centered(bg, foreground, scale=0.92)

    if preset_id == PRESET_GRAY_STUDIO:
        bg = _solid_background(width, height, "#E8EAED")
        return _paste_product_centered(bg, foreground, scale=0.90)

    if preset_id == PRESET_BRAND_GRADIENT:
        top, bottom = dominant_colors[0], dominant_colors[-1] if len(dominant_colors) > 1 else "#1a1a2e"
        bg = _gradient_background(width, height, top, bottom)
        return _paste_product_centered(bg, foreground, scale=0.88)

    if preset_id == PRESET_SOFT_PASTEL:
        top = dominant_colors[0] if dominant_colors else "#dceefb"
        bg = _gradient_background(width, height, top, "#f7f9fc")
        return _paste_product_centered(bg, foreground, scale=0.90)

    if preset_id == PRESET_DARK_PREMIUM:
        bg = _gradient_background(width, height, "#0f0f14", "#2a2a38")
        return _paste_product_centered(bg, foreground, scale=0.86)

    if preset_id == PRESET_PROMO_FRAME:
        bg = _solid_background(width, height, brand_colors["primary"])
        return _render_promo_frame(
            bg,
            foreground,
            product_name=product_name,
            display_price=display_price,
            shop_hint=shop_hint,
            colors=brand_colors,
        )

    bg = _solid_background(width, height, "#FFFFFF")
    return _paste_product_centered(bg, foreground, scale=0.75)


def _save_variation_jpeg(product_id, preset_id: str, image: Image.Image) -> str:
    from apps.content.tasks import _public_url_for_file

    buf = BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    filename = f"{variation_storage_marker(product_id)}{preset_id}_{uuid.uuid4().hex[:8]}.jpg"
    saved_name = default_storage.save(filename, ContentFile(buf.getvalue()))
    return _public_url_for_file(saved_name)


def _strip_generated_variations(additional_images: list, product_id) -> list:
    marker = variation_storage_marker(product_id)
    studio_marker = f"studio_polish/{product_id}/"
    return [
        url for url in (additional_images or [])
        if marker not in url and studio_marker not in url
    ]


def expand_product_photos(product, analysis: dict | None = None, mode: str | None = None) -> dict:
    """
    Generate scene variations from the product's primary photo.
    Appends URLs to product.additional_images (replaces prior auto-variations).

    mode: as_is | quick_polish | pro_scene / studio_polish (defaults to product.visual_mode)
    """
    mode = mode or getattr(product, "visual_mode", None) or VISUAL_MODE_QUICK_POLISH

    if mode == VISUAL_MODE_AS_IS:
        return {"skipped": True, "reason": "as_is", "variations_created": 0}

    if is_studio_polish_mode(mode):
        return _expand_studio_polish(product, analysis)

    return _expand_quick_polish(product, analysis)


def _expand_studio_polish(product, analysis: dict | None = None) -> dict:
    """One Photoroom Basic call (1 credit) + free local Pillow variants."""
    from apps.billing.visual_credits import check_visual_credit_limit, record_studio_polish
    from apps.products.photoroom import (
        photoroom_enabled,
        pick_background_color_hex,
        save_studio_polish_image,
        studio_polish_via_photoroom,
    )

    if not getattr(settings, "PHOTO_VARIATIONS_ENABLED", True):
        return {"skipped": True, "reason": "disabled"}

    if not product.image:
        return {"error": "no_image", "variations_created": 0}

    allowed, msg = check_visual_credit_limit(product.user)
    if not allowed:
        logger.info("Studio polish cap reached for %s — falling back to quick polish", product.user_id)
        result = _expand_quick_polish(product, analysis)
        result["fallback"] = "quick_polish"
        result["limit_message"] = msg
        return result

    if not photoroom_enabled():
        logger.info("Studio polish unavailable — PHOTOROOM_API_KEY missing; using quick polish")
        result = _expand_quick_polish(product, analysis)
        result["fallback"] = "quick_polish"
        result["reason"] = "photoroom_not_configured"
        return result

    source = product.image.url if hasattr(product.image, "url") else str(product.image)
    profile = getattr(product.user, "profile", None)
    brand_colors = _get_brand_palette(profile)
    background_hex = pick_background_color_hex(product, brand_colors)

    image_bytes = studio_polish_via_photoroom(source, background_color=background_hex)

    if not image_bytes:
        result = _expand_quick_polish(product, analysis)
        result["fallback"] = "quick_polish"
        result["reason"] = "photoroom_failed"
        return result

    try:
        hero_url = save_studio_polish_image(product.pk, image_bytes, suffix="hero")
    except Exception as exc:
        logger.error("Studio polish save failed: %s", exc)
        result = _expand_quick_polish(product, analysis)
        result["fallback"] = "quick_polish"
        result["reason"] = "save_failed"
        return result

    record_studio_polish(
        product.user,
        product_id=product.pk,
        provider="photoroom",
        output_data={"background_color": background_hex, "url": hero_url},
    )

    rgb = _load_product_image(source)
    new_urls = [hero_url]
    if rgb is not None:
        dominant = _dominant_hex_colors(rgb)
        foreground = remove_product_background(rgb)
        display_name = sanitize_product_name(product.name) or "Product"
        shop_hint = "Shop link in bio" if product.product_url else ""
        for preset_id in (PRESET_WHITE_STUDIO, PRESET_DARK_PREMIUM, PRESET_PROMO_FRAME):
            try:
                rendered = _render_preset(
                    preset_id,
                    foreground,
                    rgb,
                    product_name=display_name,
                    display_price=product.display_price or "",
                    shop_hint=shop_hint,
                    dominant_colors=dominant,
                    brand_colors=brand_colors,
                )
                new_urls.append(_save_variation_jpeg(product.pk, preset_id, rendered))
            except Exception as exc:
                logger.debug("Studio polish bonus preset %s failed: %s", preset_id, exc)

    kept = _strip_generated_variations(product.additional_images, product.pk)
    product.additional_images = kept + new_urls
    product.save(update_fields=["additional_images", "updated_at"])

    logger.info("Studio polish: product=%s urls=%d bg=%s", product.pk, len(new_urls), background_hex)
    return {
        "variations_created": len(new_urls),
        "mode": VISUAL_MODE_PRO_SCENE,
        "provider": "photoroom",
        "urls": new_urls,
        "background_color": background_hex,
    }


def _expand_quick_polish(product, analysis: dict | None = None) -> dict:
    """Generate scene variations from the product's primary photo (local rembg + Pillow)."""
    if not getattr(settings, "PHOTO_VARIATIONS_ENABLED", True):
        return {"skipped": True, "reason": "disabled"}

    if not product.image:
        return {"error": "no_image", "variations_created": 0}

    source = product.image.url if hasattr(product.image, "url") else str(product.image)
    rgb = _load_product_image(source)
    if rgb is None:
        return {"error": "load_failed", "variations_created": 0}

    profile = getattr(product.user, "profile", None)
    brand_colors = _get_brand_palette(profile)
    dominant = _dominant_hex_colors(rgb)

    foreground = remove_product_background(rgb)
    presets = select_presets(product, analysis)
    display_name = sanitize_product_name(product.name) or "Product"

    shop_hint = ""
    if product.product_url:
        shop_hint = "Shop link in bio"

    new_urls: list[str] = []
    for preset_id in presets:
        try:
            rendered = _render_preset(
                preset_id,
                foreground,
                rgb,
                product_name=display_name,
                display_price=product.display_price or "",
                shop_hint=shop_hint,
                dominant_colors=dominant,
                brand_colors=brand_colors,
            )
            url = _save_variation_jpeg(product.pk, preset_id, rendered)
            new_urls.append(url)
        except Exception as exc:
            logger.error("Photo variation preset %s failed for %s: %s", preset_id, product.pk, exc)

    if not new_urls:
        return {"error": "render_failed", "variations_created": 0}

    kept = _strip_generated_variations(product.additional_images, product.pk)
    product.additional_images = kept + new_urls
    product.save(update_fields=["additional_images", "updated_at"])

    logger.info(
        "expand_product_photos: product=%s presets=%s urls=%d",
        product.pk, presets, len(new_urls),
    )
    return {
        "variations_created": len(new_urls),
        "presets": presets,
        "urls": new_urls,
    }
