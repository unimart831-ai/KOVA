#!/usr/bin/env python
"""Smoke test Photoroom Basic sandbox (v1/segment) — no Django required."""

from __future__ import annotations

import os
import sys
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SEGMENT_URL = "https://sdk.photoroom.com/v1/segment"


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _make_test_product_jpeg() -> bytes:
    img = Image.new("RGB", (800, 800), "#E8EAED")
    draw = ImageDraw.Draw(img)
    draw.ellipse((220, 180, 580, 620), fill="#2563EB", outline="#1E40AF", width=6)
    draw.rectangle((300, 520, 500, 680), fill="#F59E0B")
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _fit_to_square_jpeg(image_bytes: bytes, bg_hex: str = "FFFFFF") -> bytes:
    bg = tuple(int(bg_hex[i : i + 2], 16) for i in (0, 2, 4))
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((1080, 1080), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (1080, 1080), bg)
    x = (1080 - img.width) // 2
    y = (1080 - img.height) // 2
    canvas.paste(img, (x, y))
    out = BytesIO()
    canvas.save(out, format="JPEG", quality=92, optimize=True)
    return out.getvalue()


def main() -> int:
    _load_dotenv()
    api_key = os.environ.get("PHOTOROOM_API_KEY", "").strip()
    if not api_key:
        print("ERROR: Set PHOTOROOM_API_KEY in kova_agent/.env")
        return 1

    sandbox = os.environ.get("PHOTOROOM_SANDBOX", "True").lower() in ("1", "true", "yes")
    if sandbox and not api_key.startswith("sandbox_"):
        api_key = f"sandbox_{api_key}"

    test_dir = ROOT / "tmp" / "photoroom_test"
    test_dir.mkdir(parents=True, exist_ok=True)
    input_path = test_dir / "input.jpg"
    output_path = test_dir / "sandbox_result.jpg"
    input_path.write_bytes(_make_test_product_jpeg())

    print(f"Input:  {input_path} ({input_path.stat().st_size} bytes)")
    print(f"Mode:   {'sandbox' if sandbox else 'live'}")
    print("POST   https://sdk.photoroom.com/v1/segment")

    resp = requests.post(
        SEGMENT_URL,
        headers={"x-api-key": api_key},
        files={"image_file": ("input.jpg", input_path.read_bytes(), "image/jpeg")},
        data={"bg_color": "#FFFFFF", "size": "hd", "format": "jpg", "crop": "false"},
        timeout=120,
    )

    if resp.status_code != 200:
        print(f"ERROR: HTTP {resp.status_code}")
        print(resp.text[:500])
        return 1

    if not resp.content:
        print("ERROR: empty response body")
        return 1

    result = _fit_to_square_jpeg(resp.content, "FFFFFF")
    output_path.write_bytes(result)
    print(f"Output: {output_path} ({output_path.stat().st_size} bytes)")
    print("OK — sandbox test passed (watermark expected in sandbox mode)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
