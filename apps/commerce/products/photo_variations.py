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

from apps.create.agents.carousel import _fit_font_size, _load_product_image
from apps.create.agents.graphics import _draw_gradient, _get_brand_palette, _get_font, _hex_to_rgb
from apps.commerce.products.commerce_autopilot import sanitize_product_name
from apps.commerce.products.image_utils import apply_exif_orientation

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
VISUAL_MODE_ENHANCE_LIGHTING = "enhance_lighting"
VISUAL_MODE_QUICK_POLISH = "quick_polish"
VISUAL_MODE_PRO_SCENE = "pro_scene"  # DB value — UI label: Studio polish
VISUAL_MODE_STUDIO_POLISH = "studio_polish"  # alias

PRESET_STUDIO_HERO = "studio_hero"
STUDIO_POLISH_MODES = frozenset({VISUAL_MODE_PRO_SCENE, VISUAL_MODE_STUDIO_POLISH})


def is_studio_polish_mode(mode: str | None) -> bool:
    """True when Snap should run photo expansion (studio or lite polish)."""
    if mode == VISUAL_MODE_QUICK_POLISH:
        return True  # legacy DB value → polish path (lite or studio via polish_mode)
    if mode == VISUAL_MODE_ENHANCE_LIGHTING:
        return True  # PhotoFix-only path
    return mode in STUDIO_POLISH_MODES


def is_photofix_only_mode(mode: str | None) -> bool:
    return mode == VISUAL_MODE_ENHANCE_LIGHTING


def is_lite_polish_mode(product) -> bool:
    from apps.commerce.products.polish_mode import POLISH_MODE_LITE, resolve_polish_mode

    return resolve_polish_mode(product.user, product=product) == POLISH_MODE_LITE


def normalize_visual_mode(mode: str | None) -> str:
    """Map legacy quick_polish to paid studio path."""
    mode = mode or VISUAL_MODE_PRO_SCENE
    if mode in (VISUAL_MODE_QUICK_POLISH, VISUAL_MODE_STUDIO_POLISH):
        return VISUAL_MODE_PRO_SCENE
    if mode == VISUAL_MODE_AS_IS:
        return VISUAL_MODE_AS_IS
    if mode == VISUAL_MODE_ENHANCE_LIGHTING:
        return VISUAL_MODE_ENHANCE_LIGHTING
    if mode == VISUAL_MODE_PRO_SCENE:
        return VISUAL_MODE_PRO_SCENE
    return VISUAL_MODE_PRO_SCENE


def product_uses_upload_images_only(product) -> bool:
    """True when the merchant chose Use as-is — no Photoroom scene expansion."""
    return bool(product and getattr(product, "uses_upload_images_only", False))


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
    title_y = int(height * 0.14)
    text_block_h = int(height * 0.72)

    title_font, wrapped_name, title_spacing = _fit_font_size(
        draw,
        product_name[:80],
        max_width=text_w,
        max_height=int(text_block_h * 0.42),
        start_size=int(height * 0.048),
        min_size=18,
        bold=True,
        max_lines=4,
        line_spacing_ratio=0.22,
    )
    draw.multiline_text(
        (text_x, title_y),
        wrapped_name,
        font=title_font,
        fill=_hex_to_rgb(colors["text"]),
        spacing=title_spacing,
    )

    name_bbox = draw.multiline_textbbox(
        (text_x, title_y),
        wrapped_name,
        font=title_font,
        spacing=title_spacing,
    )
    price_y = name_bbox[3] + int(height * 0.04)

    if display_price:
        price_font, price_text, _ = _fit_font_size(
            draw,
            display_price,
            max_width=text_w,
            max_height=int(height * 0.12),
            start_size=int(height * 0.065),
            min_size=22,
            bold=True,
            max_lines=1,
        )
        draw.text(
            (text_x, price_y),
            price_text,
            font=price_font,
            fill=_hex_to_rgb(colors["accent"]),
        )
        price_bbox = draw.textbbox((text_x, price_y), price_text, font=price_font)
        hint_y = price_bbox[3] + int(height * 0.04)
    else:
        hint_y = price_y

    if shop_hint:
        hint_max_h = (title_y + text_block_h) - hint_y
        hint_font, wrapped_hint, hint_spacing = _fit_font_size(
            draw,
            shop_hint[:120],
            max_width=text_w,
            max_height=max(hint_max_h, 24),
            start_size=int(height * 0.024),
            min_size=13,
            max_lines=2,
            line_spacing_ratio=0.35,
        )
        draw.multiline_text(
            (text_x, hint_y),
            wrapped_hint,
            font=hint_font,
            fill=_hex_to_rgb(colors.get("text_muted", "#B0B0B0")),
            spacing=hint_spacing,
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
    shadow_blur: int = 16,
    shadow_opacity: float = 0.32,
    shadow_offset: int = 12,
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
        sh = _make_shadow_layer(fg, blur=shadow_blur, opacity=shadow_opacity)
        base.paste(sh, (x, y + shadow_offset), sh)

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
    shadow_blur: int = 16,
    shadow_opacity: float = 0.32,
    shadow_offset: int = 12,
    studio_bg_hex: str | None = None,
) -> Image.Image:
    width, height = CANVAS_SIZE
    shadow_kwargs = {
        "shadow_blur": shadow_blur,
        "shadow_opacity": shadow_opacity,
        "shadow_offset": shadow_offset,
    }
    brand_studio = f"#{studio_bg_hex}" if studio_bg_hex else brand_colors.get("primary", "#FFFFFF")

    if preset_id == PRESET_WHITE_STUDIO:
        bg_hex = brand_studio if studio_bg_hex else "#FFFFFF"
        bg = _solid_background(width, height, bg_hex)
        return _paste_product_centered(bg, foreground, scale=0.92, **shadow_kwargs)

    if preset_id == PRESET_GRAY_STUDIO:
        bg = _solid_background(width, height, "#E8EAED")
        return _paste_product_centered(bg, foreground, scale=0.90, **shadow_kwargs)

    if preset_id == PRESET_BRAND_GRADIENT:
        top, bottom = dominant_colors[0], dominant_colors[-1] if len(dominant_colors) > 1 else "#1a1a2e"
        if studio_bg_hex:
            top = brand_studio
        bg = _gradient_background(width, height, top, bottom)
        return _paste_product_centered(bg, foreground, scale=0.88, **shadow_kwargs)

    if preset_id == PRESET_SOFT_PASTEL:
        top = dominant_colors[0] if dominant_colors else "#dceefb"
        bg = _gradient_background(width, height, top, "#f7f9fc")
        return _paste_product_centered(bg, foreground, scale=0.90, **shadow_kwargs)

    if preset_id == PRESET_DARK_PREMIUM:
        bg = _gradient_background(width, height, "#0f0f14", "#2a2a38")
        return _paste_product_centered(bg, foreground, scale=0.86, **shadow_kwargs)

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
    return _paste_product_centered(bg, foreground, scale=0.75, **shadow_kwargs)


