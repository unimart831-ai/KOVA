"""
Remotion render bridge — optional v2 reel backend (falls back to FFmpeg).
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

MEDIA_RENDER_ROOT = Path(settings.BASE_DIR) / "media_render"


def remotion_enabled() -> bool:
    backend = getattr(settings, "REEL_RENDER_BACKEND", "ffmpeg")
    if backend != "remotion":
        return False
    return MEDIA_RENDER_ROOT.is_dir() and shutil.which("npx") is not None


def compose_via_remotion(plan, *, audio_path: Path | None = None) -> bytes | None:
    """
    Render ReelComposePlan via Remotion CLI when configured.
    Returns MP4 bytes or None to fall back to FFmpeg.
    """
    if not remotion_enabled():
        return None

    render_script = MEDIA_RENDER_ROOT / "scripts" / "render-reel.mjs"
    if not render_script.is_file():
        logger.info("remotion_bridge: render script missing — using FFmpeg")
        return None

    payload = {
        "imageUrls": plan.image_urls,
        "hookTexts": plan.hook_texts,
        "slideRoles": plan.slide_roles,
        "slideDurations": plan.slide_durations,
        "transitions": plan.transitions,
        "musicMood": plan.music_mood,
    }

    import tempfile

    workdir = Path(tempfile.mkdtemp(prefix="kova-remotion-"))
    props_file = workdir / "props.json"
    out_file = workdir / "reel.mp4"
    props_file.write_text(json.dumps(payload), encoding="utf-8")

    try:
        node = shutil.which("node") or "node"
        subprocess.run(
            [node, str(render_script), str(out_file), "--props", str(props_file)],
            cwd=str(MEDIA_RENDER_ROOT),
            check=True,
            capture_output=True,
            timeout=600,
        )
        if out_file.is_file() and out_file.stat().st_size > 1000:
            return out_file.read_bytes()
    except Exception as exc:
        logger.warning("remotion_bridge: render failed — FFmpeg fallback: %s", exc)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return None
