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
from PIL import Image, ImageDraw

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
            media_urls.append(attachment.file.url)

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
