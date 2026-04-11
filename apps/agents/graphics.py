"""
Branded Graphics Engine — generates text-overlay visuals using Pillow.

Creates quote cards, tip graphics, stat highlights, and branded content
that FLUX.1 image generation cannot handle (since AI models can't render
reliable text in images).

    generate_branded_graphic(post, graphic_type, text_lines, ...)
        → Creates a MediaAttachment with the rendered image.

Supports:
  - Quote cards (large text on background)
  - Tip graphics (numbered tips with icons)
  - Stat highlights (big number + context)
  - CTA banners (action-oriented promotional graphics)
  - Branded backgrounds for AI images with text overlay
"""

import logging
import textwrap
import uuid
from io import BytesIO
from pathlib import Path

import requests
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont

from apps.content.models import MediaAttachment

logger = logging.getLogger(__name__)

# ─── PLATFORM CANVAS SIZES ───────────────────────────────────────────────────
CANVAS_SIZES = {
    "twitter": (1200, 675),
    "linkedin": (1200, 627),
    "instagram": (1080, 1080),
    "facebook": (1200, 630),
    "tiktok": (1080, 1920),
    "pinterest": (1000, 1500),
    "threads": (1080, 1080),
    "bluesky": (1200, 675),
    "youtube": (1280, 720),
}
DEFAULT_CANVAS = (1200, 675)


# ─── DEFAULT BRAND PALETTE ───────────────────────────────────────────────────
DEFAULT_COLORS = {
    "primary": "#1A1A2E",      # Dark navy
    "secondary": "#16213E",    # Slightly lighter navy
    "accent": "#E94560",       # Coral accent
    "text": "#FFFFFF",         # White text
    "text_muted": "#B0B0B0",  # Muted text for subtitles
}


# ─── GRAPHIC TYPES ────────────────────────────────────────────────────────────

class GraphicType:
    QUOTE_CARD = "quote_card"
    TIP_GRAPHIC = "tip_graphic"
    STAT_HIGHLIGHT = "stat_highlight"
    CTA_BANNER = "cta_banner"


# ─── FONT LOADING ─────────────────────────────────────────────────────────────

