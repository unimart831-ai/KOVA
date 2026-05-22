"""
Royalty-free music bed catalog for motion Reels.

Tracks live under static/audio/reel-beds/ and are referenced by reel_music_catalog.json.
When a track file is missing, compose falls back to a generated silent bed via FFmpeg.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)

VALID_MOODS = ("upbeat", "calm", "urgent")
CATALOG_PATH = Path(__file__).resolve().parent / "data" / "reel_music_catalog.json"
REEL_BEDS_ROOT = Path(settings.BASE_DIR) / "static" / "audio" / "reel-beds"


def load_music_catalog() -> list[dict]:
    """Load track metadata from the bundled JSON catalog."""
    if not CATALOG_PATH.exists():
        logger.warning("reel_music: catalog not found at %s", CATALOG_PATH)
        return []
    with CATALOG_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return list(data.get("tracks") or [])


def tracks_for_mood(mood: str) -> list[dict]:
    mood = (mood or "upbeat").lower()
    if mood not in VALID_MOODS:
        mood = "upbeat"
    return [t for t in load_music_catalog() if t.get("mood") == mood]


def pick_music_track(mood: Optional[str] = None, seed: Optional[str] = None) -> dict:
    """
    Pick a track deterministically from the catalog.

    seed: post_id or other stable string — same seed → same track for reproducibility.
    """
    pool = tracks_for_mood(mood)
    if not pool:
        return {
            "id": "silent-fallback",
            "title": "Silent",
            "mood": mood or "upbeat",
            "file": "",
            "duration_sec": 30,
            "source": "generated",
            "attribution": "",
        }
    if seed:
        idx = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(pool)
        return pool[idx]
    return pool[0]


def resolve_track_path(track: dict) -> Optional[Path]:
    """Return local filesystem path for a catalog track, or None if missing."""
    rel = (track or {}).get("file") or ""
    if not rel:
        return None
    path = REEL_BEDS_ROOT / rel
    return path if path.is_file() else None


def infer_mood_from_post(content_intent: str = "", content_text: str = "") -> str:
    """Map post intent/copy to a music mood."""
    intent = (content_intent or "").lower()
    text = (content_text or "").lower()
    urgent_markers = ("sale", "offer", "limited", "today only", "hurry", "discount", "% off")
    calm_markers = ("tip", "guide", "how to", "learn", "mindful", "wellness")
    if intent == "offer" or any(m in text for m in urgent_markers):
        return "urgent"
    if intent in ("solution", "authority", "problem_awareness") or any(m in text for m in calm_markers):
        return "calm"
    return "upbeat"


def ensure_audio_bed(track: dict, duration_sec: float) -> Path:
    """
    Return a usable audio file path for FFmpeg.

    Uses the catalog track when present; otherwise generates a silent MP3 via FFmpeg.
    Caller must delete temp files returned from the silent fallback.
    """
    existing = resolve_track_path(track)
    if existing:
        return existing

    import os

    duration = max(float(duration_sec or 30), 5.0)
    fd, tmp_name = tempfile.mkstemp(suffix=".mp3", prefix="reel-bed-")
    os.close(fd)
    tmp = Path(tmp_name)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi",
        "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", str(duration),
        "-c:a", "libmp3lame", "-q:a", "4",
        str(tmp),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        return tmp
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("reel_music: could not generate silent bed: %s", exc)
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise RuntimeError("FFmpeg is required for reel audio beds") from exc
