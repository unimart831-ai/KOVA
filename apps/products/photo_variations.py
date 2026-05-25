"""
Product photo expansion — Photoroom Plus studio polish (primary).

Legacy rembg/Pillow presets remain for tests only; production uses v2/edit.
"""

from __future__ import annotations

import logging
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
    if mode == VISUAL_MODE_QUICK_POLISH:
        return True  # legacy DB value → Plus studio
    return mode in STUDIO_POLISH_MODES


def normalize_visual_mode(mode: str | None) -> str:
    """Map legacy quick_polish to paid studio path."""
    mode = mode or VISUAL_MODE_PRO_SCENE
    if mode in (VISUAL_MODE_QUICK_POLISH, VISUAL_MODE_STUDIO_POLISH):
        return VISUAL_MODE_PRO_SCENE
    if mode == VISUAL_MODE_AS_IS:
        return VISUAL_MODE_AS_IS
    if mode == VISUAL_MODE_PRO_SCENE:
        return VISUAL_MODE_PRO_SCENE
    return VISUAL_MODE_PRO_SCENE


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


def _wrap_text_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    max_width: int,
) -> str:
    """Word-wrap text using pixel width (Pillow textbbox)."""
    words = text.split()
    if not words:
        return ""
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        trial = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
                current = [word]
            else:
                lines.append(word)
                current = []
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines)


def _paste_promo_product(
    base: Image.Image,
    product: Image.Image,
    *,
    cutout: bool,
) -> tuple[int, int, int, int]:
    """Place product in left column; return text column start x."""
    width, height = base.size
    col_left = int(width * 0.05)
    col_w = int(width * 0.34)
    margin_v = int(height * 0.14)
    max_h = height - 2 * margin_v
    max_w = int(width * (0.30 if cutout else 0.26))

    if cutout:
        fg = _scale_foreground(product, max_w, max_h)
    else:
        fg = product.convert("RGB")
        fg.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

    x = col_left + (col_w - fg.width) // 2
    y = margin_v + (max_h - fg.height) // 2

    if cutout:
        sh = _make_shadow_layer(fg, blur=14, opacity=0.28)
        base.paste(sh, (x, y + 8), sh)
        base.paste(fg, (x, y), fg)
    else:
        pad = 12
        card_draw = ImageDraw.Draw(base)
        card_draw.rounded_rectangle(
            [(x - pad, y - pad), (x + fg.width + pad, y + fg.height + pad)],
            radius=14,
            fill=(255, 255, 255),
        )
        base.paste(fg, (x, y))

    text_x = col_left + col_w + int(width * 0.04)
    return text_x, width - int(width * 0.05), y


def _draw_promo_text(
    img: Image.Image,
    *,
    text_x: int,
    text_right: int,
    product_name: str,
    display_price: str,
    shop_hint: str,
    colors: dict,
) -> Image.Image:
    """Draw title, price, and shop hint in the right column."""
    width, height = img.size
    text_w = text_right - text_x
    draw = ImageDraw.Draw(img)
    title_y = int(height * 0.16)

    title_size = int(height * 0.052)
    font_title = _get_font(title_size, bold=True)
    wrapped_name = _wrap_text_to_width(draw, product_name[:80], font_title, text_w)
    draw.multiline_text(
        (text_x, title_y),
        wrapped_name,
        font=font_title,
        fill=_hex_to_rgb(colors["text"]),
        spacing=int(title_size * 0.22),
    )

    name_bbox = draw.multiline_textbbox(
        (text_x, title_y),
        wrapped_name,
        font=font_title,
        spacing=int(title_size * 0.22),
    )
    price_y = name_bbox[3] + int(height * 0.05)

    if display_price:
        price_size = int(height * 0.072)
        font_price = _get_font(price_size, bold=True)
        draw.text(
            (text_x, price_y),
            display_price,
            font=font_price,
            fill=_hex_to_rgb(colors["accent"]),
        )
        price_bbox = draw.textbbox((text_x, price_y), display_price, font=font_price)
        hint_y = price_bbox[3] + int(height * 0.05)
    else:
        hint_y = price_y

    if shop_hint:
        hint_size = int(height * 0.026)
        font_hint = _get_font(hint_size)
        wrapped_hint = _wrap_text_to_width(draw, shop_hint[:120], font_hint, text_w)
        draw.multiline_text(
            (text_x, hint_y),
            wrapped_hint,
            font=font_hint,
            fill=_hex_to_rgb(colors.get("text_muted", "#B0B0B0")),
            spacing=int(hint_size * 0.35),
        )

    return img


