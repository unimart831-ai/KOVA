"""
9:16 beat-frame studio — designed hook / product / CTA cards for motion reels.

Product shots stay text-free; copy lives on dedicated brand cards (editor-style).
"""

from __future__ import annotations

import logging
import textwrap
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from django.conf import settings
from PIL import Image, ImageDraw, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

STORY_WIDTH = 1080
STORY_HEIGHT = 1920


@dataclass
class BeatFrameBrand:
    primary: str = "#1E3A8A"
    secondary: str = "#10B981"
    accent: str = "#F59E0B"
    brand_name: str = ""


def beat_frames_enabled() -> bool:
    return bool(getattr(settings, "REEL_BEAT_FRAMES_ENABLED", True))


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = (hex_color or "#1E3A8A").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _get_font(size: int, *, bold: bool = False):
    from apps.agents.graphics import _get_font as brand_font

    return brand_font(size, bold=bold)


def _draw_vertical_gradient(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
) -> None:
    for y in range(height):
        t = y / max(height - 1, 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def _brand_from_context(ctx: BeatFrameBrand | dict[str, Any] | None) -> BeatFrameBrand:
    if ctx is None:
        return BeatFrameBrand()
    if isinstance(ctx, BeatFrameBrand):
        return ctx
    return BeatFrameBrand(
        primary=ctx.get("primary", "#1E3A8A"),
        secondary=ctx.get("secondary", "#10B981"),
        accent=ctx.get("accent", "#F59E0B"),
        brand_name=(ctx.get("brand_name") or "")[:48],
    )


def render_hook_beat_frame(
    *,
    headline: str,
    brand: BeatFrameBrand | dict | None = None,
    product_image_bytes: bytes | None = None,
) -> Image.Image:
    """Opening beat — bold hook on brand gradient (optional blurred product backdrop)."""
    brand = _brand_from_context(brand)
    w, h = STORY_WIDTH, STORY_HEIGHT
    primary = _hex_to_rgb(brand.primary)
    secondary = _hex_to_rgb(brand.secondary)

    if product_image_bytes:
        try:
            bg = Image.open(BytesIO(product_image_bytes)).convert("RGB")
            bg = ImageOps.fit(bg, (w, h), method=Image.LANCZOS)
            bg = bg.filter(ImageFilter.GaussianBlur(radius=18))
            overlay = Image.new("RGBA", (w, h), (*primary, 180))
            bg = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
        except Exception:
            bg = Image.new("RGB", (w, h))
            draw = ImageDraw.Draw(bg)
            _draw_vertical_gradient(draw, w, h, primary, secondary)
    else:
        bg = Image.new("RGB", (w, h))
        draw = ImageDraw.Draw(bg)
        _draw_vertical_gradient(draw, w, h, primary, secondary)

    draw = ImageDraw.Draw(bg)
    accent = _hex_to_rgb(brand.accent)

    if brand.brand_name:
        name_font = _get_font(int(h * 0.028), bold=True)
        draw.text((int(w * 0.08), int(h * 0.11)), brand.brand_name.upper(), font=name_font, fill=(255, 255, 255, 200))

    headline = " ".join((headline or "New arrival").split())
    title_font = _get_font(int(h * 0.065), bold=True)
    wrapped = textwrap.fill(headline, width=16)
    lines = wrapped.split("\n")[:3]
    text = "\n".join(lines)
    bbox = draw.multiline_textbbox((0, 0), text, font=title_font, spacing=8, align="center")
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (w - tw) // 2
    ty = int(h * 0.38) - th // 2
    draw.multiline_text((tx, ty), text, font=title_font, fill=(255, 255, 255), spacing=8, align="center")

    bar_w = int(w * 0.18)
    bar_h = 6
    draw.rounded_rectangle(
        [(w - bar_w) // 2, int(h * 0.58), (w + bar_w) // 2, int(h * 0.58) + bar_h],
        radius=3,
        fill=accent,
    )
    return bg


def render_cta_beat_frame(
    *,
    price_label: str = "",
    cta_label: str = "Shop on WhatsApp",
    brand: BeatFrameBrand | dict | None = None,
    product_image_bytes: bytes | None = None,
) -> Image.Image:
    """Closing beat — hero product centered, price + CTA in a bottom panel."""
    brand = _brand_from_context(brand)
    w, h = STORY_WIDTH, STORY_HEIGHT
    primary = _hex_to_rgb(brand.primary)
    secondary = _hex_to_rgb(brand.secondary)
    accent = _hex_to_rgb(brand.accent)

    canvas = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(canvas)
    _draw_vertical_gradient(draw, w, h, (8, 12, 24), primary)

    panel_top = int(h * 0.62)
    panel_margin = int(w * 0.07)
    draw.rounded_rectangle(
        [(panel_margin, panel_top), (w - panel_margin, h - int(h * 0.08))],
        radius=32,
        fill=(255, 255, 255),
    )

    if product_image_bytes:
        try:
            product = Image.open(BytesIO(product_image_bytes)).convert("RGBA")
            max_w = int(w * 0.78)
            max_h = int(h * 0.42)
            product.thumbnail((max_w, max_h), Image.LANCZOS)
            px = (w - product.width) // 2
            py = int(h * 0.06) + max((panel_top - int(h * 0.06) - product.height) // 2, 0)

            shadow = Image.new("RGBA", (product.width + 40, product.height + 40), (0, 0, 0, 0))
            sh_draw = ImageDraw.Draw(shadow)
            sh_draw.rounded_rectangle(
                [(20, 24), (product.width + 20, product.height + 28)],
                radius=20,
                fill=(0, 0, 0, 70),
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=12))
            canvas.paste(shadow, (px - 20, py - 12), shadow)
            canvas.paste(product, (px, py), product if product.mode == "RGBA" else None)
            draw = ImageDraw.Draw(canvas)
        except Exception:
            draw = ImageDraw.Draw(canvas)

    inner_x = panel_margin + int(w * 0.06)
    inner_w = w - 2 * panel_margin - int(w * 0.12)
    price = (price_label or "").strip()
    cta = (cta_label or "Shop on WhatsApp").strip()[:36]

    content_y = panel_top + int(h * 0.045)
    if price:
        price_font = _get_font(int(h * 0.056), bold=True)
        price_bbox = draw.textbbox((0, 0), price, font=price_font)
        pw = price_bbox[2] - price_bbox[0]
        draw.text(((w - pw) // 2, content_y), price, font=price_font, fill=primary)
        content_y += int(h * 0.075)

    cta_font = _get_font(int(h * 0.034), bold=True)
    btn_h = int(h * 0.058)
    btn_w = min(inner_w, int(w * 0.72))
    btn_x = (w - btn_w) // 2
    draw.rounded_rectangle(
        [(btn_x, content_y), (btn_x + btn_w, content_y + btn_h)],
        radius=16,
        fill=secondary,
    )
    cta_bbox = draw.textbbox((0, 0), cta, font=cta_font)
    cw = cta_bbox[2] - cta_bbox[0]
    ch = cta_bbox[3] - cta_bbox[1]
    draw.text(
        (btn_x + (btn_w - cw) // 2, content_y + (btn_h - ch) // 2 - 2),
        cta,
        font=cta_font,
        fill=(255, 255, 255),
    )

    if brand.brand_name:
        foot_font = _get_font(int(h * 0.026))
        name = brand.brand_name
        nb = draw.textbbox((0, 0), name, font=foot_font)
        nw = nb[2] - nb[0]
        draw.text(
            ((w - nw) // 2, h - int(h * 0.055)),
            name,
            font=foot_font,
            fill=(180, 190, 210),
        )

    accent_bar = int(w * 0.14)
    draw.rounded_rectangle(
        [(w - accent_bar) // 2, panel_top - int(h * 0.018), (w + accent_bar) // 2, panel_top - int(h * 0.018) + 5],
        radius=2,
        fill=accent,
    )
    return canvas


def render_product_beat_frame(
    image_bytes: bytes,
    *,
    slide_index: int = 0,
    source_hint: str = "",
) -> Image.Image:
    """Full-bleed product frame — no text overlay."""
    from apps.content.video_compose import fit_image_to_story_frame

    return fit_image_to_story_frame(
        image_bytes, slide_index=slide_index, source_hint=source_hint,
    )


def parse_cta_text(text: str) -> tuple[str, str]:
    """Split 'price\\ncta' lower-third copy into price + CTA labels."""
    lines = [ln.strip() for ln in (text or "").replace("\r", "").split("\n") if ln.strip()]
    if not lines:
        return "", "Shop on WhatsApp"
    if len(lines) == 1:
        lone = lines[0]
        if any(c in lone for c in ("KES", "Ksh", "$", "€", "£", "₦")) or lone.replace(",", "").replace(".", "").isdigit():
            return lone, "Shop on WhatsApp"
        return "", lone
    return lines[0], lines[-1]


def write_beat_frame(
    dest: Path,
    *,
    role: str,
    text: str,
    image_bytes: bytes,
    brand: BeatFrameBrand | dict | None = None,
    slide_index: int = 0,
    hero_image_bytes: bytes | None = None,
    source_hint: str = "",
) -> None:
    """Write one 9:16 JPEG beat frame based on slide role."""
    role = (role or "").lower()
    hero = hero_image_bytes or image_bytes

    if role == "hook" and text.strip():
        frame = render_hook_beat_frame(
            headline=text.split("\n")[0].strip(),
            brand=brand,
            product_image_bytes=hero,
        )
    elif role == "cta":
        price, cta = parse_cta_text(text)
        frame = render_cta_beat_frame(
            price_label=price,
            cta_label=cta,
            brand=brand,
            product_image_bytes=hero,
        )
    else:
        frame = render_product_beat_frame(
            image_bytes, slide_index=slide_index, source_hint=source_hint,
        )

    frame.save(dest, format="JPEG", quality=93, optimize=True)


def brand_context_for_post(post) -> BeatFrameBrand:
    """Resolve brand DNA from post user profile."""
    from apps.agents.graphics import _get_brand_palette

    profile = getattr(getattr(post, "user", None), "profile", None)
    colors = _get_brand_palette(profile)
    brand_name = ""
    if profile:
        brand_name = getattr(profile, "company_name", "") or ""
    meta = getattr(post, "visual_metadata", None) or {}
    if meta.get("reel_brand_name"):
        brand_name = meta["reel_brand_name"]
    return BeatFrameBrand(
        primary=colors.get("primary", "#1E3A8A"),
        secondary=colors.get("secondary", "#10B981"),
        accent=colors.get("accent", "#F59E0B"),
        brand_name=brand_name,
    )