def _save_variation_jpeg(product_id, preset_id: str, image: Image.Image) -> str:
    from apps.create.content.tasks import _public_url_for_file

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


def expand_product_photos(
    product,
    analysis: dict | None = None,
    mode: str | None = None,
    *,
    commerce_source: str | None = None,
    polish_session=None,
    scene_pack: str | None = None,
    brand_template=None,
    polish_mode: str | None = None,
    visual_brief=None,
) -> dict:
    """
    Generate scene variations from the product's primary photo.
    Appends URLs to product.additional_images (replaces prior auto-variations).

    mode: as_is | pro_scene / studio_polish (quick_polish legacy → polish path)
    polish_mode: lite | studio — lite uses Basic API + local presets (no Plus credits)
    """
    mode = normalize_visual_mode(mode or getattr(product, "visual_mode", None))

    if mode == VISUAL_MODE_AS_IS:
        return {"skipped": True, "reason": "as_is", "variations_created": 0}

    if mode == VISUAL_MODE_ENHANCE_LIGHTING:
        return _expand_photofix_only(
            product,
            analysis,
            commerce_source=commerce_source,
            polish_session=polish_session,
        )

    from apps.commerce.products.polish_mode import POLISH_MODE_LITE, resolve_polish_mode
    from apps.commerce.products.scene_packs import get_product_scene_pack, normalize_scene_pack

    resolved_polish = resolve_polish_mode(
        product.user,
        polish_mode,
        product=product,
    )
    if resolved_polish == POLISH_MODE_LITE:
        return _expand_lite_polish(product, analysis)

    pack = normalize_scene_pack(scene_pack or get_product_scene_pack(product))
    return _expand_studio_polish(
        product,
        analysis,
        commerce_source=commerce_source,
        polish_session=polish_session,
        scene_pack=pack,
        brand_template=brand_template,
        visual_brief=visual_brief,
    )


def _studio_polish_error(reason: str, *, limit_message: str = "") -> dict:
    return {
        "error": reason,
        "reason": reason,
        "variations_created": 0,
        "mode": VISUAL_MODE_PRO_SCENE,
        "limit_message": limit_message,
    }


