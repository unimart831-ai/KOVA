"""Tests for 9:16 beat-frame studio and beat-sync pacing."""

from apps.create.content.reel_beat_sync import align_durations_to_beats, bpm_for_mood
from apps.create.content.reel_director import (
    CATEGORY_PACING,
    SLIDE_ROLE_CTA,
    SLIDE_ROLE_DESIRE,
    SLIDE_ROLE_HERO,
    SLIDE_ROLE_HOOK,
    build_hook_texts,
    build_slide_durations,
)
from apps.create.content.reel_frame_studio import (
    BeatFrameBrand,
    parse_cta_text,
    render_cta_beat_frame,
    render_hook_beat_frame,
)


def test_render_hook_beat_frame_size():
    frame = render_hook_beat_frame(
        headline="Fresh kitenge drop",
        brand=BeatFrameBrand(primary="#0066FF", secondary="#0066FF", accent="#F59E0B"),
    )
    assert frame.size == (1080, 1920)


def test_render_cta_beat_frame_size():
    frame = render_cta_beat_frame(
        price_label="KES 2,500",
        cta_label="Shop on WhatsApp",
        brand=BeatFrameBrand(),
    )
    assert frame.size == (1080, 1920)


def test_parse_cta_text_splits_price_and_cta():
    price, cta = parse_cta_text("KES 1,200\nShop on WhatsApp")
    assert price == "KES 1,200"
    assert cta == "Shop on WhatsApp"


def test_build_hook_texts_price_only_on_cta():
    roles = [SLIDE_ROLE_HOOK, SLIDE_ROLE_HERO, SLIDE_ROLE_DESIRE, SLIDE_ROLE_CTA]
    texts = build_hook_texts(
        slide_count=4,
        slide_roles=roles,
        product_name="Blue Dress",
        price_label="KES 3,000",
        cta_label="Order on WhatsApp",
    )
    assert texts[0] == "Blue Dress"
    assert "KES" in texts[-1]
    assert texts[1] == ""
    assert texts[2] == ""


def test_align_durations_to_beats_snaps():
    raw = [2.7, 3.1, 2.9, 3.4]
    out = align_durations_to_beats(raw, bpm=120, transition_sec=0.45)
    assert len(out) == 4
    assert all(2.0 <= d <= 6.0 for d in out)


def test_jewelry_category_slower_hero():
    roles = [SLIDE_ROLE_HOOK, SLIDE_ROLE_HERO, SLIDE_ROLE_CTA]
    general = build_slide_durations(roles, category="general", music_mood="upbeat")
    jewelry = build_slide_durations(roles, category="jewelry", music_mood="calm")
    assert jewelry[1] >= general[1] * 0.95


def test_food_category_faster_middle_beats():
    assert CATEGORY_PACING["food"][SLIDE_ROLE_DESIRE] < 1.0


def test_bpm_for_mood():
    assert bpm_for_mood("urgent") > bpm_for_mood("calm")
