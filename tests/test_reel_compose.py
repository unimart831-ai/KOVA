"""Tests for motion Reel composition and music catalog."""

import pytest
from io import BytesIO
from PIL import Image

from apps.content.reel_music import infer_mood_from_post, load_music_catalog, pick_music_track
from apps.content.video_compose import ffmpeg_available, fit_image_to_story_frame, is_video_url


@pytest.mark.django_db
class TestReelMusic:
    def test_catalog_loads(self):
        tracks = load_music_catalog()
        assert len(tracks) >= 30
        moods = {t["mood"] for t in tracks}
        assert moods == {"upbeat", "calm", "urgent"}

    def test_pick_track_deterministic(self):
        a = pick_music_track(mood="upbeat", seed="post-123")
        b = pick_music_track(mood="upbeat", seed="post-123")
        assert a["id"] == b["id"]

    def test_infer_mood_offer(self):
        assert infer_mood_from_post(content_intent="offer", content_text="50% off today") == "urgent"

    def test_infer_mood_calm(self):
        assert infer_mood_from_post(content_intent="solution", content_text="How to grow") == "calm"


class TestVideoComposeHelpers:
    def test_is_video_url(self):
        assert is_video_url("https://cdn.example.com/reel.mp4")
        assert not is_video_url("https://cdn.example.com/photo.jpg")

    def test_fit_square_to_story(self):
        img = Image.new("RGB", (1080, 1080), color=(200, 100, 50))
        buf = BytesIO()
        img.save(buf, format="JPEG")
        frame = fit_image_to_story_frame(buf.getvalue())
        assert frame.size == (1080, 1920)

    @pytest.mark.skipif(not ffmpeg_available(), reason="FFmpeg not installed")
    def test_compose_single_image_reel(self):
        from apps.content.video_compose import compose_motion_reel

        img = Image.new("RGB", (1080, 1920), color=(30, 60, 120))
        buf = BytesIO()
        img.save(buf, format="JPEG")
        tmp = pytest.importorskip("tempfile").NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.write(buf.getvalue())
        tmp.close()

        mp4 = compose_motion_reel([tmp.name], slide_duration_sec=2.0, transition_sec=0.3)
        assert mp4[:4] == b"\x00\x00\x00" or mp4[4:8] == b"ftyp"
        assert len(mp4) > 5000