def _expand_photofix_only(
    product,
    analysis: dict | None = None,
    *,
    commerce_source: str | None = None,
    polish_session=None,
) -> dict:
    """PhotoFix-only — lighting/beautify repair without AI scene expansion."""
    from apps.core.billing.models import get_effective_plan_tier
    from apps.core.billing.visual_credits import (
        check_visual_credit_limit,
        finish_studio_polish_session,
        record_studio_polish,
    )
    from apps.commerce.products.photoroom import save_studio_polish_image
    from apps.commerce.products.photoroom_plus import PLUS_VARIANT_CATALOG, run_plus_variant
    from apps.commerce.products.photoroom_preflight import run_preflight_repairs

    if not product.image:
        return {"skipped": True, "reason": "no_image", "variations_created": 0}

    allowed, limit_msg = check_visual_credit_limit(product.user)
    if not allowed:
        return _studio_polish_error("credit_limit", limit_message=limit_msg)

    try:
        source = product.image.url
    except Exception:
        return {"skipped": True, "reason": "no_image", "variations_created": 0}

    plan_tier = get_effective_plan_tier(getattr(product.user, "profile", None))
    brand_colors = None
    profile = getattr(product.user, "profile", None)
    if profile is not None:
        colors = getattr(profile, "brand_colors", None) or []
        if isinstance(colors, list) and colors:
            brand_colors = {
                "primary": str(colors[0]).lstrip("#"),
                "secondary": str(colors[1]).lstrip("#") if len(colors) > 1 else "",
            }
        elif isinstance(colors, dict):
            brand_colors = colors

    preflight = run_preflight_repairs(
        source,
        product,
        analysis,
        brand_colors,
        budget=2,
        plan_tier=plan_tier,
        commerce_source=commerce_source,
    )
    product.refresh_from_db(fields=["additional_images"])

    urls: list[str] = []
    for variant_id in preflight.repairs_run:
        marker = f"preflight_{variant_id}"
        for u in product.additional_images or []:
            if marker in (u or "") and u not in urls:
                urls.append(u)
                break

    if not urls and preflight.master_url and preflight.master_url != source:
        urls.append(preflight.master_url)
    elif not urls:
        master_url = preflight.master_url or source
        spec = PLUS_VARIANT_CATALOG.get("photofix")
        if spec:
            edit_result = run_plus_variant(
                master_url, spec, product, analysis, brand_colors,
            )
            if edit_result.ok:
                try:
                    url = save_studio_polish_image(
                        product.pk, edit_result.content, suffix="photofix_only",
                    )
                    urls.append(url)
                    record_studio_polish(
                        product.user,
                        product_id=str(product.pk),
                        provider="photoroom_plus",
                        output_data={
                            "variant": "photofix",
                            "label": "PhotoFix",
                            "url": url,
                            "mode": "enhance_lighting",
                        },
                    )
                except Exception as exc:
                    logger.warning("PhotoFix-only save failed: %s", exc)

    if urls:
        extras = list(product.additional_images or [])
        for url in urls:
            if url not in extras:
                extras.append(url)
        product.additional_images = extras
        product.save(update_fields=["additional_images", "updated_at"])

    if polish_session:
        finish_studio_polish_session(polish_session, success=bool(urls))

    return {
        "variations_created": len(urls),
        "urls": urls,
        "mode": VISUAL_MODE_ENHANCE_LIGHTING,
        "preflight_repairs": preflight.repairs_run,
    }


def _fallback_minimal_studio(
    product,
    source: str,
    brand_colors: dict | None,
) -> dict | None:
    """One Photoroom studio call, then local presets if the API is down."""
    from apps.commerce.products.photoroom import (
        pick_background_color_hex,
        save_studio_polish_image,
        studio_polish_via_photoroom,
    )

    bg = pick_background_color_hex(product, brand_colors)
    hero_bytes = studio_polish_via_photoroom(source, background_color=bg)
    if hero_bytes:
        try:
            url = save_studio_polish_image(product.pk, hero_bytes, suffix="studio_white")
            return {"urls": [url], "variant_ids": ["studio_white"], "provider": "photoroom_minimal"}
        except Exception as exc:
            logger.error("Minimal studio save failed: %s", exc)

    quick = _expand_quick_polish(product, analysis=None)
    if quick.get("variations_created", 0) > 0:
        return {
            "urls": quick.get("urls") or [],
            "variant_ids": ["local_quick_polish"],
            "provider": "local_quick_polish",
        }
    return None


