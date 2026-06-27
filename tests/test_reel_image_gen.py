"""Reel multi-scene image generation."""

from apps.content.image_gen import build_reel_scene_prompts


def test_build_reel_scene_prompts_returns_distinct_scenes():
    prompts = build_reel_scene_prompts("Glow Serum", count=4)
    assert len(prompts) == 4
    assert all("Glow Serum" in p for p in prompts)
    assert all("no text" in p.lower() for p in prompts)
    assert len(set(prompts)) == 4
