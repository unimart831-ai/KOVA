"""Unit tests for motion reel composition helpers."""

import pytest

from apps.content.video_compose import (
    REEL_TRANSITIONS,
    _build_xfade_filter,
    _ken_burns_ease,
    _ken_burns_filter,
    _slide_durations_for,
    caption_safe_zones,
    hook_position_for_slide,
)


def test_ken_burns_varies_by_index():
    a = _ken_burns_filter(90, variant=0)
    b = _ken_burns_filter(90, variant=2)
    assert a != b
    assert "zoompan" in a
    assert "pow" in a


def test_ken_burns_ease_smoothstep():
    assert "pow" in _ken_burns_ease("on/90")


def test_caption_safe_zones():
    zones = caption_safe_zones()
    assert zones["caption_top"] > zones["hero_top"]
    assert zones["caption_bottom"] <= 1920


def test_hook_position_lower_third_only():
    assert hook_position_for_slide(0, "Hook") == "lower_third"
    assert hook_position_for_slide(1, "") == ""


def test_xfade_uses_multiple_transition_types():
    graph, _ = _build_xfade_filter(4, slide_sec=3.5, transition_sec=0.5)
    used = [t for t in REEL_TRANSITIONS if t in graph]
    assert len(used) >= 2


def test_xfade_single_clip():
    graph, vout = _build_xfade_filter(1, slide_sec=3.0, transition_sec=0.5)
    assert vout == "vout"
    assert "format=yuv420p" in graph


def test_slide_durations_for_roles_targets_runtime():
    from apps.content.video_compose import slide_durations_for_roles

    roles = ["hook", "hero", "desire", "cta"]
    d = slide_durations_for_roles(roles, target_total_sec=14.0, transition_sec=0.45)
    assert len(d) == 4
    gaps = 3 * 0.45
    assert sum(d) - gaps == pytest.approx(14.0, rel=0.05)


def test_slide_durations_hook_longer_than_middle():
    d = _slide_durations_for(5)
    assert d[0] >= d[2]
    assert len(d) == 5


def test_ken_burns_has_ten_variants():
    variants = {_ken_burns_filter(90, variant=i) for i in range(10)}
    assert len(variants) == 10
