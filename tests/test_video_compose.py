"""Unit tests for motion reel composition helpers."""

from apps.content.video_compose import (
    REEL_TRANSITIONS,
    _build_xfade_filter,
    _ken_burns_filter,
)


def test_ken_burns_varies_by_index():
    a = _ken_burns_filter(90, variant=0)
    b = _ken_burns_filter(90, variant=2)
    assert a != b
    assert "zoompan" in a


def test_xfade_uses_multiple_transition_types():
    graph, _ = _build_xfade_filter(4, slide_sec=3.5, transition_sec=0.5)
    used = [t for t in REEL_TRANSITIONS if t in graph]
    assert len(used) >= 2


def test_xfade_single_clip():
    graph, vout = _build_xfade_filter(1, slide_sec=3.0, transition_sec=0.5)
    assert vout == "vout"
    assert "format=yuv420p" in graph
