"""
Photoroom Batch API — async bulk polish for Market Day / CSV catalog (P2).

Docs: https://docs.photoroom.com/image-editing-api-plus-plan/batch-editing
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger(__name__)

PHOTOROOM_BATCH_URL = "https://image-api.photoroom.com/v2/batch"


@dataclass
class BatchJobResult:
    batch_id: str
    status: str
    item_count: int = 0
    error: str = ""


def batch_api_enabled() -> bool:
    return bool(
        getattr(settings, "PHOTOROOM_BATCH_API_ENABLED", False)
        and getattr(settings, "PHOTOROOM_API_KEY", "")
    )


def submit_batch_edit(items: list[dict]) -> BatchJobResult | None:
    """
    Submit a batch of v2/edit jobs. Each item: {imageUrl, params dict}.

    Returns batch_id for polling (implement poll_batch_status separately).
    """
    if not batch_api_enabled() or not items:
        return None

    import requests

    api_key = getattr(settings, "PHOTOROOM_API_KEY", "")
    if getattr(settings, "PHOTOROOM_SANDBOX", False) and not api_key.startswith("sandbox_"):
        api_key = f"sandbox_{api_key}"

    try:
        resp = requests.post(
            PHOTOROOM_BATCH_URL,
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json={"items": items[:50]},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return BatchJobResult(
            batch_id=str(data.get("id") or data.get("batchId") or ""),
            status=data.get("status") or "submitted",
            item_count=len(items),
        )
    except Exception as exc:
        logger.warning("Photoroom batch submit failed: %s", exc)
        return BatchJobResult(batch_id="", status="failed", error=str(exc)[:500])
