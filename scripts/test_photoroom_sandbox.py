#!/usr/bin/env python
"""Smoke test Photoroom Plus sandbox (v2/edit) — no Django required."""

from __future__ import annotations

import os
import sys
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
EDIT_URL = "https://image-api.photoroom.com/v2/edit"


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
    output_path = test_dir / "plus_sandbox_result.jpg"
    input_path.write_bytes(_make_test_product_jpeg())

    params = {
        "removeBackground": "true",
        "background.color": "FFFFFF",
        "outputSize": "1080x1080",
        "padding": "0.12",
        "shadow.mode": "ai.soft",
        "export.format": "jpeg",
    }

    print(f"Input:  {input_path} ({input_path.stat().st_size} bytes)")
    print(f"Mode:   {'sandbox' if sandbox else 'live'}")
    print(f"POST   {EDIT_URL}")

    resp = requests.post(
        EDIT_URL,
        headers={"x-api-key": api_key},
        files={"imageFile": ("input.jpg", input_path.read_bytes(), "image/jpeg")},
        data=params,
        timeout=120,
    )

    if resp.status_code != 200:
        print(f"ERROR: HTTP {resp.status_code}")
        print(resp.text[:800])
        return 1

    if not resp.content:
        print("ERROR: empty response body")
        return 1

    output_path.write_bytes(resp.content)
    with Image.open(output_path) as img:
        print(f"Output: {output_path} ({output_path.stat().st_size} bytes, {img.size[0]}x{img.size[1]})")
    print("OK — Plus sandbox test passed (watermark expected in sandbox mode)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
