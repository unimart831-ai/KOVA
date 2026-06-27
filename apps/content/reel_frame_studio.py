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
    """Closing beat — price + CTA on designed card (never over product pixels)."""
    brand = _brand_from_context(brand)
    w, h = STORY_WIDTH, STORY_HEIGHT
    primary = _hex_to_rgb(brand.primary)
    secondary = _hex_to_rgb(brand.secondary)
    accent = _hex_to_rgb(brand.accent)

    canvas = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(canvas)
    _draw_vertical_gradient(draw, w, h, (8, 12, 24), primary)

    card_h = int(h * 0.42)
    card_y = int(h * 0.30)
    card_margin = int(w * 0.08)
    draw.rounded_rectangle(
        [(card_margin, card_y), (w - card_margin, card_y + card_h)],
        radius=28,
        fill=(255, 255, 255),
    )

    if product_image_bytes:
        try:
            thumb = Image.open(BytesIO(product_image_bytes)).convert("RGB")
            thumb_size = int(w * 0.28)
            thumb = ImageOps.fit(thumb, (thumb_size, thumb_size), method=Image.LANCZOS)
            thumb_x = w - card_margin - thumb_size - int(w * 0.04)
            thumb_y = card_y + int(card_h * 0.12)
            mask = Image.new("L", (thumb_size, thumb_size), 0)
            mdraw = ImageDraw.Draw(mask)
            mdraw.rounded_rectangle([(0, 0), (thumb_size, thumb_size)], radius=16, fill=255)
            canvas.paste(thumb, (thumb_x, thumb_y), mask)
        except Exception:
            pass

    inner_x = card_margin + int(w * 0.06)
    inner_y = card_y + int(card_h * 0.14)
    price = (price_label or "").strip()
    cta = (cta_label or "Shop on WhatsApp").strip()[:36]

    if price:
        price_font = _get_font(int(h * 0.052), bold=True)
        draw.text((inner_x, inner_y), price, font=price_font, fill=primary)

    cta_font = _get_font(int(h * 0.034), bold=True)
    cta_y = inner_y + (int(h * 0.07) if price else 0)
    btn_h = int(h * 0.055)
    btn_w = int(w * 0.52)
    draw.rounded_rectangle(
        [(inner_x, cta_y), (inner_x + btn_w, cta_y + btn_h)],
        radius=14,
        fill=secondary,
    )
    cta_bbox = draw.textbbox((0, 0), cta, font=cta_font)
    cw = cta_bbox[2] - cta_bbox[0]
    ch = cta_bbox[3] - cta_bbox[1]
    draw.text(
        (inner_x + (btn_w - cw) // 2, cta_y + (btn_h - ch) // 2 - 2),
        cta,
        font=cta_font,
        fill=(255, 255, 255),
    )

    if brand.brand_name:
        foot_font = _get_font(int(h * 0.026))
        draw.text(
            (inner_x, card_y + card_h - int(h * 0.055)),
            brand.brand_name,
            font=foot_font,
            fill=(100, 110, 130),
        )

    accent_bar = int(w * 0.12)
    draw.rounded_rectangle(
        [(w - accent_bar) // 2, h - int(h * 0.12), (w + accent_bar) // 2, h - int(h * 0.12) + 5],
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
    elif role == "cta" and text.strip():
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
