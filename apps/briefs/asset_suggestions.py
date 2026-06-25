"""Campaign opportunities tied to catalog assets."""

from __future__ import annotations

from apps.products.asset_queries import studio_assets_for_user
from apps.products.models import BusinessAsset


def asset_campaign_opportunities(user, *, limit: int = 3) -> list[dict]:
    assets = studio_assets_for_user(
        user,
        status=BusinessAsset.Status.PUBLISHED,
        limit=limit * 2,
    )
    if not assets:
        assets = studio_assets_for_user(user, limit=limit)
    out = []
    for asset in assets[:limit]:
        meta = asset.metadata or {}
        intel = meta.get("intelligence") or {}
        out.append({
            "asset_id": str(asset.pk),
            "title": asset.title,
            "asset_type": asset.get_asset_type_display(),
            "angle": intel.get("campaign_angle") or f"Promote {asset.title}",
            "proposals_url_name": "content:asset_proposals",
        })
    return out