def _draw_promo_border(img: Image.Image, colors: dict) -> Image.Image:
    width, height = img.size
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        [(int(width * 0.04), int(height * 0.04)), (width - int(width * 0.04), height - int(height * 0.04))],
        radius=24,
        outline=_hex_to_rgb(colors["accent"]),
        width=3,
    )
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
    base = bg.convert("RGBA")
    text_x, text_right, _ = _paste_promo_product(base, foreground, cutout=True)
    img = base.convert("RGB")
    img = _draw_promo_text(
        img,
        text_x=text_x,
        text_right=text_right,
        product_name=product_name,
        display_price=display_price,
        shop_hint=shop_hint,
        colors=colors,
    )
    return _draw_promo_border(img, colors)


def _render_promo_from_hero(
    hero: Image.Image,
    *,
    product_name: str,
    display_price: str,
    shop_hint: str,
    colors: dict,
) -> Image.Image:
    """Promo layout using Plus hero (no rembg)."""
    width, height = CANVAS_SIZE
    bg = _gradient_background(width, height, colors["primary"], colors["secondary"])
    base = bg.convert("RGBA")
    text_x, text_right, _ = _paste_promo_product(base, hero, cutout=False)
    img = base.convert("RGB")
    img = _draw_promo_text(
        img,
        text_x=text_x,
        text_right=text_right,
        product_name=product_name,
        display_price=display_price,
        shop_hint=shop_hint,
        colors=colors,
    )
    return _draw_promo_border(img, colors)


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

    mode: as_is | pro_scene / studio_polish (quick_polish legacy → studio)
    """
    mode = normalize_visual_mode(mode or getattr(product, "visual_mode", None))

    if mode == VISUAL_MODE_AS_IS:
        return {"skipped": True, "reason": "as_is", "variations_created": 0}

    return _expand_studio_polish(product, analysis)


def _studio_polish_error(reason: str, *, limit_message: str = "") -> dict:
    return {
        "error": reason,
        "reason": reason,
        "variations_created": 0,
        "mode": VISUAL_MODE_PRO_SCENE,
        "limit_message": limit_message,
    }


def _expand_studio_polish(product, analysis: dict | None = None) -> dict:
    """Photoroom Plus pack — all applicable v2/edit variants (1 credit each)."""
    from apps.billing.models import get_effective_plan_tier
    from apps.billing.visual_credits import check_visual_credit_limit, get_visual_credit_usage, record_studio_polish
    from apps.products.photoroom import photoroom_enabled, save_studio_polish_image
    from apps.products.photoroom_plus import (
        AI_SCENE_VARIANT_IDS,
        detect_product_category,
        get_max_variants_for_plan,
        run_plus_variant,
        select_plus_variants,
        slide_role_for_variant,
    )

    if not getattr(settings, "PHOTO_VARIATIONS_ENABLED", True):
        return {"skipped": True, "reason": "disabled"}

    if not product.image:
        return _studio_polish_error("no_image")

    allowed, msg = check_visual_credit_limit(product.user)
    if not allowed:
        logger.info("Studio polish cap reached for %s", product.user_id)
        reason = "platform_blocked" if "platform" in msg.lower() else "at_limit"
        return _studio_polish_error(reason, limit_message=msg)

    if not photoroom_enabled():
        logger.warning("Studio polish unavailable — PHOTOROOM_API_KEY missing")
        return _studio_polish_error("photoroom_not_configured")

    from django.conf import settings as django_settings

    from apps.products.photoroom_brand_template import build_photoroom_brand_template
    from apps.products.photoroom_preflight import (
        channel_export_budget,
        run_channel_exports,
        run_preflight_repairs,
    )

    profile = getattr(product.user, "profile", None)
    plan_tier = get_effective_plan_tier(profile) if profile else "starter"
    brand_colors = _get_brand_palette(profile)
    brand_template = build_photoroom_brand_template(profile, product.user_id)
    usage = get_visual_credit_usage(product.user)
    plan_max = get_max_variants_for_plan(plan_tier)
    if usage.get("unlimited"):
        credit_pool = plan_max
    else:
        credit_pool = min(plan_max, max(0, usage.get("remaining", 0)))
    if credit_pool <= 0:
        return _studio_polish_error("at_limit", limit_message=msg)

    source = product.image.url if hasattr(product.image, "url") else str(product.image)

    preflight_max = int(getattr(django_settings, "PHOTOROOM_PREFLIGHT_MAX_REPAIRS", 2))
    repair_budget = 0
    if getattr(django_settings, "PHOTOROOM_PREFLIGHT_ENABLED", True):
        repair_budget = min(preflight_max, max(0, credit_pool - 1))

    preflight = run_preflight_repairs(
        source,
        product,
        analysis,
        brand_colors,
        budget=repair_budget,
        plan_tier=plan_tier,
        brand_template=brand_template,
    )
    credit_pool -= len(preflight.repairs_run)
    source = preflight.master_url

    channel_slots = channel_export_budget(plan_tier)
    min_scenes = int(getattr(django_settings, "PHOTOROOM_MIN_SCENE_VARIANTS", 3))
    if credit_pool > min_scenes and channel_slots > 0:
        channel_budget = min(channel_slots, credit_pool - min_scenes)
        scene_budget = credit_pool - channel_budget
    else:
        channel_budget = 0
        scene_budget = max(1, credit_pool)

    variants = select_plus_variants(
        product,
        analysis,
        plan_tier=plan_tier,
        max_count=scene_budget,
    )

    new_urls: list[str] = []
    variant_ids: list[str] = []
    failed_ids: list[str] = []
    first_hero_bytes: bytes | None = None
    ai_layout_index = 0

    for spec in variants:
        ok, cap_msg = check_visual_credit_limit(product.user)
        if not ok:
            logger.info("Stopping Plus pack — credit cap for user %s", product.user_id)
            break

        layout_idx = ai_layout_index if spec.id in AI_SCENE_VARIANT_IDS else 0
        image_bytes = run_plus_variant(
            source,
            spec,
            product,
            analysis,
            brand_colors,
            brand_template=brand_template,
            layout_index=layout_idx,
        )
        if spec.id in AI_SCENE_VARIANT_IDS and image_bytes:
            ai_layout_index += 1
        if not image_bytes:
            failed_ids.append(spec.id)
            continue

        if first_hero_bytes is None:
            first_hero_bytes = image_bytes

        try:
            hero_url = save_studio_polish_image(product.pk, image_bytes, suffix=spec.id)
        except Exception as exc:
            logger.error("Plus save failed [%s]: %s", spec.id, exc)
            failed_ids.append(spec.id)
            continue

        record_studio_polish(
            product.user,
            product_id=product.pk,
            provider="photoroom_plus",
            output_data={
                "variant": spec.id,
                "label": spec.label,
                "url": hero_url,
                "phase": "scene",
                "slide_role": slide_role_for_variant(
                    spec.id,
                    getattr(product, "offering_type", "product") or "product",
                    detect_product_category(product, analysis),
                ),
                "brand_template": brand_template.as_log_dict() if brand_template else {},
                "api": "v2/edit",
            },
        )
        new_urls.append(hero_url)
        variant_ids.append(spec.id)

    if not new_urls:
        reason = "photoroom_failed" if failed_ids else "photoroom_failed"
        return _studio_polish_error(reason)

    channel_ids: list[str] = []
    if channel_budget > 0 and new_urls:
        hero_url = next(
            (u for u in new_urls if "studio_white" in u),
            new_urls[0],
        )
        channel_urls, channel_ids = run_channel_exports(
            hero_url,
            product,
            analysis,
            brand_colors,
            budget=channel_budget,
            aspect_ratio=preflight.quality.aspect_ratio,
            brand_template=brand_template,
        )
        new_urls.extend(channel_urls)

    try:
        if first_hero_bytes:
            hero_img = Image.open(BytesIO(first_hero_bytes)).convert("RGB")
        display_name = sanitize_product_name(product.name) or "Product"
        shop_hint = "Shop link in bio" if product.product_url else ""
        promo = _render_promo_from_hero(
            hero_img,
            product_name=display_name,
            display_price=product.display_price or "",
            shop_hint=shop_hint,
            colors=brand_colors,
        )
        new_urls.append(_save_variation_jpeg(product.pk, PRESET_PROMO_FRAME, promo))
    except Exception as exc:
        logger.debug("Promo frame from Plus hero failed: %s", exc)

    kept = _strip_generated_variations(product.additional_images, product.pk)
    product.additional_images = kept + new_urls
    product.save(update_fields=["additional_images", "updated_at"])

    logger.info(
        "Plus pack: product=%s variants=%d/%d failed=%s preflight=%s channel=%s",
        product.pk,
        len(variant_ids),
        len(variants),
        failed_ids,
        preflight.repairs_run,
        channel_ids,
    )
    return {
        "variations_created": len(new_urls),
        "plus_variants": len(variant_ids),
        "variant_ids": variant_ids,
        "failed_variants": failed_ids,
        "preflight_repairs": preflight.repairs_run,
        "preflight_failed": preflight.repairs_failed,
        "channel_exports": channel_ids,
        "photo_quality": {
            "lighting": preflight.quality.lighting,
            "sharpness": preflight.quality.sharpness,
            "crop": preflight.quality.crop,
        },
        "brand_template": brand_template.as_log_dict() if brand_template else {},
        "mode": VISUAL_MODE_PRO_SCENE,
        "provider": "photoroom_plus",
        "urls": new_urls,
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
