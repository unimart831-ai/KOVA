"""
Photoroom Basic v1/segment — cutout-only routing for white-bg exports.

See docs/KOVA_PHOTOROOM_STRATEGY.md Phase 2.
https://docs.photoroom.com/remove-background-api-basic-plan/
"""

from __future__ import annotations

import logging
from io import BytesIO

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

PHOTOROOM_SEGMENT_URL = "https://sdk.photoroom.com/v1/segment"

# White-bg cutout exports eligible for Basic routing (5 Basic ≈ 1 Plus internally).
BASIC_ROUTE_VARIANT_IDS = frozenset({
    "studio_white",
    "channel_marketplace",
    "channel_marketplace_jpeg",
})


def basic_api_enabled() -> bool:
    if not getattr(settings, "PHOTOROOM_BASIC_ROUTING_ENABLED", True):
        return False
    return bool((getattr(settings, "PHOTOROOM_BASIC_API_KEY", "") or "").strip())


def is_basic_routable_variant(variant_id: str, params: dict[str, str]) -> bool:
    """True when this variant is a white-bg cutout with no AI background/shadow stack."""
    if variant_id not in BASIC_ROUTE_VARIANT_IDS:
        return False
    if not basic_api_enabled():
        return False
    if (
        params.get("background.prompt")
        or params.get("background.expandPrompt")
        or params.get("background.expandPrompt.mode")
    ):
        return False
    if params.get("beautify.mode") or params.get("flatLay.mode"):
        return False
    if params.get("ghostMannequin.mode") or params.get("virtualModel.mode"):
        return False
    if params.get("editWithAI.mode") or params.get("expand.mode") or params.get("uncrop.mode"):
        return False
    return params.get("removeBackground") == "true"


def _basic_api_key_headers() -> tuple[str | None, dict]:
    api_key = (getattr(settings, "PHOTOROOM_BASIC_API_KEY", "") or "").strip()
    if not api_key:
        return None, {}
    return api_key, {"x-api-key": api_key}


def _parse_output_size(raw: str) -> tuple[int, int]:
    try:
        w, h = raw.lower().split("x", 1)
        return max(64, int(w)), max(64, int(h))
    except (ValueError, AttributeError):
        return 1080, 1080


def _parse_padding_ratio(raw: str | float | None) -> float:
    if raw is None:
        return 0.06
    text = str(raw).strip().rstrip("%")
    try:
        val = float(text)
    except (TypeError, ValueError):
        return 0.06
    if str(raw).strip().endswith("%"):
        return min(max(val / 100.0, 0.0), 0.45)
    return min(max(val, 0.0), 0.45)


def composite_cutout_on_white(
    cutout_rgba: bytes,
    *,
    output_size: str = "1080x1080",
    padding: str | float = "0.06",
    export_format: str = "jpeg",
) -> bytes | None:
    """Place transparent PNG cutout on solid white canvas with padding."""
    try:
        from PIL import Image
    except ImportError:
        logger.error("Pillow required for Basic cutout composite")
        return None

    try:
        fg = Image.open(BytesIO(cutout_rgba)).convert("RGBA")
    except Exception as exc:
        logger.warning("Basic cutout decode failed: %s", exc)
        return None

    canvas_w, canvas_h = _parse_output_size(output_size)
    pad = _parse_padding_ratio(padding)
    inner_w = max(1, int(canvas_w * (1 - 2 * pad)))
    inner_h = max(1, int(canvas_h * (1 - 2 * pad)))

    fg.thumbnail((inner_w, inner_h), Image.Resampling.LANCZOS)
    fw, fh = fg.size
    canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
    x = (canvas_w - fw) // 2
    y = (canvas_h - fh) // 2
    canvas.paste(fg, (x, y), fg)

    buf = BytesIO()
    fmt = (export_format or "jpeg").lower()
    if fmt == "png":
        canvas.save(buf, format="PNG")
    else:
        canvas.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def photoroom_basic_segment(image_url: str, *, file_bytes: bytes | None = None) -> bytes | None:
    """Call Basic v1/segment; returns PNG with alpha or None."""
    from apps.products.photoroom import _load_image_bytes, _resolve_public_image_url

    api_key, headers = _basic_api_key_headers()
    if not api_key:
        return None

    if not file_bytes:
        public_url = _resolve_public_image_url(image_url)
        if public_url:
            try:
                resp = requests.post(
                    PHOTOROOM_SEGMENT_URL,
                    headers=headers,
                    data={"imageUrl": public_url},
                    timeout=120,
                )
                resp.raise_for_status()
                if resp.content:
                    return resp.content
            except Exception as exc:
                logger.warning("Basic segment URL failed, trying upload: %s", exc)

        loaded = _load_image_bytes(image_url)
        if not loaded:
            return None
        file_bytes, filename = loaded
    else:
        filename = "image.jpg"

    try:
        resp = requests.post(
            PHOTOROOM_SEGMENT_URL,
            headers=headers,
            files={"image_file": (filename, file_bytes, "image/jpeg")},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.content or None
    except Exception as exc:
        logger.error("Photoroom Basic segment failed: %s", exc)
        return None


def run_basic_white_cutout(
    image_url: str,
    params: dict[str, str],
    *,
    file_bytes: bytes | None = None,
) -> bytes | None:
    """Basic segment + local white composite matching Plus output params."""
    cutout = photoroom_basic_segment(image_url, file_bytes=file_bytes)
    if not cutout:
        return None
    return composite_cutout_on_white(
        cutout,
        output_size=params.get("outputSize", "1080x1080"),
        padding=params.get("padding", "0.06"),
        export_format=params.get("export.format", "jpeg"),
    )
