"""Tests for PhotoFix, composition grid, and reel video gating."""

from unittest.mock import MagicMock, patch

from apps.products.photoroom_composition import _compose_grid_local
from apps.products.photoroom_photofix import should_run_photofix_for_commerce
from apps.products.photoroom_video import reel_should_use_photoroom_video, video_generation_enabled


def test_should_run_photofix_for_snap():
    with patch("apps.products.photoroom_photofix.photofix_enabled", return_value=True):
        assert should_run_photofix_for_commerce(commerce_source="snap") is True
        assert should_run_photofix_for_commerce(commerce_source="batch_snap") is True
        assert should_run_photofix_for_commerce(commerce_source=None) is False


def test_compose_grid_local_produces_jpeg():
    from PIL import Image
    from io import BytesIO

    buf = BytesIO()
    Image.new("RGBA", (100, 100), (255, 0, 0, 255)).save(buf, format="PNG")
    cutout = buf.getvalue()

    result = _compose_grid_local([cutout, cutout], width=400, height=600, bg_rgb=(240, 240, 240))
    assert result is not None
    assert result[:3] == b"\xff\xd8\xff"


def test_video_enabled_in_sandbox():
    with patch("django.conf.settings.PHOTOROOM_API_KEY", "test-key", create=True):
        with patch("django.conf.settings.PHOTOROOM_SANDBOX", True, create=True):
            with patch("django.conf.settings.PHOTOROOM_VIDEO_ENABLED", False, create=True):
                with patch("django.conf.settings.PHOTOROOM_REEL_USE_VIDEO_API", True, create=True):
                    assert video_generation_enabled() is True


def test_reel_prefers_photoroom_when_not_forced_ffmpeg():
    post = MagicMock()
    post.visual_metadata = {}
    with patch("apps.products.photoroom_video.video_generation_enabled", return_value=True):
        with patch("django.conf.settings.PHOTOROOM_REEL_USE_VIDEO_API", True, create=True):
            assert reel_should_use_photoroom_video(post) is True
    post.visual_metadata = {"reel_compose_backend": "ffmpeg"}
    with patch("apps.products.photoroom_video.video_generation_enabled", return_value=True):
        assert reel_should_use_photoroom_video(post) is False
