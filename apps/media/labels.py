"""User-facing labels for media orchestration backends (no vendor names in UI)."""

from __future__ import annotations

REEL_BACKEND_LABELS = {
    "kling": "Cinematic reel",
    "photoroom": "Product motion",
    "ffmpeg": "Motion reel",
}

REEL_COMPOSE_HINTS = {
    "kling": "Cinematic motion · music",
    "photoroom": "Product motion · music",
    "ffmpeg": "Music · crossfade",
}

CAROUSEL_BACKEND_LABELS = {
    "bannerbear": "Branded carousel",
    "local": "AI carousel",
}

FORMAT_LABELS = {
    "single_post": "Feed post",
    "carousel": "Carousel",
    "story": "Story",
    "reel": "Reel",
    "tiktok": "TikTok",
    "whatsapp_offer": "WhatsApp offer",
}


def reel_backend_label(backend: str | None) -> str:
    if not backend:
        return REEL_BACKEND_LABELS["ffmpeg"]
    return REEL_BACKEND_LABELS.get(backend, REEL_BACKEND_LABELS["ffmpeg"])


def reel_compose_hint(backend: str | None) -> str:
    if not backend:
        return REEL_COMPOSE_HINTS["ffmpeg"]
    return REEL_COMPOSE_HINTS.get(backend, REEL_COMPOSE_HINTS["ffmpeg"])


def carousel_backend_label(backend: str | None) -> str:
    if not backend:
        return CAROUSEL_BACKEND_LABELS["local"]
    return CAROUSEL_BACKEND_LABELS.get(backend, CAROUSEL_BACKEND_LABELS["local"])


def format_label(fmt: str) -> str:
    return FORMAT_LABELS.get(fmt, fmt.replace("_", " ").title())
