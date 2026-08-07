"""Normalized intelligence metadata for BusinessAsset."""

from __future__ import annotations

from typing import Any


def normalize_asset_metadata(raw: dict | None) -> dict[str, Any]:
    meta = dict(raw or {})
    intel = dict(meta.get("intelligence") or {})
    for key in ("objective", "campaign_angle", "target_audience", "audience_hints"):
        if key in meta and key not in intel:
            intel[key] = meta[key]
    if meta.get("vision_analysis"):
        vision = meta["vision_analysis"]
        if isinstance(vision, dict):
            intel.setdefault("campaign_angle", vision.get("campaign_angle", ""))
            intel.setdefault("target_audience", vision.get("target_audience", ""))
    if intel.get("target_audience") and not intel.get("audience_hints"):
        intel["audience_hints"] = [intel["target_audience"]]
    meta["intelligence"] = intel
    return meta


def merge_intelligence(
    asset,
    *,
    objective: str = "",
    campaign_angle: str = "",
    target_audience: str = "",
    vision_analysis: dict | None = None,
    audience_hints: list | None = None,
) -> None:
    meta = normalize_asset_metadata(getattr(asset, "metadata", None) or {})
    intel = meta["intelligence"]
    if objective:
        intel["objective"] = objective
    if campaign_angle:
        intel["campaign_angle"] = campaign_angle
        meta["campaign_angle"] = campaign_angle
    if target_audience:
        intel["target_audience"] = target_audience
        meta["target_audience"] = target_audience
    if audience_hints:
        intel["audience_hints"] = list(audience_hints)
    if vision_analysis:
        meta["vision_analysis"] = vision_analysis
    asset.metadata = meta
    asset.save(update_fields=["metadata", "updated_at"])