def _expand_studio_polish(
    product,
    analysis: dict | None = None,
    *,
    commerce_source: str | None = None,
    polish_session=None,
    scene_pack: str | None = None,
    brand_template=None,
    visual_brief=None,
) -> dict:
    """Photoroom Plus pack — all applicable v2/edit variants (1 credit each)."""
    from apps.core.billing.models import get_effective_plan_tier
    from apps.core.billing.visual_credits import (
        begin_studio_polish_session,
        check_visual_credit_limit,
        finish_studio_polish_session,
        get_visual_credit_usage,
        record_studio_polish,
    )
    from apps.commerce.products.photoroom import photoroom_enabled, save_studio_polish_image
    from apps.commerce.products.photoroom_plus import (
        LAYOUT_VARIANT_IDS,
        PLUS_VARIANT_CATALOG,
        detect_product_category,
        get_max_variants_for_plan,
        multi_angle_polish_credit_enabled,
        run_plus_variant,
        select_plus_variants,
        slide_role_for_variant,
    )
    from apps.commerce.products.scene_packs import normalize_scene_pack, raw_upload_image_urls

    if polish_session is None:
        polish_session = begin_studio_polish_session(
            product.user,
            product_id=str(product.pk),
            source=commerce_source or "manual",
        )

    def _finish(result: dict) -> dict:
        ok = (
            result.get("variations_created", 0) > 0
            or result.get("skipped")
            or result.get("reason") == "as_is"
        )
        finish_studio_polish_session(
            polish_session,
            success=ok,
            output_data=result,
            error_message=result.get("limit_message") or result.get("error") or "",
        )
        return result

    if not getattr(settings, "PHOTO_VARIATIONS_ENABLED", True):
        return _finish({"skipped": True, "reason": "disabled"})

    if not product.image:
        return _finish(_studio_polish_error("no_image"))

    scene_pack = normalize_scene_pack(scene_pack)
    raw_extra_angles = raw_upload_image_urls(product.additional_images)

    allowed, msg = check_visual_credit_limit(product.user)
    if not allowed:
        logger.info("Studio polish cap reached for %s", product.user_id)
        reason = "platform_blocked" if "platform" in msg.lower() else "at_limit"
        return _finish(_studio_polish_error(reason, limit_message=msg))

    source = product.image.url if hasattr(product.image, "url") else str(product.image)

    if not photoroom_enabled():
        logger.warning("Studio polish unavailable — PHOTOROOM_API_KEY missing")
        profile = getattr(product.user, "profile", None)
        brand_colors = _get_brand_palette(profile)
        fallback = _fallback_minimal_studio(product, source, brand_colors)
        if fallback and fallback.get("urls"):
            product.additional_images = (product.additional_images or []) + fallback["urls"]
            product.save(update_fields=["additional_images", "updated_at"])
            return _finish({
                "variations_created": len(fallback["urls"]),
                "mode": VISUAL_MODE_PRO_SCENE,
                "provider": fallback["provider"],
                "urls": fallback["urls"],
                "fallback": True,
            })
        return _finish(_studio_polish_error("photoroom_not_configured"))

    from django.conf import settings as django_settings

    from apps.commerce.products.photoroom_brand_template import build_photoroom_brand_template
    from apps.commerce.products.photoroom_brand_template import hero_studio_variant_ids
    from apps.commerce.products.photoroom_preflight import (
        run_channel_exports,
        run_marketplace_exports,
        run_preflight_repairs,
    )
    from apps.commerce.products.scene_packs import scene_pack_export_budget

    profile = getattr(product.user, "profile", None)
    plan_tier = get_effective_plan_tier(profile) if profile else "starter"
    brand_colors = _get_brand_palette(profile)
    if brand_template is None:
        brand_template = build_photoroom_brand_template(profile, product.user_id)
    usage = get_visual_credit_usage(product.user)
    plan_max = get_max_variants_for_plan(plan_tier)
    if usage.get("unlimited"):
        credit_pool = plan_max
    else:
        credit_pool = min(plan_max, max(0, usage.get("remaining", 0)))
    if credit_pool <= 0:
        return _finish(_studio_polish_error("at_limit", limit_message=msg))

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
        commerce_source=commerce_source,
    )
    credit_pool -= len(preflight.repairs_run)
    source = preflight.master_url

    from apps.commerce.products.photoroom import _load_image_bytes

    master_bytes: bytes | None = None
    loaded = _load_image_bytes(source)
    if loaded:
        master_bytes, _ = loaded

    cutout_png_url: str | None = None
    if getattr(django_settings, "PHOTOROOM_TRANSPARENT_CUTOUT_SAVE", True):
        from apps.commerce.products.photoroom_basic import save_transparent_cutout

        cutout_png_url = save_transparent_cutout(
            product.pk,
            source,
            file_bytes=master_bytes,
        )

    uncertainty = preflight.quality.uncertainty_score
    if uncertainty is None and getattr(
        django_settings, "PHOTOROOM_BASIC_PROBE_ENABLED", True,
    ):
        from apps.commerce.products.photoroom_basic import probe_basic_cutout_quality
        from apps.commerce.products.photoroom_plus import detect_product_category

        product_category_early = detect_product_category(product, analysis)
        basic_score, _ = probe_basic_cutout_quality(
            source,
            category=product_category_early,
            original_bytes=master_bytes,
        )
        if basic_score is not None:
            uncertainty = basic_score
            preflight.quality.uncertainty_score = uncertainty

    if (
        uncertainty is None
        and getattr(django_settings, "PHOTOROOM_UNCERTAINTY_PROBE_ENABLED", True)
        and credit_pool > 0
    ):
        ok_probe, _ = check_visual_credit_limit(product.user)
        if ok_probe:
            from apps.commerce.products.photoroom_api import merge_uncertainty, probe_cutout_uncertainty

            score, probe_result = probe_cutout_uncertainty(source)
            if probe_result.sandbox_limited:
                return _finish(_studio_polish_error(
                    "platform_blocked",
                    limit_message=probe_result.error or "Photoroom sandbox limit reached.",
                ))
            if probe_result.ok:
                credit_pool -= 1
                uncertainty = merge_uncertainty(uncertainty, score)
                preflight.quality.uncertainty_score = uncertainty

    story_banner_slots, marketplace_slots = scene_pack_export_budget(scene_pack, plan_tier)
    export_slots = story_banner_slots + marketplace_slots
    target_variants = int(getattr(django_settings, "STUDIO_POLISH_TARGET_VARIANTS", 4))
    min_scenes = min(
        int(getattr(django_settings, "PHOTOROOM_MIN_SCENE_VARIANTS", 3)),
        target_variants,
    )
    if getattr(django_settings, "PHOTOROOM_PROFESSIONAL_MODE", True):
        prof_min = int(getattr(django_settings, "PHOTOROOM_PROFESSIONAL_MIN_SCENES", 4))
        min_scenes = min(max(min_scenes, prof_min), target_variants)
    if credit_pool > min_scenes and export_slots > 0 and target_variants > 4:
        export_budget = min(export_slots, credit_pool - min_scenes)
        channel_budget = min(story_banner_slots, export_budget)
        marketplace_budget = min(
            marketplace_slots,
            max(0, export_budget - channel_budget),
        )
        scene_budget = credit_pool - channel_budget - marketplace_budget
    else:
        channel_budget = 0
        marketplace_budget = 0
        scene_budget = max(1, min(credit_pool, target_variants))

    from apps.create.media.orchestrator import cap_photoroom_scenes_for_plan

    scene_budget = cap_photoroom_scenes_for_plan(product.user, scene_budget)

    from apps.create.media.campaign_visual_brief import get_visual_brief_for_product

    brief = visual_brief or get_visual_brief_for_product(product)
    if brief:
        scene_budget = min(scene_budget, len(brief.capped_scenes(product.user)))
        if getattr(django_settings, "PHOTOROOM_PROFESSIONAL_MODE", True):
            from apps.create.media.photoroom_brief import max_scenes_for_user

            scene_budget = max(scene_budget, min(max_scenes_for_user(product.user), credit_pool))

    category = detect_product_category(product, analysis)
    offering = getattr(product, "offering_type", "product") or "product"

    variants = select_plus_variants(
        product,
        analysis,
        plan_tier=plan_tier,
        max_count=scene_budget,
        uncertainty_score=uncertainty,
        brand_template=brand_template,
        brand_colors=brand_colors,
        commerce_source=commerce_source,
        scene_pack=scene_pack,
        visual_brief=brief,
    )

    new_urls: list[str] = []
    variant_ids: list[str] = []
    failed_ids: list[str] = []
    first_hero_bytes: bytes | None = None
    ai_layout_index = 0

    import concurrent.futures

    def _process_single_variant(args):
        spec, layout_idx = args
        try:
            return spec, run_plus_variant(
                source,
                spec,
                product,
                analysis,
                brand_colors,
                brand_template=brand_template,
                layout_index=layout_idx,
                visual_brief=brief,
            )
        except Exception as exc:
            logger.warning("Plus variant %s failed: %s", spec.id, exc)
            from apps.commerce.products.photoroom_api import PhotoroomEditResult

            return spec, PhotoroomEditResult(content=None, error=str(exc))

    # Pre-check credits and build work items
    work_items = []
    for spec in variants:
        ok, cap_msg = check_visual_credit_limit(product.user)
        if not ok:
            logger.info("Stopping Plus pack — credit cap for user %s", product.user_id)
            break
        layout_idx = ai_layout_index if spec.id in LAYOUT_VARIANT_IDS else 0
        if spec.id in LAYOUT_VARIANT_IDS:
            ai_layout_index += 1
        work_items.append((spec, layout_idx))

    max_workers = int(getattr(django_settings, "PHOTOROOM_EXPAND_MAX_WORKERS", 2))
    results_ordered = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_single_variant, item): idx
            for idx, item in enumerate(work_items)
        }
        results_map = {}
        for future in concurrent.futures.as_completed(futures):
            idx = futures[future]
            results_map[idx] = future.result()
        # Maintain original order
        for idx in range(len(work_items)):
            if idx in results_map:
                results_ordered.append(results_map[idx])

    from apps.commerce.products.photoroom_api import merge_uncertainty

    from apps.commerce.products.photoroom_review import review_flags_for_output
    from apps.commerce.products.photoroom_guard import (
        SAFE_HERO_VARIANT_ID,
        is_cutout_variant,
        validate_cutout_output,
    )

    product_category = detect_product_category(product, analysis)

    # Process results in order
    for spec, edit_result in results_ordered:
        if edit_result and edit_result.uncertainty_score is not None:
            preflight.quality.uncertainty_score = merge_uncertainty(
                preflight.quality.uncertainty_score,
                edit_result.uncertainty_score,
            )
        image_bytes = edit_result.content if edit_result and edit_result.ok else None

        if edit_result and getattr(django_settings, "PHOTOROOM_QA_ENABLED", True):
            from apps.create.media.photoroom_brief import qa_retry_params, validate_plus_result
            from apps.commerce.products.photoroom_plus import photoroom_edit

            ok_qa, qa_reason = validate_plus_result(edit_result, variant_id=spec.id)
            if not ok_qa and image_bytes:
                logger.info("Photoroom QA retry for %s (%s)", spec.id, qa_reason)
                retry_params = qa_retry_params(spec.id, product_category)
                if retry_params and credit_pool > 0:
                    retry_result = photoroom_edit(source, retry_params)
                    if retry_result.ok and retry_result.content:
                        edit_result = retry_result
                        image_bytes = retry_result.content
                        credit_pool -= 1
                    else:
                        image_bytes = None

        if image_bytes and master_bytes and is_cutout_variant(spec.id):
            ok_cutout, reject_reason = validate_cutout_output(
                master_bytes,
                image_bytes,
                category=product_category,
            )
            if not ok_cutout:
                logger.warning(
                    "Cutout rejected for %s on product %s (%s) — studio_safe fallback",
                    spec.id,
                    product.pk,
                    reject_reason,
                )
                safe_spec = PLUS_VARIANT_CATALOG.get(SAFE_HERO_VARIANT_ID)
                if safe_spec and credit_pool > 0:
                    safe_result = run_plus_variant(
                        source,
                        safe_spec,
                        product,
                        analysis,
                        brand_colors,
                        brand_template=brand_template,
                        visual_brief=brief,
                    )
                    if safe_result.ok and safe_result.content:
                        image_bytes = safe_result.content
                        edit_result = safe_result
                        spec = safe_spec
                    else:
                        image_bytes = None
                else:
                    image_bytes = None

        if spec.id in LAYOUT_VARIANT_IDS and image_bytes:
            pass  # layout_index already incremented above
        if not image_bytes:
            if edit_result and edit_result.sandbox_limited:
                return _finish(_studio_polish_error(
                    "platform_blocked",
                    limit_message=edit_result.error or "Photoroom sandbox limit reached.",
                ))
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
            provider="photoroom_basic" if edit_result.api == "basic/v1/segment" else "photoroom_plus",
            output_data={
                "variant": spec.id,
                "label": spec.label,
                "url": hero_url,
                "uncertainty_score": edit_result.uncertainty_score if edit_result else None,
                "phase": "scene",
                "slide_role": slide_role_for_variant(
                    spec.id,
                    getattr(product, "offering_type", "product") or "product",
                    detect_product_category(product, analysis),
                ),
                "brand_template": brand_template.as_log_dict() if brand_template else {},
                "api": edit_result.api if edit_result else "v2/edit",
                **review_flags_for_output(
                    spec.id,
                    uncertainty_score=edit_result.uncertainty_score if edit_result else None,
                ),
            },
        )
        new_urls.append(hero_url)
        variant_ids.append(spec.id)

    if not new_urls:
        fallback = _fallback_minimal_studio(product, source, brand_colors)
        if fallback and fallback.get("urls"):
            kept = _strip_generated_variations(product.additional_images, product.pk)
            product.additional_images = kept + fallback["urls"]
            product.save(update_fields=["additional_images", "updated_at"])
            return _finish({
                "variations_created": len(fallback["urls"]),
                "plus_variants": 0,
                "variant_ids": fallback.get("variant_ids", []),
                "failed_variants": failed_ids,
                "mode": VISUAL_MODE_PRO_SCENE,
                "provider": fallback.get("provider", "fallback"),
                "urls": fallback["urls"],
                "fallback": True,
            })
        return _finish(_studio_polish_error("photoroom_failed"))

    multi_angle_variant: str | None = None
    multi_angle_count = 0
    if (
        target_variants > 4
        and multi_angle_polish_credit_enabled(plan_tier)
        and raw_extra_angles
        and credit_pool > 0
    ):
        angle_spec = PLUS_VARIANT_CATALOG.get("edit_ai_angle")
        if angle_spec:
            for angle_idx, angle_url in enumerate(raw_extra_angles):
                if credit_pool <= 0:
                    break
                ok_angle, _ = check_visual_credit_limit(product.user)
                if not ok_angle:
                    break
                try:
                    angle_result = run_plus_variant(
                        angle_url,
                        angle_spec,
                        product,
                        analysis,
                        brand_colors,
                        brand_template=brand_template,
                    )
                except Exception as exc:
                    logger.warning(
                        "Multi-angle polish failed for %s (angle %d): %s",
                        product.pk,
                        angle_idx + 1,
                        exc,
                    )
                    continue
                if not angle_result or not angle_result.ok or not angle_result.content:
                    continue
                try:
                    angle_suffix = f"edit_ai_angle_{angle_idx + 1}"
                    angle_polished_url = save_studio_polish_image(
                        product.pk,
                        angle_result.content,
                        suffix=angle_suffix,
                    )
                except Exception as exc:
                    logger.warning(
                        "Multi-angle save failed for %s (angle %d): %s",
                        product.pk,
                        angle_idx + 1,
                        exc,
                    )
                    continue
                record_studio_polish(
                    product.user,
                    product_id=product.pk,
                    provider="photoroom_plus",
                    output_data={
                        "variant": angle_spec.id,
                        "label": f"{angle_spec.label} ({angle_idx + 2})",
                        "url": angle_polished_url,
                        "phase": "scene",
                        "slide_role": "proof",
                        "api": angle_result.api if angle_result else "v2/edit",
                        "multi_angle": True,
                        **review_flags_for_output(
                            angle_spec.id,
                            uncertainty_score=angle_result.uncertainty_score,
                        ),
                    },
                )
                new_urls.append(angle_polished_url)
                variant_ids.append(angle_spec.id)
                multi_angle_variant = angle_spec.id
                multi_angle_count += 1
                credit_pool = max(0, credit_pool - 1)

    if (
        offering == "product"
        and credit_pool > 0
        and getattr(django_settings, "PHOTOROOM_VIRTUAL_MODEL_AUTO_PACK", True)
        and len(variant_ids) < target_variants
        and "virtual_model" not in variant_ids
        and not any(v.startswith("virtual_model") for v in variant_ids)
    ):
        from apps.commerce.products.photoroom_virtual_models import append_virtual_model_pack

        remaining = target_variants - len(variant_ids)
        vm_budget = min(credit_pool, remaining, 1 if target_variants <= 4 else credit_pool)
        vm_urls, vm_ids, vm_credits = append_virtual_model_pack(
            product,
            source,
            analysis,
            brand_colors,
            brand_template=brand_template,
            credit_budget=vm_budget,
            product_category=product_category,
        )
        if vm_urls:
            new_urls.extend(vm_urls)
            variant_ids.extend(vm_ids)
            credit_pool = max(0, credit_pool - vm_credits)

    channel_ids: list[str] = []
    marketplace_ids: list[str] = []
    if new_urls:
        hero_studio_ids = hero_studio_variant_ids(brand_template, brand_colors)
        hero_url = new_urls[0]
        for preferred_id in hero_studio_ids:
            for url, vid in zip(new_urls, variant_ids):
                if vid == preferred_id:
                    hero_url = url
                    break
            else:
                continue
            break

        if channel_budget > 0:
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

        if marketplace_budget > 0:
            marketplace_urls, marketplace_ids = run_marketplace_exports(
                hero_url,
                product,
                analysis,
                brand_colors,
                budget=marketplace_budget,
                brand_template=brand_template,
            )
            new_urls.extend(marketplace_urls)

    if target_variants > 4:
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

    if cutout_png_url and target_variants > 4:
        new_urls.append(cutout_png_url)

    kept = _strip_generated_variations(product.additional_images, product.pk)
    product.additional_images = kept + new_urls
    product.save(update_fields=["additional_images", "updated_at"])

    from apps.create.agents.models import AgentAction
    from apps.commerce.products.photoroom_review import summarize_review_state

    polish_actions = list(
        AgentAction.objects.filter(
            user=product.user,
            action_type__in=("commerce.studio_polish", "commerce.pro_scene"),
            input_data__product_id=str(product.pk),
            status=AgentAction.ActionStatus.COMPLETED,
        ).exclude(input_data__session=True).order_by("-created_at")[:50]
    )
    review_state = summarize_review_state(polish_actions)

    logger.info(
        "Plus pack: product=%s variants=%d/%d failed=%s preflight=%s channel=%s marketplace=%s",
        product.pk,
        len(variant_ids),
        len(variants),
        failed_ids,
        preflight.repairs_run,
        channel_ids,
        marketplace_ids,
    )
    return _finish({
        "variations_created": len(new_urls),
        "plus_variants": len(variant_ids),
        "variant_ids": variant_ids,
        "failed_variants": failed_ids,
        "scene_pack": scene_pack,
        "multi_angle_polished": bool(multi_angle_variant),
        "multi_angle_count": multi_angle_count,
        "multi_angle_variant": multi_angle_variant,
        "preflight_repairs": preflight.repairs_run,
        "preflight_failed": preflight.repairs_failed,
        "channel_exports": channel_ids,
        "marketplace_exports": marketplace_ids,
        "photo_quality": {
            "lighting": preflight.quality.lighting,
            "sharpness": preflight.quality.sharpness,
            "crop": preflight.quality.crop,
            "uncertainty_score": preflight.quality.uncertainty_score,
        },
        "brand_template": brand_template.as_log_dict() if brand_template else {},
        "mode": VISUAL_MODE_PRO_SCENE,
        "provider": "photoroom_plus",
        "urls": new_urls,
        **review_state,
    })


