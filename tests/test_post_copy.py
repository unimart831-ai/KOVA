"""Tests for human-native post caption formatting."""

from types import SimpleNamespace

from apps.create.content.post_copy import (
    build_commerce_caption,
    build_quick_post_caption,
    normalize_caption_spacing,
    polish_post_caption,
)


def test_normalize_caption_spacing_preserves_paragraphs():
    raw = "Hook line\n\nBody paragraph one.\n\n\n\nBody two.\n  "
    out = normalize_caption_spacing(raw)
    assert out == "Hook line\n\nBody paragraph one.\n\nBody two."


def test_polish_post_caption_spaces_emoji_bullet_blocks():
    raw = "Hook\n\n✨ Feature one\n⚡ Feature two\n🔥 Feature three\n\nPrice"
    out = polish_post_caption(raw, "instagram")
    assert "\n\n✨ Feature one" in out
    assert out.index("🔥 Feature three") < out.index("Price")


def test_build_commerce_caption_flows_like_prose():
    product = SimpleNamespace(
        pk="abc-123",
        name="Wireless Earbuds Pro",
        description=(
            "Crystal-clear sound for your daily commute.\n\n"
            "Comfortable fit that stays put all day."
        ),
        display_price="KES 4,500",
        offering_type="product",
        category_id=None,
        category=None,
    )
    analysis = {
        "key_features": ["30-hour battery", "Active noise canceling"],
        "campaign_angle": "Your commute just got quieter.",
    }
    caption = build_commerce_caption(
        product,
        platform="instagram",
        key_features=analysis["key_features"],
        analysis=analysis,
        post_format="carousel",
    )
    assert "Your commute just got quieter." in caption
    assert "Crystal-clear sound" in caption
    assert "Available for KES 4,500" in caption
    assert "link in bio" in caption.lower()
    assert "✨ 30-hour" not in caption
    assert caption.count("\n\n") >= 3


def test_build_commerce_reel_caption_is_short():
    product = SimpleNamespace(
        pk="reel-1",
        name="Silk Scarf",
        description="Soft and elegant.",
        display_price="KES 2,000",
        offering_type="product",
        category_id=None,
        category=None,
    )
    caption = build_commerce_caption(
        product,
        platform="instagram",
        post_format="reel",
    )
    assert len(caption) <= 280
    assert "link in bio" in caption.lower()


def test_build_quick_post_avoids_raw_url_on_instagram():
    product = SimpleNamespace(
        pk="qp-1",
        name="Handmade Soap",
        description="Gentle on sensitive skin.",
        display_price="KES 800",
        offering_type="product",
        category_id=None,
        category=None,
    )
    caption = build_quick_post_caption(product, platform="instagram")
    assert "http" not in caption.lower()
    assert "link in bio" in caption.lower()


def test_adapt_caption_keeps_line_breaks():
    from apps.create.content.campaign_bundle import _adapt_caption

    text = "Line one\n\nLine two\n\nLine three"
    out = _adapt_caption(text, "instagram", 2200)
    assert "\n\n" in out
    assert "Line one" in out and "Line three" in out


def test_polish_splits_dense_paragraph_after_short_blocks():
    """Hook + short para + wall-of-text should become scannable paragraphs."""
    raw = (
        "The most annoying part of modern tech is the nightly charging ritual.\n\n"
        "You've got your phone, your earbuds, your smartwatch... and a tangle of "
        "three different cables you have to find, plug in, and hope they all work. "
        "It's a hassle that feels completely out of sync with the convenience the "
        "tech itself promises.\n\n"
        "That's why we were so impressed by the magnetic wireless ecosystem. With the "
        "oraimo 10000mAh Magnetic Wireless Power Bank, you can charge your phone, "
        "earbuds, and watch without ever plugging in a single cable. It just snaps on. "
        "It solves the 'dozen things to plug in' problem by turning your charging "
        "station into a simple, clean dock. It's not just a gadget; it's a system "
        "upgrade. You're eliminating cable clutter, reducing wear and tear on your "
        "ports, and streamlining your entire daily routine. We're running a flash sale "
        "on it for the next 48 hours. Genuine product, full warranty. What's your "
        "biggest tech frustration at home?"
    )
    out = polish_post_caption(raw, "facebook")
    blocks = [b.strip() for b in out.split("\n\n") if b.strip()]
    assert len(blocks) >= 5
    assert blocks[0].startswith("The most annoying part")
    assert "oraimo" in out
    assert out.endswith("?")


def test_polish_splits_single_wall_of_text():
    blob = (
        "Hook sentence here. Second sentence sets context. Third adds detail. "
        "Fourth keeps going. Fifth sentence too. Sixth wraps benefits. "
        "Seventh mentions the offer. What's your take?"
    )
    out = polish_post_caption(blob, "facebook")
    assert out.count("\n\n") >= 3
    assert out.startswith("Hook sentence here.")
    assert "What's your take?" in out
