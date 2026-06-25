"""Unified asset intake — Snap, manual, brief all land on proposals."""

from __future__ import annotations

from apps.products.business_assets import sync_asset_from_product
from apps.products.models import BusinessAsset, Product


def create_manual_asset(
    user,
    *,
    title: str,
    description: str = "",
    asset_type: str = BusinessAsset.AssetType.PRODUCT,
    offering_type: str = "product",
) -> BusinessAsset:
    product = Product.objects.create(
        user=user,
        name=title[:200],
        description=description,
        offering_type=offering_type,
        source=Product.Source.MANUAL,
        is_active=True,
    )
    return sync_asset_from_product(
        product,
        source=BusinessAsset.Source.MANUAL,
        status=BusinessAsset.Status.DRAFT,
    )