def _lite_shadow_params(shadow_mode: str | None) -> tuple[int, float, int]:
    """Map brand shadow_mode to local Pillow shadow (blur, opacity, y-offset)."""
    mode = (shadow_mode or "ai.soft").lower()
    if mode == "ai.hard":
        return 8, 0.42, 6
    if mode == "ai.floating":
        return 28, 0.22, 18
    return 16, 0.32, 12


def _expand_lite_polish(product, analysis: dict | None = None) -> dict:
    """Lite polish — Basic API cutout when available, else rembg + local presets."""
    from apps.commerce.products.photoroom_brand_template import build_photoroom_brand_template
    from apps.commerce.products.photoroom_basic import basic_api_enabled, photoroom_basic_segment

    if not getattr(settings, "PHOTO_VARIATIONS_ENABLED", True):
        return {"skipped": True, "reason": "disabled", "mode": "lite"}

    if not product.image:
        return {"error": "no_image", "variations_created": 0, "mode": "lite"}

    source = product.image.url if hasattr(product.image, "url") else str(product.image)
    rgb = _load_product_image(source)
    if rgb is None:
        return {"error": "load_failed", "variations_created": 0, "mode": "lite"}

    profile = getattr(product.user, "profile", None)
    brand_colors = _get_brand_palette(profile)
    brand_template = build_photoroom_brand_template(profile, product.user_id)
    if brand_template.enabled and brand_template.studio_color_hex:
        primary = f"#{brand_template.studio_color_hex}"
        brand_colors = {**brand_colors, "primary": primary}

    shadow_blur, shadow_opacity, shadow_offset = _lite_shadow_params(
        brand_template.shadow_mode if brand_template.enabled else None
    )
    dominant = _dominant_hex_colors(rgb)
    cutout_provider = "local_rembg"

    foreground: Image.Image | None = None
    if basic_api_enabled():
        try:
            buf = BytesIO()
            rgb.save(buf, format="JPEG", quality=95)
            cutout_bytes = photoroom_basic_segment(source, file_bytes=buf.getvalue())
            if cutout_bytes:
                fg = Image.open(BytesIO(cutout_bytes)).convert("RGBA")
                if fg.getbbox():
                    foreground = _trim_transparent(fg)
                    cutout_provider = "photoroom_basic"
        except Exception as exc:
            logger.warning("Lite polish Basic cutout failed: %s", exc)

    if foreground is None:
        foreground = remove_product_background(rgb)

    presets = select_presets(product, analysis)
    display_name = sanitize_product_name(product.name) or "Product"
    shop_hint = "Shop link in bio" if product.product_url else ""

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
                shadow_blur=shadow_blur,
                shadow_opacity=shadow_opacity,
                shadow_offset=shadow_offset,
                studio_bg_hex=brand_template.studio_color_hex if brand_template.enabled else None,
            )
            url = _save_variation_jpeg(product.pk, preset_id, rendered)
            new_urls.append(url)
        except Exception as exc:
            logger.error("Lite polish preset %s failed for %s: %s", preset_id, product.pk, exc)

    if not new_urls:
        return {"error": "render_failed", "variations_created": 0, "mode": "lite"}

    kept = _strip_generated_variations(product.additional_images, product.pk)
    product.additional_images = kept + new_urls
    product.save(update_fields=["additional_images", "updated_at"])

    logger.info(
        "expand_lite_polish: product=%s presets=%s urls=%d provider=%s",
        product.pk, presets, len(new_urls), cutout_provider,
    )
    return {
        "variations_created": len(new_urls),
        "presets": presets,
        "urls": new_urls,
        "mode": "lite",
        "polish_mode": "lite",
        "provider": cutout_provider,
        "brand_template": brand_template.as_log_dict() if brand_template else {},
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
