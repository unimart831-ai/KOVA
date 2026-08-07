"""Tests for motion Reel composition and music catalog."""

import json
import pytest
from io import BytesIO
from pathlib import Path
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.create.content import reel_music
from apps.create.content.reel_music import (
    add_track,
    delete_track,
    infer_mood_from_post,
    load_music_catalog,
    pick_music_track,
    replace_track_file,
    resolve_track_path,
)
from apps.create.content.video_compose import (
    ffmpeg_available,
    fit_composite_slide_to_story,
    fit_image_to_story_frame,
    is_video_url,
)


@pytest.fixture
def isolated_reel_catalog(tmp_path, monkeypatch):
    catalog = tmp_path / "catalog.json"
    beds = tmp_path / "beds"
    beds.mkdir()
    catalog.write_text(json.dumps({"version": 1, "tracks": []}), encoding="utf-8")
    monkeypatch.setattr(reel_music, "CATALOG_PATH", catalog)
    monkeypatch.setattr(reel_music, "REEL_BEDS_ROOT", beds)
    monkeypatch.setattr(reel_music, "REEL_BEDS_CACHE", tmp_path / "cache")
    monkeypatch.setattr(reel_music, "save_track_file", lambda rel, f: reel_music.REEL_BEDS_ROOT.joinpath(*rel.split("/")).write_bytes(f.read()))
    return beds


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

    def test_add_and_delete_track(self, isolated_reel_catalog):
        mp3 = SimpleUploadedFile("beat.mp3", b"\xff\xfb" + b"\x00" * 128, content_type="audio/mpeg")
        track = add_track(title="Test Groove", mood="upbeat", uploaded_file=mp3, duration_sec=28)
        assert track["id"].startswith("upbeat-")
        assert load_music_catalog()
        assert resolve_track_path(track) is not None
        assert delete_track(track["id"]) is True
        assert load_music_catalog() == []

    def test_replace_track(self, isolated_reel_catalog):
        mp3 = SimpleUploadedFile("beat.mp3", b"\xff\xfb" + b"\x00" * 128, content_type="audio/mpeg")
        track = add_track(title="Replace Me", mood="calm", uploaded_file=mp3)
        new_mp3 = SimpleUploadedFile("new.mp3", b"\xff\xfb" + b"\x01" * 128, content_type="audio/mpeg")
        replace_track_file(track["id"], new_mp3)
        path = resolve_track_path(track)
        assert path is not None
        assert path.read_bytes()[3] == 1


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

    def test_fit_promo_frame_letterboxes_centered(self):
        img = Image.new("RGB", (1080, 1080), color=(200, 100, 50))
        buf = BytesIO()
        img.save(buf, format="JPEG")
        data = buf.getvalue()
        frame = fit_composite_slide_to_story(data)
        assert frame.size == (1080, 1920)
        center = frame.getpixel((540, 960))
        assert center[0] > 150

        hinted = fit_image_to_story_frame(data, source_hint="/media/studio/promo_frame_abc.jpg")
        assert hinted.size == (1080, 1920)
        assert hinted.getpixel((540, 960))[0] > 150

    @pytest.mark.skipif(not ffmpeg_available(), reason="FFmpeg not installed")
    def test_compose_single_image_reel(self):
        from apps.create.content.video_compose import compose_motion_reel

        img = Image.new("RGB", (1080, 1920), color=(30, 60, 120))
        buf = BytesIO()
        img.save(buf, format="JPEG")
        tmp = pytest.importorskip("tempfile").NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.write(buf.getvalue())
        tmp.close()

        mp4 = compose_motion_reel([tmp.name], slide_duration_sec=2.0, transition_sec=0.3)
        assert mp4[:4] == b"\x00\x00\x00" or mp4[4:8] == b"ftyp"
        assert len(mp4) > 5000