def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """
    Load a font at the given size. Uses system fonts with fallbacks.
    """
    # Try common system fonts in order of preference
    # Includes Debian/Ubuntu paths (/usr/share/fonts/) and Nix paths (/nix/store/)
    font_candidates = [
        "arial.ttf", "Arial.ttf",
        "Helvetica.ttf",
        "DejaVuSans.ttf",
        "LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    if bold:
        font_candidates = [
            "arialbd.ttf", "Arial Bold.ttf",
            "Helvetica-Bold.ttf",
            "DejaVuSans-Bold.ttf",
            "LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ] + font_candidates

    # Also search Nix store for fonts (Railway/nixpacks deployment)
    import glob
    nix_dejavu = glob.glob("/nix/store/*/share/fonts/truetype/DejaVuSans*.ttf")
    if nix_dejavu:
        if bold:
            bold_fonts = [f for f in nix_dejavu if "Bold" in f]
            font_candidates = bold_fonts + font_candidates
        regular_fonts = [f for f in nix_dejavu if "Bold" not in f]
        font_candidates = regular_fonts + font_candidates

    for font_name in font_candidates:
        try:
            return ImageFont.truetype(font_name, size)
        except (OSError, IOError):
            continue

    # Fallback: Pillow 10.1+ load_default supports size param for scalable rendering
    logger.warning("No TrueType fonts found — using Pillow default font at size %d. "
                    "Install dejavu or liberation fonts for better results.", size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        # Pillow < 10.1 doesn't support size param
        return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert '#FF5733' to (255, 87, 51). Returns white on invalid input."""
    try:
        hex_color = hex_color.strip().lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join(c * 2 for c in hex_color)
        if len(hex_color) != 6:
            raise ValueError(f"Invalid hex color length: {hex_color}")
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    except (ValueError, AttributeError):
        logger.warning("Invalid hex color '%s', falling back to white", hex_color)
        return (255, 255, 255)


def _get_brand_palette(profile) -> dict:
    """Extract brand colors from user profile, with defaults."""
    colors = dict(DEFAULT_COLORS)
    brand_colors = getattr(profile, "brand_colors", None) or []
    if brand_colors:
        if len(brand_colors) >= 1:
            colors["primary"] = brand_colors[0]
        if len(brand_colors) >= 2:
            colors["accent"] = brand_colors[1]
        if len(brand_colors) >= 3:
            colors["secondary"] = brand_colors[2]
    return colors


# ─── GRADIENT BACKGROUND ─────────────────────────────────────────────────────

def _draw_gradient(draw: ImageDraw.Draw, width: int, height: int,
                   color_top: str, color_bottom: str):
    """Draw a vertical gradient from color_top to color_bottom."""
    r1, g1, b1 = _hex_to_rgb(color_top)
    r2, g2, b2 = _hex_to_rgb(color_bottom)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def _add_accent_bar(draw: ImageDraw.Draw, width: int, height: int,
                    accent_color: str, position: str = "top"):
    """Add a thin accent bar at top or bottom."""
    bar_height = max(int(height * 0.008), 4)
    color = _hex_to_rgb(accent_color)
    if position == "top":
        draw.rectangle([0, 0, width, bar_height], fill=color)
    else:
        draw.rectangle([0, height - bar_height, width, height], fill=color)


# ─── LOGO WATERMARK ──────────────────────────────────────────────────────────

_logo_cache: dict[str, Image.Image | None] = {}


def _fetch_logo(logo_url: str) -> Image.Image | None:
    """Download and cache brand logo from URL. Returns RGBA Image or None."""
    if not logo_url:
        return None
    if logo_url in _logo_cache:
        return _logo_cache[logo_url]
    try:
        resp = requests.get(logo_url, timeout=10)
        resp.raise_for_status()
        if "image" not in resp.headers.get("content-type", ""):
            _logo_cache[logo_url] = None
            return None
        logo = Image.open(BytesIO(resp.content)).convert("RGBA")
        _logo_cache[logo_url] = logo
        return logo
    except Exception as exc:
        logger.debug("Could not fetch brand logo from %s: %s", logo_url, exc)
        _logo_cache[logo_url] = None
        return None


def apply_logo_watermark(img: Image.Image, profile) -> Image.Image:
    """
    Overlay the user's brand logo on the bottom-right of an image.
    Semi-transparent, max 60px tall, with padding from edges.
    """
    logo_url = getattr(profile, "brand_logo_url", "") if profile else ""
    if not logo_url:
        return img

    logo = _fetch_logo(logo_url)
    if logo is None:
        return img

    # Scale logo: max height = 5% of canvas, max width = 15% of canvas
    max_h = max(int(img.height * 0.05), 30)
    max_w = max(int(img.width * 0.15), 80)
    logo_w, logo_h = logo.size
    scale = min(max_w / logo_w, max_h / logo_h, 1.0)
    new_w = int(logo_w * scale)
    new_h = int(logo_h * scale)
    logo_resized = logo.resize((new_w, new_h), Image.LANCZOS)

    # Apply semi-transparency (60% opacity)
    if logo_resized.mode == "RGBA":
        alpha = logo_resized.split()[3]
        alpha = alpha.point(lambda p: int(p * 0.6))
        logo_resized.putalpha(alpha)

    # Position: bottom-right with padding
    padding = int(min(img.width, img.height) * 0.03)
    x = img.width - new_w - padding
    y = img.height - new_h - padding

    # Composite onto the image
    if img.mode != "RGBA":
        img = img.convert("RGBA")
        img.paste(logo_resized, (x, y), logo_resized)
        img = img.convert("RGB")
    else:
        img.paste(logo_resized, (x, y), logo_resized)

    return img


# ─── GRAPHIC GENERATORS ──────────────────────────────────────────────────────

def _render_quote_card(width: int, height: int, text: str,
                       attribution: str, colors: dict) -> Image.Image:
    """
    Quote card: large centered text with optional attribution.
    Great for: inspirational quotes, bold statements, testimonials.
    """
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    # Background gradient
    _draw_gradient(draw, width, height, colors["primary"], colors["secondary"])
    _add_accent_bar(draw, width, height, colors["accent"], "top")
    _add_accent_bar(draw, width, height, colors["accent"], "bottom")

    # Main quote text
    padding_x = int(width * 0.1)
    text_area_width = width - (padding_x * 2)

    # Scale font size based on text length and canvas size
    base_size = int(min(width, height) * 0.07)
    if len(text) > 200:
        base_size = int(base_size * 0.65)
    elif len(text) > 100:
        base_size = int(base_size * 0.8)

    font_main = _get_font(base_size, bold=True)
    font_attr = _get_font(int(base_size * 0.45))

    # Wrap text to fit
    chars_per_line = max(text_area_width // (base_size * 0.55), 15)
    wrapped = textwrap.fill(text, width=int(chars_per_line))

    # Opening quote mark
    quote_font = _get_font(int(base_size * 2.5), bold=True)
    accent_rgb = _hex_to_rgb(colors["accent"])
    draw.text(
        (padding_x, int(height * 0.12)),
        "\u201c", font=quote_font, fill=(*accent_rgb, 180),
    )

    # Center the quote vertically
    bbox = draw.textbbox((0, 0), wrapped, font=font_main)
    text_height = bbox[3] - bbox[1]
    text_y = max((height - text_height) // 2 - int(height * 0.05), int(height * 0.2))

    draw.multiline_text(
        (padding_x, text_y),
        wrapped,
        font=font_main,
        fill=_hex_to_rgb(colors["text"]),
        spacing=int(base_size * 0.4),
    )

    # Attribution
    if attribution:
        attr_text = f"\u2014 {attribution}"
        draw.text(
            (padding_x, text_y + text_height + int(height * 0.04)),
            attr_text,
            font=font_attr,
            fill=_hex_to_rgb(colors["text_muted"]),
        )

    return img


def _render_tip_graphic(width: int, height: int, title: str,
                        tips: list[str], colors: dict) -> Image.Image:
    """
    Tip graphic: numbered tips with title.
    Great for: how-to lists, actionable advice, best practices.
    """
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    _draw_gradient(draw, width, height, colors["primary"], colors["secondary"])
    _add_accent_bar(draw, width, height, colors["accent"], "top")

    padding_x = int(width * 0.08)
    padding_y = int(height * 0.08)

    # Title
    title_size = int(min(width, height) * 0.055)
    font_title = _get_font(title_size, bold=True)
    draw.text(
        (padding_x, padding_y),
        title.upper(),
        font=font_title,
        fill=_hex_to_rgb(colors["accent"]),
    )

    # Divider line
    divider_y = padding_y + title_size + int(height * 0.03)
    draw.line(
        [(padding_x, divider_y), (width - padding_x, divider_y)],
        fill=_hex_to_rgb(colors["accent"]),
        width=3,
    )

    # Tips
    tip_size = int(min(width, height) * 0.035)
    num_size = int(tip_size * 1.3)
    font_tip = _get_font(tip_size)
    font_num = _get_font(num_size, bold=True)

    text_area_width = width - (padding_x * 2) - num_size * 2
    max_tips = min(len(tips), 7)  # Cap at 7 to fit
    available_height = height - divider_y - padding_y * 2
    tip_spacing = min(available_height // max(max_tips, 1), int(height * 0.12))
    tip_y = divider_y + int(height * 0.04)

    for i, tip in enumerate(tips[:max_tips]):
        # Number circle
        accent_rgb = _hex_to_rgb(colors["accent"])
        circle_x = padding_x + int(num_size * 0.6)
        circle_y = tip_y + int(tip_size * 0.4)
        circle_r = int(num_size * 0.5)
        draw.ellipse(
            [circle_x - circle_r, circle_y - circle_r,
             circle_x + circle_r, circle_y + circle_r],
            fill=accent_rgb,
        )
        # Number text centered in circle
        num_text = str(i + 1)
        num_bbox = draw.textbbox((0, 0), num_text, font=font_num)
        num_w = num_bbox[2] - num_bbox[0]
        num_h = num_bbox[3] - num_bbox[1]
        draw.text(
            (circle_x - num_w // 2, circle_y - num_h // 2 - 2),
            num_text,
            font=font_num,
            fill=_hex_to_rgb(colors["text"]),
        )

        # Tip text
        chars_per_line = max(text_area_width // (tip_size * 0.5), 20)
        wrapped_tip = textwrap.fill(tip, width=int(chars_per_line))
        text_x = padding_x + num_size * 2
        draw.multiline_text(
            (text_x, tip_y),
            wrapped_tip,
            font=font_tip,
            fill=_hex_to_rgb(colors["text"]),
            spacing=int(tip_size * 0.3),
        )

        tip_y += tip_spacing

    return img


def _render_stat_highlight(width: int, height: int, stat_number: str,
                           stat_label: str, context: str,
                           colors: dict) -> Image.Image:
    """
    Stat highlight: big number with context.
    Great for: data points, achievements, milestones, impact numbers.
    """
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    _draw_gradient(draw, width, height, colors["primary"], colors["secondary"])
    _add_accent_bar(draw, width, height, colors["accent"], "bottom")

    # Big number
    num_size = int(min(width, height) * 0.2)
    font_num = _get_font(num_size, bold=True)
    num_bbox = draw.textbbox((0, 0), stat_number, font=font_num)
    num_w = num_bbox[2] - num_bbox[0]

    center_x = (width - num_w) // 2
    num_y = int(height * 0.2)

    draw.text(
        (center_x, num_y),
        stat_number,
        font=font_num,
        fill=_hex_to_rgb(colors["accent"]),
    )

    # Label below the number
    label_size = int(min(width, height) * 0.05)
    font_label = _get_font(label_size, bold=True)
    label_bbox = draw.textbbox((0, 0), stat_label.upper(), font=font_label)
    label_w = label_bbox[2] - label_bbox[0]

    draw.text(
        ((width - label_w) // 2, num_y + num_size + int(height * 0.02)),
        stat_label.upper(),
        font=font_label,
        fill=_hex_to_rgb(colors["text"]),
    )

    # Context text
    if context:
        ctx_size = int(min(width, height) * 0.03)
        font_ctx = _get_font(ctx_size)
        padding_x = int(width * 0.15)
        chars_per_line = max((width - padding_x * 2) // (ctx_size * 0.5), 20)
        wrapped_ctx = textwrap.fill(context, width=int(chars_per_line))
        ctx_bbox = draw.textbbox((0, 0), wrapped_ctx, font=font_ctx)
        ctx_w = ctx_bbox[2] - ctx_bbox[0]
        ctx_y = num_y + num_size + label_size + int(height * 0.08)
        draw.multiline_text(
            ((width - ctx_w) // 2, ctx_y),
            wrapped_ctx,
            font=font_ctx,
            fill=_hex_to_rgb(colors["text_muted"]),
            align="center",
            spacing=int(ctx_size * 0.4),
        )

    return img


def _render_cta_banner(width: int, height: int, headline: str,
                       subtext: str, cta_text: str,
                       colors: dict) -> Image.Image:
    """
    CTA banner: headline + subtext + action button.
    Great for: promotions, announcements, event invites, product launches.
    """
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    _draw_gradient(draw, width, height, colors["primary"], colors["secondary"])

    padding_x = int(width * 0.1)

    # Headline
    hl_size = int(min(width, height) * 0.07)
    font_hl = _get_font(hl_size, bold=True)
    chars_per_line = max((width - padding_x * 2) // (hl_size * 0.55), 10)
    wrapped_hl = textwrap.fill(headline, width=int(chars_per_line))

    hl_y = int(height * 0.2)
    draw.multiline_text(
        (padding_x, hl_y),
        wrapped_hl,
        font=font_hl,
        fill=_hex_to_rgb(colors["text"]),
        spacing=int(hl_size * 0.3),
    )

    # Subtext
    hl_bbox = draw.textbbox((0, 0), wrapped_hl, font=font_hl)
    hl_height = hl_bbox[3] - hl_bbox[1]
    sub_y = hl_y + hl_height + int(height * 0.05)

    if subtext:
        sub_size = int(min(width, height) * 0.035)
        font_sub = _get_font(sub_size)
        sub_chars = max((width - padding_x * 2) // (sub_size * 0.5), 15)
        wrapped_sub = textwrap.fill(subtext, width=int(sub_chars))
        draw.multiline_text(
            (padding_x, sub_y),
            wrapped_sub,
            font=font_sub,
            fill=_hex_to_rgb(colors["text_muted"]),
            spacing=int(sub_size * 0.3),
        )
        sub_bbox = draw.textbbox((0, 0), wrapped_sub, font=font_sub)
        sub_height = sub_bbox[3] - sub_bbox[1]
        btn_y = sub_y + sub_height + int(height * 0.06)
    else:
        btn_y = sub_y + int(height * 0.06)

    # CTA button
    if cta_text:
        btn_size = int(min(width, height) * 0.04)
        font_btn = _get_font(btn_size, bold=True)
        btn_bbox = draw.textbbox((0, 0), cta_text.upper(), font=font_btn)
        btn_w = btn_bbox[2] - btn_bbox[0]
        btn_h = btn_bbox[3] - btn_bbox[1]
        btn_pad_x = int(btn_w * 0.4)
        btn_pad_y = int(btn_h * 0.6)

        accent_rgb = _hex_to_rgb(colors["accent"])
        # Rounded rectangle button
        draw.rounded_rectangle(
            [padding_x, btn_y,
             padding_x + btn_w + btn_pad_x * 2, btn_y + btn_h + btn_pad_y * 2],
            radius=int(btn_h * 0.4),
            fill=accent_rgb,
        )
        draw.text(
            (padding_x + btn_pad_x, btn_y + btn_pad_y),
            cta_text.upper(),
            font=font_btn,
            fill=_hex_to_rgb(colors["text"]),
        )

    return img


# ─── RENDER DISPATCH ──────────────────────────────────────────────────────────

RENDERERS = {
    GraphicType.QUOTE_CARD: _render_quote_card,
    GraphicType.TIP_GRAPHIC: _render_tip_graphic,
    GraphicType.STAT_HIGHLIGHT: _render_stat_highlight,
    GraphicType.CTA_BANNER: _render_cta_banner,
}


# ─── PUBLIC API ───────────────────────────────────────────────────────────────

def generate_branded_graphic(
    post,
    graphic_type: str,
    *,
    text: str = "",
    attribution: str = "",
    tips: list[str] | None = None,
    stat_number: str = "",
    stat_label: str = "",
    context: str = "",
    headline: str = "",
    subtext: str = "",
    cta_text: str = "",
) -> str | None:
    """
    Generate a branded graphic and attach it to the post.

    Args:
        post: Post instance
        graphic_type: One of GraphicType constants
        **kwargs: Type-specific content (text, tips, stat_number, etc.)

    Returns:
        URL of the saved image, or None if rendering failed.
    """
    platform = post.social_account.platform if post.social_account else "twitter"
    width, height = CANVAS_SIZES.get(platform, DEFAULT_CANVAS)

    # Load brand colors from user profile
    profile = getattr(post.user, "profile", None)
    colors = _get_brand_palette(profile)

    renderer = RENDERERS.get(graphic_type)
    if not renderer:
        logger.warning("Unknown graphic type: %s", graphic_type)
        return None

    try:
        # Build kwargs for the specific renderer
        if graphic_type == GraphicType.QUOTE_CARD:
            img = renderer(width, height, text, attribution, colors)
        elif graphic_type == GraphicType.TIP_GRAPHIC:
            img = renderer(width, height, text or headline, tips or [], colors)
        elif graphic_type == GraphicType.STAT_HIGHLIGHT:
            img = renderer(width, height, stat_number, stat_label, context, colors)
        elif graphic_type == GraphicType.CTA_BANNER:
            img = renderer(width, height, headline, subtext, cta_text, colors)
        else:
            return None

        # Apply brand logo watermark
        img = apply_logo_watermark(img, profile)

        # Save to bytes
        buffer = BytesIO()
        img.save(buffer, format="PNG", compress_level=6)
        buffer.seek(0)

        # Create MediaAttachment
        filename = f"graphic_{uuid.uuid4().hex[:12]}.png"
        filepath = f"graphics/{filename}"
        attachment = MediaAttachment(
            post=post,
            file_type="image",
            alt_text=f"{graphic_type}: {text[:200] or headline[:200] or stat_label[:200]}",
            order=0,
        )
        attachment.file.save(filepath, ContentFile(buffer.read()), save=True)

        # Update post media_urls
        media_url = attachment.file.url
        if not post.media_urls:
            post.media_urls = []
        post.media_urls.append(media_url)
        post.media_status = "generated"
        post.save(update_fields=["media_urls", "media_status", "updated_at"])

        logger.info("Generated %s graphic for post %s", graphic_type, post.id)
        return media_url

    except Exception as exc:
        logger.exception("Branded graphic generation failed for post %s: %s", post.id, exc)
        return None
