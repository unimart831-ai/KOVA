"""Unit tests for reel caption layout, safe zones, and hook sequencing."""

from PIL import Image
from apps.content.reel_director import build_hook_texts
from apps.content.video_compose import (
    CAPTION_MAX_LINES,
    SAFE_BOTTOM_MARGIN,
    SAFE_TOP_MARGIN,
    caption_safe_zones,
    hook_position_for_slide,
    render_hook_text_on_frame,
    _ken_burns_ease,
    _ken_burns_filter,
    _wrap_caption_lines,
)


def test_caption_safe_zones_respect_platform_margins():
    zones = caption_safe_zones(1080, 1920)
    assert zones["hero_top"] == int(1920 * SAFE_TOP_MARGIN)
    assert zones["hero_bottom"] == int(1920 * (SAFE_TOP_MARGIN + 0.60))
    assert zones["caption_bottom"] == int(1920 * (1.0 - SAFE_BOTTOM_MARGIN))
    assert zones["caption_top"] >= zones["hero_bottom"]
    assert zones["caption_top"] < zones["caption_bottom"]


def test_hook_position_always_lower_third():
    assert hook_position_for_slide(0, "Glow Serum") == "lower_third"
    assert hook_position_for_slide(2, "") == ""


def test_wrap_caption_lines_max_two():
    wrapped = _wrap_caption_lines(
        "Line one\nLine two\nLine three",
        max_lines=CAPTION_MAX_LINES,
        chars_per_line=24,
    )
    assert wrapped.count("\n") <= CAPTION_MAX_LINES - 1


def test_build_hook_texts_staggered_sequence():
    texts = build_hook_texts(
        slide_count=5,
        slide_roles=["hook", "hero", "desire", "desire", "cta"],
        product_name="Amaya Speaker",
        price_label="KES 1,200",
        brand_name="Amaya Audio",
        cta_label="Order on WhatsApp",
    )
    assert texts[0] == "Amaya Speaker"
    assert texts[1] == ""
    assert texts[2] == ""
    assert texts[3] == ""
    assert texts[4] == "KES 1,200\nShop on WhatsApp"


def test_build_hook_texts_short_cta():
    texts = build_hook_texts(
        slide_count=2,
        slide_roles=["hook", "cta"],
        product_name="Speaker",
        price_label="KES 500",
        cta_label="Buy on WhatsApp",
    )
    assert "Shop on WhatsApp" in texts[1]


def test_ken_burns_uses_smoothstep_easing():
    filt = _ken_burns_filter(90, variant=0)
    ease = _ken_burns_ease("on/90")
    assert ease in filt
    assert "pow" in filt


def test_render_hook_lower_third_does_not_cover_hero_center():
    frame = Image.new("RGB", (1080, 1920), color=(240, 240, 240))
    out = render_hook_text_on_frame(
        frame,
        "Premium Glow Serum",
        slide_index=0,
        slide_count=3,
    )
    zones = caption_safe_zones(1080, 1920)
    hero_slice = out.crop((0, zones["hero_top"], 1080, zones["hero_bottom"]))
    caption_slice = out.crop((0, zones["caption_top"], 1080, zones["caption_bottom"]))
    hero_avg = sum(hero_slice.convert("L").getdata()) / max(len(hero_slice.getdata()), 1)
    caption_avg = sum(caption_slice.convert("L").getdata()) / max(len(caption_slice.getdata()), 1)
    assert caption_avg < hero_avg
