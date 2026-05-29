"""
Carousel Generator — creates multi-slide visual content.

Generates 2-10 branded slides from structured content (tips, listicles,
how-tos, storytelling threads). Each slide is a self-contained graphic
rendered with the branded graphics engine.

Instagram carousels get 1.4x more reach than single images.
LinkedIn carousels get 3x engagement.

    generate_carousel(post, slides_data, ...)
        → Creates multiple MediaAttachments for the post.
"""

import logging
import uuid
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageOps

from apps.agents.graphics import (
    CANVAS_SIZES,
    DEFAULT_CANVAS,
    GraphicType,
    _add_accent_bar,
    _draw_gradient,
    _get_brand_palette,
    _get_font,
    _hex_to_rgb,
    _render_cta_banner,
    _render_quote_card,
    _render_stat_highlight,
    _render_tip_graphic,
    apply_logo_watermark,
)
from apps.content.models import MediaAttachment

logger = logging.getLogger(__name__)


def _render_title_slide(width: int, height: int, title: str,
                        subtitle: str, colors: dict) -> Image.Image:
    """Opening slide: big title + subtitle. Sets the hook."""
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    _draw_gradient(draw, width, height, colors["primary"], colors["secondary"])
    _add_accent_bar(draw, width, height, colors["accent"], "top")
    _add_accent_bar(draw, width, height, colors["accent"], "bottom")

    import textwrap

    padding_x = int(width * 0.1)

    # Title
    title_size = int(min(width, height) * 0.08)
    font_title = _get_font(title_size, bold=True)
    chars = max((width - padding_x * 2) // (title_size * 0.55), 10)
    wrapped = textwrap.fill(title, width=int(chars))

    bbox = draw.textbbox((0, 0), wrapped, font=font_title)
    text_h = bbox[3] - bbox[1]
    y = (height - text_h) // 2 - int(height * 0.08)

    draw.multiline_text(
        (padding_x, y), wrapped, font=font_title,
        fill=_hex_to_rgb(colors["text"]),
        spacing=int(title_size * 0.4),
    )

    # Subtitle
    if subtitle:
        sub_size = int(min(width, height) * 0.035)
        font_sub = _get_font(sub_size)
        sub_chars = max((width - padding_x * 2) // (sub_size * 0.5), 15)
        wrapped_sub = textwrap.fill(subtitle, width=int(sub_chars))
        draw.multiline_text(
            (padding_x, y + text_h + int(height * 0.04)),
            wrapped_sub, font=font_sub,
            fill=_hex_to_rgb(colors["text_muted"]),
            spacing=int(sub_size * 0.3),
        )

    # Swipe indicator
    swipe_size = int(min(width, height) * 0.025)
    font_swipe = _get_font(swipe_size)
    swipe_text = "Swipe \u2192"
    swipe_bbox = draw.textbbox((0, 0), swipe_text, font=font_swipe)
    swipe_w = swipe_bbox[2] - swipe_bbox[0]
    draw.text(
        (width - padding_x - swipe_w, height - int(height * 0.08)),
        swipe_text, font=font_swipe,
        fill=_hex_to_rgb(colors["accent"]),
    )

    return img


def _render_content_slide(width: int, height: int, slide_number: int,
                          total_slides: int, content: str,
                          slide_title: str, colors: dict) -> Image.Image:
    """Individual content slide with number indicator."""
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    import textwrap

    _draw_gradient(draw, width, height, colors["primary"], colors["secondary"])

    padding_x = int(width * 0.08)
    padding_y = int(height * 0.08)

    # Slide number (top-left)
    num_size = int(min(width, height) * 0.04)
    font_num = _get_font(num_size, bold=True)
    draw.text(
        (padding_x, padding_y),
        f"{slide_number}/{total_slides}",
        font=font_num,
        fill=_hex_to_rgb(colors["accent"]),
    )

    # Slide title (if provided)
    title_y = padding_y + num_size + int(height * 0.03)
    if slide_title:
        title_size = int(min(width, height) * 0.05)
        font_title = _get_font(title_size, bold=True)
        draw.text(
            (padding_x, title_y),
            slide_title,
            font=font_title,
            fill=_hex_to_rgb(colors["text"]),
        )
        content_y = title_y + title_size + int(height * 0.03)
    else:
        content_y = title_y

    # Content text
    content_size = int(min(width, height) * 0.038)
    font_content = _get_font(content_size)
    text_area_width = width - (padding_x * 2)
    chars = max(text_area_width // (content_size * 0.5), 15)
    wrapped = textwrap.fill(content, width=int(chars))

    draw.multiline_text(
        (padding_x, content_y),
        wrapped,
        font=font_content,
        fill=_hex_to_rgb(colors["text"]),
        spacing=int(content_size * 0.5),
    )

    # Bottom accent bar
    _add_accent_bar(draw, width, height, colors["accent"], "bottom")

    return img


def _render_closing_slide(width: int, height: int, cta_text: str,
                          brand_name: str, colors: dict) -> Image.Image:
    """Closing slide: CTA + brand name. Drives action."""
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    _draw_gradient(draw, width, height, colors["primary"], colors["secondary"])
    _add_accent_bar(draw, width, height, colors["accent"], "top")
    _add_accent_bar(draw, width, height, colors["accent"], "bottom")

    # CTA text
    cta_size = int(min(width, height) * 0.06)
    font_cta = _get_font(cta_size, bold=True)
    cta_bbox = draw.textbbox((0, 0), cta_text, font=font_cta)
    cta_w = cta_bbox[2] - cta_bbox[0]
    cta_h = cta_bbox[3] - cta_bbox[1]

    cta_y = (height - cta_h) // 2 - int(height * 0.05)
    draw.text(
        ((width - cta_w) // 2, cta_y),
        cta_text,
        font=font_cta,
        fill=_hex_to_rgb(colors["accent"]),
    )

    # Brand name
    if brand_name:
        brand_size = int(min(width, height) * 0.035)
        font_brand = _get_font(brand_size)
        brand_bbox = draw.textbbox((0, 0), brand_name, font=font_brand)
        brand_w = brand_bbox[2] - brand_bbox[0]
        draw.text(
            ((width - brand_w) // 2, cta_y + cta_h + int(height * 0.06)),
            brand_name,
            font=font_brand,
            fill=_hex_to_rgb(colors["text_muted"]),
        )

    return img


# ─── PUBLIC API ───────────────────────────────────────────────────────────────

def generate_carousel(
    post,
    slides: list[dict],
    *,
    title: str = "",
    subtitle: str = "",
    closing_cta: str = "Follow for more",
) -> list[str]:
    """
    Generate a multi-slide carousel and attach all images to the post.

    Args:
        post: Post instance
        slides: List of dicts with keys:
            - content (str): Main text for the slide
            - title (str, optional): Slide heading
            - type (str, optional): 'quote', 'tip', 'stat', or 'content' (default)
            For 'stat' type: stat_number, stat_label
        title: Opening slide title
        subtitle: Opening slide subtitle
        closing_cta: CTA text for the closing slide

    Returns:
        List of media URLs for all slides.
    """
    if not slides:
        return []

    # Filter out empty slides and cap at 10 to prevent runaway generation
    slides = [s for s in slides if s.get("content", "").strip()]
    if not slides:
        logger.warning("Carousel slides all empty for post %s", post.id)
        return []
    slides = slides[:10]

    platform = post.platform or (post.social_account.platform if post.social_account else "instagram")
    width, height = CANVAS_SIZES.get(platform, DEFAULT_CANVAS)

    # Use square for carousel-native platforms
    if platform in ("instagram", "threads"):
        width, height = 1080, 1080

    profile = getattr(post.user, "profile", None)
    colors = _get_brand_palette(profile)
    brand_name = getattr(profile, "company_name", "") if profile else ""

    total_slides = len(slides) + (1 if title else 0) + 1  # +1 for closing
    media_urls = []

    try:
        slide_images = []

        # Title slide
        if title:
            slide_images.append(
                _render_title_slide(width, height, title, subtitle, colors)
            )

        # Content slides
        for i, slide_data in enumerate(slides):
            slide_num = i + (2 if title else 1)
            slide_type = slide_data.get("type", "content")
            slide_title_text = slide_data.get("title", "")
            content = slide_data.get("content", "")

            if slide_type == "quote":
                img = _render_quote_card(
                    width, height, content,
                    slide_data.get("attribution", ""), colors,
                )
            elif slide_type == "stat":
                img = _render_stat_highlight(
                    width, height,
                    slide_data.get("stat_number", ""),
                    slide_data.get("stat_label", ""),
                    content, colors,
                )
            elif slide_type == "tip":
                img = _render_tip_graphic(
                    width, height, slide_title_text,
                    [content], colors,
                )
            else:
                img = _render_content_slide(
                    width, height, slide_num, total_slides,
                    content, slide_title_text, colors,
                )
            slide_images.append(img)

        # Closing slide
        slide_images.append(
            _render_closing_slide(width, height, closing_cta, brand_name, colors)
        )

        # Save all slides as MediaAttachments
        for idx, img in enumerate(slide_images):
            # Apply brand logo watermark to each slide
            img = apply_logo_watermark(img, profile)

            buffer = BytesIO()
            img.save(buffer, format="PNG", compress_level=6)
            buffer.seek(0)

            filename = f"carousel_{uuid.uuid4().hex[:8]}_s{idx + 1}.png"
            filepath = f"carousels/{filename}"
            attachment = MediaAttachment(
                post=post,
                file_type="image",
                alt_text=f"Carousel slide {idx + 1}/{len(slide_images)}",
                order=idx,
            )
            attachment.file.save(filepath, ContentFile(buffer.read()), save=True)
            from apps.content.tasks import _public_url_for_file
            public_url = _public_url_for_file(attachment.file.name)
            media_urls.append(public_url or attachment.file.url)

        # Update post
        if not post.media_urls:
            post.media_urls = []
        post.media_urls.extend(media_urls)
        post.media_status = "generated"
        post.save(update_fields=["media_urls", "media_status", "updated_at"])

        logger.info(
            "Generated %d-slide carousel for post %s (%s)",
            len(slide_images), post.id, platform,
        )
        return media_urls

    except Exception as exc:
        logger.exception("Carousel generation failed for post %s: %s", post.id, exc)
        return []


# ─── PRODUCT PHOTO CAROUSEL ───────────────────────────────────────────────────

def _load_product_image(image_source: str):
    """
    Load a PIL Image from a URL, data URI, relative path, or absolute file path.
    Returns None if loading fails for any reason.
    """
    from io import BytesIO as _BytesIO

    if not image_source:
        return None

    try:
        if image_source.startswith("data:"):
            import base64
            _header, b64data = image_source.split(",", 1)
            raw = base64.b64decode(b64data)
            img = Image.open(_BytesIO(raw))
        elif image_source.startswith(("http://", "https://")):
            import requests
            resp = requests.get(image_source, timeout=12)
            resp.raise_for_status()
            img = Image.open(_BytesIO(resp.content))
        elif image_source.startswith("/"):
            from apps.content.tasks import _public_url_for_file

            rel = image_source.lstrip("/")
            if rel.startswith("media/"):
                rel = rel[6:]
            public = _public_url_for_file(rel)
            if public:
                import requests
                resp = requests.get(public, timeout=12)
                resp.raise_for_status()
                img = Image.open(_BytesIO(resp.content))
            else:
                raise FileNotFoundError(f"No public URL for {image_source[:80]}")
        else:
            from django.core.files.storage import default_storage
            try:
                with default_storage.open(image_source.lstrip("/")) as f:
                    img = Image.open(_BytesIO(f.read()))
            except Exception:
                img = Image.open(image_source)

        from apps.products.image_utils import apply_exif_orientation

        img = apply_exif_orientation(img)
        return img.convert("RGB")

    except Exception as exc:
        logger.warning("Could not load product image %r: %s", image_source[:80], exc)
        return None


def _wrap_text(draw, text: str, font, max_width: int) -> str:
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


def _render_product_hero_hook_slide(
    width: int,
    height: int,
    image_source: str,
    headline: str,
    subtext: str,
    colors: dict,
    *,
    badge: str = "",
    slide_num: int = 1,
    total_slides: int = 1,
) -> Image.Image:
    raw = _load_product_image(image_source)
    if raw is None:
        return _render_title_slide(width, height, headline, subtext, colors)

    img = ImageOps.fit(raw, (width, height), method=Image.Resampling.LANCZOS).convert("RGBA")
    strip_h = int(height * 0.30)
    gradient = Image.new("RGBA", (width, strip_h), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(gradient)
    for y in range(strip_h):
        g_draw.rectangle(
            [(0, y), (width, y + 1)],
            fill=(0, 0, 0, int(150 * (y / strip_h))),
        )
    img.paste(gradient, (0, height - strip_h), gradient)
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)
    padding_x = int(width * 0.07)
    text_y_base = height - strip_h + int(height * 0.04)

    if badge:
        badge_size = int(min(width, height) * 0.028)
        font_badge = _get_font(badge_size, bold=True)
        badge_text = badge.upper()
        bb = draw.textbbox((0, 0), badge_text, font=font_badge)
        bw, bh = bb[2] - bb[0], bb[3] - bb[1]
        bx, by = padding_x, text_y_base - int(height * 0.10)
        draw.rounded_rectangle(
            [(bx - 8, by - 4), (bx + bw + 8, by + bh + 4)],
            radius=8,
            fill=_hex_to_rgb(colors["accent"]),
        )
        draw.text((bx, by), badge_text, font=font_badge, fill=(255, 255, 255))

    title_size = int(min(width, height) * 0.058)
    font_title = _get_font(title_size, bold=True)
    wrapped_title = _wrap_text(draw, headline, font_title, width - padding_x * 2)
    draw.multiline_text(
        (padding_x, text_y_base),
        wrapped_title,
        font=font_title,
        fill=(255, 255, 255),
        spacing=int(title_size * 0.2),
    )

    if subtext:
        sub_size = int(min(width, height) * 0.032)
        font_sub = _get_font(sub_size)
        wrapped_sub = _wrap_text(draw, subtext, font_sub, width - padding_x * 2)
        title_bbox = draw.multiline_textbbox(
            (padding_x, text_y_base), wrapped_title, font=font_title,
            spacing=int(title_size * 0.2),
        )
        draw.multiline_text(
            (padding_x, title_bbox[3] + int(height * 0.015)),
            wrapped_sub,
            font=font_sub,
            fill=(220, 220, 230),
            spacing=int(sub_size * 0.25),
        )

    draw.text(
        (padding_x, height - int(height * 0.08)),
        f"{slide_num}/{total_slides}  ·  Swipe →",
        font=_get_font(int(min(width, height) * 0.028), bold=True),
        fill=_hex_to_rgb(colors["accent"]),
    )
    return img


def _render_product_story_slide(
    width: int,
    height: int,
    image_source: str,
    headline: str,
    body: str,
    colors: dict,
    *,
    slide_num: int,
    total_slides: int,
) -> Image.Image:
    raw = _load_product_image(image_source)
    if raw is None:
        return _render_content_slide(width, height, slide_num, total_slides, body, headline, colors)

    img = ImageOps.fit(raw, (width, height), method=Image.Resampling.LANCZOS).convert("RGBA")
    card_h = int(height * 0.28)
    card = Image.new("RGBA", (width, card_h), (26, 26, 46, 195))
    img.paste(card, (0, height - card_h), card)
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)
    padding_x = int(width * 0.08)
    card_top = height - card_h + int(height * 0.04)

    font_label = _get_font(int(min(width, height) * 0.028), bold=True)
    draw.text(
        (padding_x, card_top),
        headline.upper(),
        font=font_label,
        fill=_hex_to_rgb(colors["accent"]),
    )

    body_size = int(min(width, height) * 0.036)
    font_body = _get_font(body_size)
    wrapped = _wrap_text(draw, body, font_body, width - padding_x * 2)
    label_bbox = draw.textbbox((padding_x, card_top), headline.upper(), font=font_label)
    draw.multiline_text(
        (padding_x, label_bbox[3] + int(height * 0.02)),
        wrapped,
        font=font_body,
        fill=(255, 255, 255),
        spacing=int(body_size * 0.35),
    )

    draw.text(
        (padding_x, height - int(height * 0.06)),
        f"{slide_num}/{total_slides}",
        font=_get_font(int(min(width, height) * 0.028), bold=True),
        fill=_hex_to_rgb(colors["accent"]),
    )
    return img


def _render_product_benefit_slide(
    width: int,
    height: int,
    image_source: str,
    headline: str,
    body: str,
    colors: dict,
    *,
    layout: str,
    slide_num: int,
    total_slides: int,
) -> Image.Image:
    raw = _load_product_image(image_source)
    if raw is None:
        return _render_content_slide(width, height, slide_num, total_slides, headline, "", colors)

    img = ImageOps.fit(raw, (width, height), method=Image.Resampling.LANCZOS).convert("RGBA")
    padding_x = int(width * 0.07)

    if layout == "benefit_side":
        panel_w = int(width * 0.52)
        panel = Image.new("RGBA", (panel_w, height), (0, 0, 0, 180))
        img.paste(panel, (0, 0), panel)
        text_x, text_max_w, text_y = padding_x, panel_w - padding_x * 2, int(height * 0.28)
    elif layout == "benefit_badge":
        badge_h = int(height * 0.24)
        gradient = Image.new("RGBA", (width, badge_h), (0, 0, 0, 0))
        g_draw = ImageDraw.Draw(gradient)
        for y in range(badge_h):
            g_draw.rectangle([(0, y), (width, y + 1)], fill=(0, 0, 0, int(140 * (y / badge_h))))
        img.paste(gradient, (0, height - badge_h), gradient)
        text_x, text_max_w = padding_x, width - padding_x * 2
        text_y = height - badge_h + int(height * 0.05)
    else:
        overlay_h = int(height * 0.22)
        gradient = Image.new("RGBA", (width, overlay_h), (0, 0, 0, 0))
        g_draw = ImageDraw.Draw(gradient)
        for y in range(overlay_h):
            g_draw.rectangle([(0, y), (width, y + 1)], fill=(0, 0, 0, int(150 * (y / overlay_h))))
        img.paste(gradient, (0, height - overlay_h), gradient)
        text_x, text_max_w = padding_x, width - padding_x * 2
        text_y = height - overlay_h + int(height * 0.04)

    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)
    title_size = int(min(width, height) * 0.048)
    font_title = _get_font(title_size, bold=True)
    wrapped = _wrap_text(draw, headline, font_title, text_max_w)
    draw.multiline_text(
        (text_x, text_y), wrapped, font=font_title, fill=(255, 255, 255),
        spacing=int(title_size * 0.25),
    )

    if body:
        body_size = int(min(width, height) * 0.030)
        font_body = _get_font(body_size)
        title_bbox = draw.multiline_textbbox((text_x, text_y), wrapped, font=font_title)
        wrapped_body = _wrap_text(draw, body, font_body, text_max_w)
        draw.multiline_text(
            (text_x, title_bbox[3] + int(height * 0.02)),
            wrapped_body,
            font=font_body,
            fill=_hex_to_rgb(colors["text_muted"]),
            spacing=int(body_size * 0.3),
        )

    draw.text(
        (padding_x, int(height * 0.05)),
        f"{slide_num}/{total_slides}",
        font=_get_font(int(min(width, height) * 0.028), bold=True),
        fill=_hex_to_rgb(colors["accent"]),
    )
    return img


def _render_product_price_slide(
    width: int,
    height: int,
    image_source: str,
    price: str,
    body: str,
    subtext: str,
    colors: dict,
    *,
    slide_num: int,
    total_slides: int,
) -> Image.Image:
    raw = _load_product_image(image_source)
    if raw is None:
        return _render_closing_slide(width, height, price, subtext, colors)

    img = ImageOps.fit(raw, (width, height), method=Image.Resampling.LANCZOS).convert("RGBA")
    dim = Image.new("RGBA", (width, height), (0, 0, 0, 45))
    img = Image.alpha_composite(img, dim).convert("RGB")
    draw = ImageDraw.Draw(img)
    padding_x = int(width * 0.08)

    price_size = int(min(width, height) * 0.10)
    font_price = _get_font(price_size, bold=True)
    pb = draw.textbbox((0, 0), price, font=font_price)
    pw, ph = pb[2] - pb[0], pb[3] - pb[1]
    px = (width - pw) // 2
    py = int(height * 0.32)
    draw.rounded_rectangle(
        [(px - 20, py - 12), (px + pw + 20, py + ph + 12)],
        radius=16,
        fill=_hex_to_rgb(colors["accent"]),
    )
    draw.text((px, py), price, font=font_price, fill=(255, 255, 255))

    if subtext:
        sub_size = int(min(width, height) * 0.034)
        font_sub = _get_font(sub_size, bold=True)
        sb = draw.textbbox((0, 0), subtext, font=font_sub)
        sw = sb[2] - sb[0]
        draw.text(((width - sw) // 2, py + ph + int(height * 0.04)), subtext, font=font_sub, fill=(255, 255, 255))

    if body:
        body_size = int(min(width, height) * 0.032)
        font_body = _get_font(body_size)
        wrapped = _wrap_text(draw, body, font_body, width - padding_x * 2)
        bb = draw.multiline_textbbox((0, 0), wrapped, font=font_body)
        bw = bb[2] - bb[0]
        draw.multiline_text(
            ((width - bw) // 2, int(height * 0.62)),
            wrapped,
            font=font_body,
            fill=_hex_to_rgb(colors["text_muted"]),
            spacing=int(body_size * 0.3),
        )

    draw.text(
        (padding_x, height - int(height * 0.06)),
        f"{slide_num}/{total_slides}",
        font=_get_font(int(min(width, height) * 0.028), bold=True),
        fill=_hex_to_rgb(colors["accent"]),
    )
    return img


def _render_photo_slide(
    width: int,
    height: int,
    image_source: str,
    overlay_text: str,
    colors: dict,
    *,
    slide_num: int | None = None,
    total_slides: int | None = None,
    is_first: bool = False,
) -> Image.Image:
    """
    Product photo slide: cover-cropped image + dark bottom gradient + white text.
    Falls back to a brand-colored content slide if the image cannot be loaded.
    """
    import textwrap

    raw = _load_product_image(image_source)
    if raw is None:
        if is_first:
            return _render_title_slide(width, height, overlay_text, "", colors)
        return _render_content_slide(
            width, height,
            slide_num or 1,
            total_slides or 1,
            overlay_text, "", colors,
        )

    # Cover-crop to exact canvas size
    img = ImageOps.fit(raw, (width, height), method=Image.Resampling.LANCZOS)
    img = img.convert("RGBA")

    # Bottom text strip — keep most of the product visible
    overlay_h = int(height * 0.22)
    overlay_start = height - overlay_h
    gradient = Image.new("RGBA", (width, overlay_h), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(gradient)
    for y in range(overlay_h):
        alpha = int(130 * (y / overlay_h))
        g_draw.rectangle([(0, y), (width, y + 1)], fill=(0, 0, 0, alpha))
    img.paste(gradient, (0, overlay_start), gradient)

    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)

    padding_x = int(width * 0.07)

    # Slide counter (top-left, accent color)
    if slide_num is not None and total_slides is not None:
        num_size = int(min(width, height) * 0.032)
        font_num = _get_font(num_size, bold=True)
        draw.text(
            (padding_x, int(height * 0.06)),
            f"{slide_num}/{total_slides}",
            font=font_num,
            fill=_hex_to_rgb(colors["accent"]),
        )

    # Main overlay text — white, bold, bottom of gradient zone
    text_size = int(min(width, height) * 0.055)
    font_text = _get_font(text_size, bold=True)
    text_area_w = width - padding_x * 2
    chars = max(text_area_w // max(int(text_size * 0.55), 1), 10)
    wrapped = textwrap.fill(overlay_text, width=int(chars))

    text_bbox = draw.textbbox((0, 0), wrapped, font=font_text)
    text_h = text_bbox[3] - text_bbox[1]
    text_y = height - int(height * 0.06) - text_h - (int(height * 0.05) if is_first else 0)

    draw.multiline_text(
        (padding_x, text_y),
        wrapped,
        font=font_text,
        fill=(255, 255, 255),
        spacing=int(text_size * 0.35),
    )

    # "Swipe →" hint on the first slide
    if is_first:
        swipe_size = int(min(width, height) * 0.025)
        font_swipe = _get_font(swipe_size)
        swipe_text = "Swipe →"
        swipe_bbox = draw.textbbox((0, 0), swipe_text, font=font_swipe)
        swipe_w = swipe_bbox[2] - swipe_bbox[0]
        draw.text(
            (width - padding_x - swipe_w, height - int(height * 0.04)),
            swipe_text,
            font=font_swipe,
            fill=_hex_to_rgb(colors["accent"]),
        )

    return img


def _render_clean_split_slide(
    width: int,
    height: int,
    image_source: str,
    headline: str,
    body: str,
    colors: dict,
    *,
    slide_num: int,
    total_slides: int,
) -> Image.Image:
    """Product-first: image top 72%, branded text bar bottom 28%. No overlay on product."""
    raw = _load_product_image(image_source)
    if raw is None:
        return _render_content_slide(width, height, slide_num, total_slides, headline, body, colors)

    img_zone_h = int(height * 0.72)
    bar_h = height - img_zone_h

    product_img = ImageOps.fit(raw, (width, img_zone_h), method=Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (width, height), _hex_to_rgb(colors["primary"]))
    canvas.paste(product_img, (0, 0))

    draw = ImageDraw.Draw(canvas)
    padding_x = int(width * 0.07)

    title_size = int(min(width, height) * 0.046)
    font_title = _get_font(title_size, bold=True)
    title_y = img_zone_h + int(bar_h * 0.18)
    wrapped_title = _wrap_text(draw, headline, font_title, width - padding_x * 2)
    draw.multiline_text(
        (padding_x, title_y), wrapped_title, font=font_title,
        fill=(255, 255, 255), spacing=int(title_size * 0.2),
    )

    if body:
        body_size = int(min(width, height) * 0.030)
        font_body = _get_font(body_size)
        title_bbox = draw.multiline_textbbox(
            (padding_x, title_y), wrapped_title, font=font_title, spacing=int(title_size * 0.2),
        )
        body_y = title_bbox[3] + int(bar_h * 0.08)
        wrapped_body = _wrap_text(draw, body, font_body, width - padding_x * 2)
        draw.multiline_text(
            (padding_x, body_y), wrapped_body, font=font_body,
            fill=_hex_to_rgb(colors["text_muted"]), spacing=int(body_size * 0.25),
        )

    counter_size = int(min(width, height) * 0.024)
    font_counter = _get_font(counter_size, bold=True)
    draw.text(
        (padding_x, height - int(bar_h * 0.25)),
        f"{slide_num}/{total_slides}",
        font=font_counter,
        fill=_hex_to_rgb(colors["accent"]),
    )

    return canvas


def _render_side_panel_slide(
    width: int,
    height: int,
    image_source: str,
    headline: str,
    body: str,
    colors: dict,
    *,
    slide_num: int,
    total_slides: int,
) -> Image.Image:
    """Product-first: image left 58%, text panel right 42%. Zero overlay on product."""
    raw = _load_product_image(image_source)
    if raw is None:
        return _render_content_slide(width, height, slide_num, total_slides, headline, body, colors)

    img_zone_w = int(width * 0.58)
    panel_w = width - img_zone_w

    product_img = ImageOps.fit(raw, (img_zone_w, height), method=Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (width, height), _hex_to_rgb(colors["primary"]))
    canvas.paste(product_img, (0, 0))

    draw = ImageDraw.Draw(canvas)
    panel_x = img_zone_w
    padding = int(panel_w * 0.12)
    text_max_w = panel_w - padding * 2

    accent_h = int(height * 0.005)
    draw.rectangle(
        [(panel_x, 0), (width, accent_h)],
        fill=_hex_to_rgb(colors["accent"]),
    )

    title_size = int(min(width, height) * 0.042)
    font_title = _get_font(title_size, bold=True)
    title_y = int(height * 0.22)
    wrapped_title = _wrap_text(draw, headline, font_title, text_max_w)
    draw.multiline_text(
        (panel_x + padding, title_y), wrapped_title, font=font_title,
        fill=(255, 255, 255), spacing=int(title_size * 0.25),
    )

    if body:
        body_size = int(min(width, height) * 0.028)
        font_body = _get_font(body_size)
        title_bbox = draw.multiline_textbbox(
            (panel_x + padding, title_y), wrapped_title, font=font_title,
            spacing=int(title_size * 0.25),
        )
        body_y = title_bbox[3] + int(height * 0.03)
        wrapped_body = _wrap_text(draw, body, font_body, text_max_w)
        draw.multiline_text(
            (panel_x + padding, body_y), wrapped_body, font=font_body,
            fill=_hex_to_rgb(colors["text_muted"]), spacing=int(body_size * 0.3),
        )

    counter_size = int(min(width, height) * 0.024)
    font_counter = _get_font(counter_size, bold=True)
    draw.text(
        (panel_x + padding, height - int(height * 0.08)),
        f"{slide_num}/{total_slides}",
        font=font_counter,
        fill=_hex_to_rgb(colors["accent"]),
    )

    return canvas


def _render_minimal_caption_slide(
    width: int,
    height: int,
    image_source: str,
    caption: str,
    colors: dict,
    *,
    slide_num: int | None = None,
    total_slides: int | None = None,
) -> Image.Image:
    """Product-first: full photo with only a minimal 10% caption strip at bottom."""
    raw = _load_product_image(image_source)
    if raw is None:
        return _render_content_slide(
            width, height, slide_num or 1, total_slides or 1, caption, "", colors,
        )

    img = ImageOps.fit(raw, (width, height), method=Image.Resampling.LANCZOS).convert("RGBA")

    strip_h = int(height * 0.10)
    strip = Image.new("RGBA", (width, strip_h), (0, 0, 0, 120))
    img.paste(strip, (0, height - strip_h), strip)

    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)
    padding_x = int(width * 0.06)

    cap_size = int(min(width, height) * 0.032)
    font_cap = _get_font(cap_size, bold=True)
    max_w = width - padding_x * 2 - (int(width * 0.12) if slide_num else 0)
    display_text = caption
    while draw.textbbox((0, 0), display_text, font=font_cap)[2] > max_w and len(display_text) > 10:
        display_text = display_text[:-4] + "\u2026"
    cap_y = height - strip_h + (strip_h - cap_size) // 2
    draw.text(
        (padding_x, cap_y), display_text, font=font_cap, fill=(255, 255, 255),
    )

    if slide_num is not None and total_slides is not None:
        counter_text = f"{slide_num}/{total_slides}"
        counter_size = int(min(width, height) * 0.024)
        font_counter = _get_font(counter_size, bold=True)
        cb = draw.textbbox((0, 0), counter_text, font=font_counter)
        cw = cb[2] - cb[0]
        draw.text(
            (width - padding_x - cw, cap_y),
            counter_text, font=font_counter, fill=_hex_to_rgb(colors["accent"]),
        )

    return img


def generate_product_carousel(
    post,
    product,
    *,
    key_features: list[str] | None = None,
    analysis: dict | None = None,
    closing_cta: str = "Shop Now",
) -> list[str]:
    """
    Story-driven product carousel: hook → story → benefits → price → CTA.

    Uses vision analysis for accurate copy and varied slide layouts.
    """
    from apps.content.tasks import _normalize_reel_image_source
    from apps.products.product_copy import build_product_carousel_plan

    raw_images = product.carousel_image_urls or product.all_image_urls
    all_images = [_normalize_reel_image_source(u) for u in raw_images if u]
    if not all_images:
        logger.warning("generate_product_carousel: product %s has no images", product.pk)
        return []

    width, height = 1080, 1080
    profile = getattr(post.user, "profile", None)
    colors = _get_brand_palette(profile)
    brand_name = getattr(profile, "company_name", "") if profile else ""

    slide_plan = build_product_carousel_plan(product, analysis, key_features)
    total_slides = len(slide_plan) + 1

    media_urls = []
    try:
        slide_images = []

        for idx, spec in enumerate(slide_plan):
            slide_num = idx + 1
            img_src = all_images[spec.get("image_index", idx) % len(all_images)]
            layout = spec.get("layout", "benefit_bottom")

            if layout == "hero_hook":
                slide = _render_product_hero_hook_slide(
                    width, height, img_src,
                    spec.get("headline", product.name),
                    spec.get("subtext", ""),
                    colors,
                    badge=spec.get("badge", ""),
                    slide_num=slide_num,
                    total_slides=total_slides,
                )
            elif layout == "story_card":
                slide = _render_product_story_slide(
                    width, height, img_src,
                    spec.get("headline", "The details"),
                    spec.get("body", ""),
                    colors,
                    slide_num=slide_num,
                    total_slides=total_slides,
                )
            elif layout == "price_reveal":
                slide = _render_product_price_slide(
                    width, height, img_src,
                    spec.get("headline", product.display_price or ""),
                    spec.get("body", ""),
                    spec.get("subtext", product.name),
                    colors,
                    slide_num=slide_num,
                    total_slides=total_slides,
                )
            elif layout == "clean_split":
                slide = _render_clean_split_slide(
                    width, height, img_src,
                    spec.get("headline", product.name),
                    spec.get("body", ""),
                    colors,
                    slide_num=slide_num,
                    total_slides=total_slides,
                )
            elif layout == "side_panel":
                slide = _render_side_panel_slide(
                    width, height, img_src,
                    spec.get("headline", product.name),
                    spec.get("body", ""),
                    colors,
                    slide_num=slide_num,
                    total_slides=total_slides,
                )
            elif layout == "minimal_caption":
                slide = _render_minimal_caption_slide(
                    width, height, img_src,
                    spec.get("headline", product.name),
                    colors,
                    slide_num=slide_num,
                    total_slides=total_slides,
                )
            elif layout.startswith("benefit"):
                slide = _render_product_benefit_slide(
                    width, height, img_src,
                    spec.get("headline", ""),
                    spec.get("body", ""),
                    colors,
                    layout=layout,
                    slide_num=slide_num,
                    total_slides=total_slides,
                )
            else:
                slide = _render_photo_slide(
                    width, height, img_src,
                    spec.get("headline", product.name),
                    colors,
                    slide_num=slide_num,
                    total_slides=total_slides,
                    is_first=idx == 0,
                )
            slide_images.append(slide)

        slide_images.append(
            _render_closing_slide(width, height, closing_cta, brand_name, colors)
        )

        for order, img in enumerate(slide_images):
            img = apply_logo_watermark(img, profile)

            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=88, optimize=True)
            buffer.seek(0)

            filename = f"product_carousel_{uuid.uuid4().hex[:8]}_s{order + 1}.jpg"
            filepath = f"carousels/{filename}"
            attachment = MediaAttachment(
                post=post,
                file_type="image",
                alt_text=f"Product carousel slide {order + 1}/{len(slide_images)}",
                order=order,
            )
            attachment.file.save(filepath, ContentFile(buffer.read()), save=True)
            from apps.content.tasks import _public_url_for_file

            public_url = _public_url_for_file(attachment.file.name)
            media_urls.append(public_url or attachment.file.url)

        if not post.media_urls:
            post.media_urls = []
        post.media_urls = list(media_urls)
        post.media_status = "generated"
        post.save(update_fields=["media_urls", "media_status", "updated_at"])

        logger.info(
            "Generated %d-slide story carousel for post %s (product=%s, platform=%s)",
            len(slide_images), post.id, product.pk, post.platform,
        )
        return media_urls

    except Exception as exc:
        logger.exception(
            "Product carousel generation failed for post %s: %s", post.id, exc
        )
        return []
