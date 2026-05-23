"""
Royalty-free music bed catalog for motion Reels.

Tracks live under static/audio/reel-beds/ (and reel-beds/ on default storage)
and are referenced by reel_music_catalog.json.
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
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

VALID_MOODS = ("upbeat", "calm", "urgent")
CATALOG_PATH = Path(__file__).resolve().parent / "data" / "reel_music_catalog.json"
REEL_BEDS_ROOT = Path(settings.BASE_DIR) / "static" / "audio" / "reel-beds"
REEL_BEDS_CACHE = Path(settings.BASE_DIR) / "tmp" / "reel-beds-cache"
STORAGE_PREFIX = "reel-beds/"
CATALOG_STORAGE_KEY = f"{STORAGE_PREFIX}catalog.json"


def _load_catalog_from_path(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return list(data.get("tracks") or [])


def load_music_catalog() -> list[dict]:
    """Load track metadata — prefers cloud catalog in production when available."""
    use_storage = bool(getattr(settings, "AWS_STORAGE_BUCKET_NAME", ""))
    if use_storage:
        from django.core.files.storage import default_storage

        try:
            if default_storage.exists(CATALOG_STORAGE_KEY):
                with default_storage.open(CATALOG_STORAGE_KEY) as fh:
                    data = json.load(fh)
                return list(data.get("tracks") or [])
        except Exception as exc:
            logger.warning("reel_music: storage catalog load failed: %s", exc)

    if not CATALOG_PATH.exists():
        logger.warning("reel_music: catalog not found at %s", CATALOG_PATH)
        return []
    return _load_catalog_from_path(CATALOG_PATH)


def save_music_catalog(tracks: list[dict]) -> None:
    """Persist catalog to local JSON and cloud storage (when configured)."""
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "tracks": tracks}
    serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    CATALOG_PATH.write_text(serialized, encoding="utf-8")

    try:
        from django.core.files.storage import default_storage

        if default_storage.exists(CATALOG_STORAGE_KEY):
            default_storage.delete(CATALOG_STORAGE_KEY)
        default_storage.save(CATALOG_STORAGE_KEY, ContentFile(serialized.encode("utf-8")))
    except Exception as exc:
        logger.warning("reel_music: could not mirror catalog to storage: %s", exc)


def get_track_by_id(track_id: str) -> dict | None:
    for track in load_music_catalog():
        if track.get("id") == track_id:
            return track
    return None


def slugify_track_filename(title: str) -> str:
    from slugify import slugify

    base = slugify(title or "track", max_length=48) or "track"
    return f"{base}.mp3"


def next_track_id(mood: str) -> str:
    mood = (mood or "upbeat").lower()
    prefix = f"{mood}-"
    numbers = []
    for track in load_music_catalog():
        tid = track.get("id") or ""
        if tid.startswith(prefix):
            suffix = tid[len(prefix):]
            if suffix.isdigit():
                numbers.append(int(suffix))
    n = max(numbers, default=0) + 1
    return f"{prefix}{n:02d}"


def unique_relative_path(mood: str, filename: str) -> str:
    """Ensure mood/filename is unique in catalog."""
    mood = (mood or "upbeat").lower()
    filename = Path(filename).name
    rel = f"{mood}/{filename}"
    existing = {t.get("file") for t in load_music_catalog()}
    if rel not in existing:
        return rel
    stem = Path(filename).stem
    ext = Path(filename).suffix or ".mp3"
    n = 2
    while f"{mood}/{stem}-{n}{ext}" in existing:
        n += 1
    return f"{mood}/{stem}-{n}{ext}"


def save_track_file(relative_path: str, uploaded_file) -> Path:
    """
    Save MP3 to local reel-beds folder and default storage (R2 in production).
    """
    from django.core.files.storage import default_storage

    rel = relative_path.replace("\\", "/").lstrip("/")
    data = uploaded_file.read()
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    dest = REEL_BEDS_ROOT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)

    storage_key = f"{STORAGE_PREFIX}{rel}"
    try:
        if default_storage.exists(storage_key):
            default_storage.delete(storage_key)
        default_storage.save(storage_key, ContentFile(data))
    except Exception as exc:
        logger.warning("reel_music: could not mirror track to storage (%s): %s", storage_key, exc)

    return dest


def delete_track_file(relative_path: str) -> None:
    from django.core.files.storage import default_storage

    rel = relative_path.replace("\\", "/").lstrip("/")
    local = REEL_BEDS_ROOT / rel
    if local.is_file():
        local.unlink()
    storage_key = f"{STORAGE_PREFIX}{rel}"
    try:
        if default_storage.exists(storage_key):
            default_storage.delete(storage_key)
    except Exception as exc:
        logger.warning("reel_music: could not delete storage object %s: %s", storage_key, exc)
    cache_path = REEL_BEDS_CACHE / rel
    if cache_path.is_file():
        cache_path.unlink(missing_ok=True)


def add_track(
    *,
    title: str,
    mood: str,
    uploaded_file,
    attribution: str = "",
    source: str = "uploaded",
    duration_sec: int = 30,
) -> dict:
    """Upload file and append a catalog entry."""
    mood = (mood or "upbeat").lower()
    if mood not in VALID_MOODS:
        raise ValueError(f"Invalid mood: {mood}")

    title = (title or "").strip()
    if not title:
        raise ValueError("Title is required")

    filename = slugify_track_filename(title)
    rel = unique_relative_path(mood, filename)
    save_track_file(rel, uploaded_file)

    track = {
        "id": next_track_id(mood),
        "title": title,
        "mood": mood,
        "file": rel,
        "duration_sec": int(duration_sec or 30),
        "source": source or "uploaded",
        "attribution": (attribution or "").strip(),
    }
    tracks = load_music_catalog()
    tracks.append(track)
    save_music_catalog(tracks)
    return track


def replace_track_file(track_id: str, uploaded_file) -> dict:
    """Replace MP3 bytes for an existing catalog track."""
    tracks = load_music_catalog()
    track = None
    for item in tracks:
        if item.get("id") == track_id:
            track = item
            break
    if not track:
        raise ValueError("Track not found")
    rel = track.get("file") or ""
    if not rel:
        raise ValueError("Track has no file path")
    save_track_file(rel, uploaded_file)
    return track


def delete_track(track_id: str, *, remove_file: bool = True) -> bool:
    """Remove track from catalog and optionally delete its MP3."""
    tracks = load_music_catalog()
    removed = None
    kept = []
    for item in tracks:
        if item.get("id") == track_id:
            removed = item
        else:
            kept.append(item)
    if not removed:
        return False
    if remove_file and removed.get("file"):
        delete_track_file(removed["file"])
    save_music_catalog(kept)
    return True


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
    if path.is_file():
        return path

    from django.core.files.storage import default_storage

    storage_key = f"{STORAGE_PREFIX}{rel}"
    try:
        if default_storage.exists(storage_key):
            cache_path = REEL_BEDS_CACHE / rel
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            if not cache_path.is_file():
                with default_storage.open(storage_key, "rb") as src:
                    cache_path.write_bytes(src.read())
            return cache_path
    except Exception as exc:
        logger.warning("reel_music: storage fetch failed for %s: %s", storage_key, exc)

    return None


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
