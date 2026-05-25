"""
Motion Reel compositor — Ken Burns slideshow + crossfade + music bed.

Produces 1080×1920 H.264 MP4 from image URLs or local paths.
Requires FFmpeg on the worker host.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
DEFAULT_FPS = 30
DEFAULT_SLIDE_SEC = 3.5
DEFAULT_TRANSITION_SEC = 0.55
MIN_SLIDE_SEC = 2.0
MAX_SLIDE_SEC = 6.0

# Rotating FFmpeg xfade transitions — each slide change gets a distinct motion style.
REEL_TRANSITIONS = (
    "slideup",
    "slidedown",
    "slideleft",
    "slideright",
    "wipeup",
    "wipedown",
    "smoothup",
    "smoothdown",
    "circleopen",
    "dissolve",
    "zoomin",
    "wipetl",
    "wipebr",
    "fade",
)


class VideoComposeError(Exception):
    """Raised when reel composition fails."""


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def is_video_url(url: str) -> bool:
    if not url:
        return False
    path = urlparse(url).path.lower()
    return path.endswith((".mp4", ".mov", ".webm", ".m4v"))


def _download_bytes(source: str, timeout: float = 45.0) -> bytes:
    if source.startswith(("http://", "https://")):
        resp = httpx.get(source, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        return resp.content
    path = Path(source)
    if not path.is_file():
        raise VideoComposeError(f"Image not found: {source}")
    return path.read_bytes()


def fit_image_to_story_frame(image_bytes: bytes) -> Image.Image:
    """
    Fit any aspect ratio into 9:16 with blurred background + centered foreground.
    """
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    target_w, target_h = OUTPUT_WIDTH, OUTPUT_HEIGHT

    cover = ImageOps.fit(img, (target_w, target_h), method=Image.LANCZOS)
    if abs((img.width / img.height) - (target_w / target_h)) < 0.05:
        return cover

    bg = ImageOps.fit(img, (target_w, target_h), method=Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=24))

    fg = img.copy()
    max_fg_w = int(target_w * 0.92)
    max_fg_h = int(target_h * 0.72)
    fg.thumbnail((max_fg_w, max_fg_h), Image.LANCZOS)

    canvas = bg.copy()
    x = (target_w - fg.width) // 2
    y = (target_h - fg.height) // 2
    canvas.paste(fg, (x, y))
    return canvas


def _write_story_frame(image_bytes: bytes, dest: Path) -> None:
    frame = fit_image_to_story_frame(image_bytes)
    frame.save(dest, format="JPEG", quality=92, optimize=True)


def _ken_burns_filter(slide_frames: int, variant: int = 0) -> str:
    """zoompan filter — Ken Burns with directional pan (rise, descend, drift)."""
    v = variant % 6
    h, w = OUTPUT_HEIGHT, OUTPUT_WIDTH
    pan_y = int(h * 0.10)
    pan_x = int(w * 0.08)

    if v == 0:
        zoom_expr = "min(zoom+0.0015,1.15)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
    elif v == 1:
        zoom_expr = "if(lte(on,1),1.14,max(1.001,zoom-0.0018))"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
    elif v == 2:
        zoom_expr = "min(zoom+0.0012,1.12)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = f"ih/2-(ih/zoom/2)+{pan_y}*(1-on/{slide_frames})"
    elif v == 3:
        zoom_expr = "min(zoom+0.0012,1.12)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = f"ih/2-(ih/zoom/2)-{pan_y}*(1-on/{slide_frames})"
    elif v == 4:
        zoom_expr = "min(zoom+0.0012,1.12)"
        x_expr = f"iw/2-(iw/zoom/2)-{pan_x}*(1-on/{slide_frames})"
        y_expr = "ih/2-(ih/zoom/2)"
    else:
        zoom_expr = "min(zoom+0.0012,1.12)"
        x_expr = f"iw/2-(iw/zoom/2)+{pan_x}*(1-on/{slide_frames})"
        y_expr = "ih/2-(ih/zoom/2)"

    return (
        f"zoompan=z='{zoom_expr}':"
        f"x='{x_expr}':y='{y_expr}':"
        f"d={slide_frames}:s={w}x{h}:fps={DEFAULT_FPS}"
    )


def _pick_transition(index: int) -> str:
    return REEL_TRANSITIONS[index % len(REEL_TRANSITIONS)]


def _build_xfade_filter(num_clips: int, slide_sec: float, transition_sec: float) -> tuple[str, str]:
    """Build filter_complex for chained xfade transitions with varied motion styles."""
    if num_clips == 1:
        return "[0:v]format=yuv420p[vout]", "vout"

    parts = []
    offset = slide_sec - transition_sec
    prev = "0:v"
    for i in range(1, num_clips):
        out = f"v{i}"
        transition = _pick_transition(i - 1)
        parts.append(
            f"[{prev}][{i}:v]xfade=transition={transition}:duration={transition_sec:.3f}:offset={offset:.3f}[{out}]"
        )
        prev = out
        offset += slide_sec - transition_sec
    parts.append(f"[{prev}]format=yuv420p[vout]")
    return ";".join(parts), "vout"


def compose_motion_reel(
    image_sources: Iterable[str],
    *,
    slide_duration_sec: float = DEFAULT_SLIDE_SEC,
    transition_sec: float = DEFAULT_TRANSITION_SEC,
    audio_path: Optional[Path] = None,
    template: str = "slideshow",
) -> bytes:
    """
    Compose a motion Reel MP4 from ordered image sources (URLs or paths).

    Returns raw MP4 bytes.
    """
    if not ffmpeg_available():
        raise VideoComposeError("FFmpeg is not installed on this worker")

    sources = [s for s in image_sources if s]
    if not sources:
        raise VideoComposeError("At least one image is required for reel composition")

    slide_sec = max(MIN_SLIDE_SEC, min(float(slide_duration_sec), MAX_SLIDE_SEC))
    transition_sec = min(float(transition_sec), slide_sec * 0.4)
    slide_frames = max(int(slide_sec * DEFAULT_FPS), 1)

    workdir = Path(tempfile.mkdtemp(prefix="kova-reel-"))
    output_path = workdir / "output.mp4"
    silent_audio = False

    try:
        frame_paths: list[Path] = []
        for idx, source in enumerate(sources):
            frame_path = workdir / f"frame_{idx:02d}.jpg"
            _write_story_frame(_download_bytes(source), frame_path)
            frame_paths.append(frame_path)

        clip_paths: list[Path] = []
        for idx, frame_path in enumerate(frame_paths):
            clip_path = workdir / f"clip_{idx:02d}.mp4"
            vf = _ken_burns_filter(slide_frames, variant=idx)
            cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-loop", "1", "-i", str(frame_path),
                "-vf", vf,
                "-t", f"{slide_sec:.3f}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-an",
                str(clip_path),
            ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            clip_paths.append(clip_path)

        total_duration = slide_sec * len(clip_paths) - transition_sec * max(len(clip_paths) - 1, 0)
        total_duration = max(total_duration, slide_sec)

        audio_input = audio_path
        if audio_input is None:
            from apps.content.reel_music import ensure_audio_bed

            silent_tmp = ensure_audio_bed({"file": ""}, total_duration + 1)
            audio_input = silent_tmp
            silent_audio = True

        filter_graph, vout = _build_xfade_filter(len(clip_paths), slide_sec, transition_sec)

        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
        for clip in clip_paths:
            cmd.extend(["-i", str(clip)])
        cmd.extend(["-i", str(audio_input)])

        if len(clip_paths) == 1:
            cmd.extend([
                "-map", "0:v", "-map", "1:a",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k",
                "-shortest",
                str(output_path),
            ])
        else:
            cmd.extend([
                "-filter_complex", filter_graph,
                "-map", f"[{vout}]", "-map", f"{len(clip_paths)}:a",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k",
                "-shortest",
                str(output_path),
            ])

        subprocess.run(cmd, check=True, capture_output=True, timeout=300)

        if not output_path.is_file() or output_path.stat().st_size < 1000:
            raise VideoComposeError("FFmpeg produced an empty or invalid MP4")

        logger.info(
            "compose_motion_reel: template=%s slides=%d duration~%.1fs size=%d",
            template, len(sources), total_duration, output_path.stat().st_size,
        )
        return output_path.read_bytes()

    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b"").decode(errors="replace")[-500:]
        raise VideoComposeError(f"FFmpeg failed: {stderr}") from exc
    finally:
        if silent_audio and audio_path is None:
            try:
                if audio_input and Path(audio_input).is_file() and str(audio_input).startswith(tempfile.gettempdir()):
                    Path(audio_input).unlink(missing_ok=True)
            except Exception:
                pass
        shutil.rmtree(workdir, ignore_errors=True)


def compose_carousel_to_reel(
    slide_urls: Iterable[str],
    *,
    audio_path: Optional[Path] = None,
) -> bytes:
    """Carousel → Reel: crossfade between existing slide images."""
    return compose_motion_reel(
        slide_urls,
        slide_duration_sec=3.0,
        transition_sec=0.6,
        audio_path=audio_path,
        template="carousel_to_video",
    )
