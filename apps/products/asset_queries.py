"""BusinessAsset queries for Studio and intake."""

from __future__ import annotations

from apps.products.models import BusinessAsset


def studio_assets_for_user(user, *, status=None, asset_type=None, q=None, limit=12):
    qs = BusinessAsset.objects.filter(user=user).select_related("product").order_by("-updated_at")
    if status:
        qs = qs.filter(status=status)
    if asset_type:
        qs = qs.filter(asset_type=asset_type)
    if q:
        qs = qs.filter(title__icontains=q)
    return list(qs[:limit])
