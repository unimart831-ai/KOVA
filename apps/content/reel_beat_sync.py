"""
Beat-aligned reel pacing — snap slide durations to musical grid + CTA sound FX.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

MOOD_BPM: dict[str, float] = {
    "upbeat": 118.0,
    "calm": 92.0,
    "urgent": 128.0,
}

SFX_FOLDER = Path(__file__).resolve().parent.parent.parent / "static" / "audio" / "reel-beds" / "sfx"


def beat_sync_enabled() -> bool:
    return bool(getattr(settings, "REEL_BEAT_SYNC_ENABLED", True))


def cta_sfx_enabled() -> bool:
    return bool(getattr(settings, "REEL_CTA_SFX_ENABLED", True))


def bpm_for_mood(mood: str) -> float:
    default = float(getattr(settings, "REEL_DEFAULT_BPM", 120.0))
    return MOOD_BPM.get((mood or "upbeat").lower(), default)


def align_durations_to_beats(
    durations: list[float],
    *,
    bpm: float | None = None,
    transition_sec: float = 0.45,
    min_sec: float = 2.0,
    max_sec: float = 6.0,
) -> list[float]:
    """Snap each slide duration to the nearest half-beat while preserving total runtime."""
    if not beat_sync_enabled() or not durations:
        return durations

    bpm = bpm or float(getattr(settings, "REEL_DEFAULT_BPM", 120.0))
    beat = 60.0 / max(bpm, 60.0)
    half = beat / 2.0

    raw_total = sum(durations) - transition_sec * max(len(durations) - 1, 0)
    snapped: list[float] = []
    for d in durations:
        units = max(1, round(d / half))
        snapped.append(max(min_sec, min(max_sec, units * half)))

    new_total = sum(snapped) - transition_sec * max(len(snapped) - 1, 0)
    if raw_total > 0 and new_total > 0:
        scale = raw_total / new_total
        snapped = [max(min_sec, min(max_sec, d * scale)) for d in snapped]

    return snapped


def cta_slide_start_sec(
    slide_durations: list[float],
    transition_sec: float = 0.45,
) -> float:
    """Timestamp when the final slide begins (for SFX placement)."""
    if len(slide_durations) <= 1:
        return 0.0
    total = 0.0
    for d in slide_durations[:-1]:
        total += d - transition_sec
    return max(total, 0.0)


def ensure_cta_sfx_path() -> Path | None:
    """Return path to a short swish SFX — generates once via FFmpeg if missing."""
    if not cta_sfx_enabled():
        return None
    SFX_FOLDER.mkdir(parents=True, exist_ok=True)
    path = SFX_FOLDER / "cta-swish.mp3"
    if path.is_file() and path.stat().st_size > 200:
        return path
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi",
                "-i", "sine=frequency=880:duration=0.08",
                "-f", "lavfi",
                "-i", "sine=frequency=440:duration=0.18",
                "-filter_complex",
                "[0:a][1:a]concat=n=2:v=0:a=1,afade=t=out:st=0.2:d=0.08,volume=0.35",
                "-c:a", "libmp3lame", "-q:a", "6",
                str(path),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        if path.is_file():
            return path
    except Exception as exc:
        logger.warning("reel_beat_sync: could not generate CTA SFX: %s", exc)
    return None


def build_audio_mix_filter(
    *,
    music_input_idx: int,
    duration_sec: float,
    cta_start_sec: float | None = None,
    cta_boost: bool = False,
    sfx_input_idx: int | None = None,
) -> str | None:
    """FFmpeg filter_complex for music + optional CTA SFX + volume lift → [aout]."""
    if not cta_boost and sfx_input_idx is None:
        return None

    steps: list[str] = []
    current = f"[{music_input_idx}:a]"

    if cta_boost and duration_sec >= 4:
        fade_start = max(duration_sec - 1.2, 0.0)
        steps.append(
            f"{current}volume=1.0:enable='between(t,0,{fade_start:.2f})',"
            f"volume=1.12:enable='between(t,{fade_start:.2f},{duration_sec:.2f})'[mus]"
        )
        current = "[mus]"

    if sfx_input_idx is not None and cta_start_sec is not None:
        delay_ms = int(max(cta_start_sec, 0.0) * 1000)
        steps.append(f"[{sfx_input_idx}:a]adelay={delay_ms}|{delay_ms},volume=0.55[sfx]")
        steps.append(f"{current}[sfx]amix=inputs=2:duration=first:dropout_transition=0[aout]")
    elif steps:
        steps.append(f"{current}anull[aout]")

    return ";".join(steps) if steps else None
