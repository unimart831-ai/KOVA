"""Bridge Lead CRM records to Conversion attribution for Growth dashboards."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def resolve_campaign_for_lead(lead):
    """Best-effort MarketingCampaign from lead FKs / UTM / source post."""
    if getattr(lead, "marketing_campaign_id", None):
        return lead.marketing_campaign

    from apps.create.content.campaign_attribution import resolve_marketing_campaign

    meta = lead.metadata or {}
    post = getattr(lead, "source_post", None)
    return resolve_marketing_campaign(
        lead.user,
        campaign_id=meta.get("campaign_id"),
        campaign_slug=meta.get("campaign_slug") or meta.get("utm_campaign", ""),
        utm_campaign=meta.get("utm_campaign", ""),
        post=post,
        metadata=meta,
    )


def attribute_lead_to_campaign(lead, *, campaign=None, emit_conversion: bool = True):
    """Attach campaign FK and optionally emit Conversion(type=lead)."""
    from apps.insight.analytics.models import Conversion

    resolved = campaign or resolve_campaign_for_lead(lead)
    updates = []

    if resolved and lead.marketing_campaign_id != resolved.pk:
        lead.marketing_campaign = resolved
        updates.append("marketing_campaign")
        meta = dict(lead.metadata or {})
        meta.setdefault("campaign_id", str(resolved.pk))
        if resolved.slug:
            meta.setdefault("campaign_slug", resolved.slug)
        lead.metadata = meta
        updates.append("metadata")

    if updates:
        lead.save(update_fields=updates + ["last_activity_at"])

    if not emit_conversion or not resolved:
        return resolved

    already = Conversion.objects.filter(
        user=lead.user,
        conversion_type=Conversion.ConversionType.LEAD,
        metadata__lead_id=str(lead.pk),
    ).exists()
    if already:
        return resolved

    try:
        from apps.create.content.campaign_attribution import create_attributed_conversion

        meta = dict(lead.metadata or {})
        meta["lead_id"] = str(lead.pk)
        create_attributed_conversion(
            lead.user,
            Conversion.ConversionType.LEAD,
            campaign=resolved,
            post=lead.source_post,
            utm_source=meta.get("utm_source", "") or lead.source_platform or "",
            utm_medium=meta.get("utm_medium", "") or lead.source_type or "",
            utm_campaign=meta.get("utm_campaign", "") or (resolved.slug or ""),
            event_name=f"lead:{lead.source_type}",
            metadata=meta,
        )
    except Exception:
        logger.exception("Failed to emit Conversion for lead %s", lead.pk)

    return resolved
