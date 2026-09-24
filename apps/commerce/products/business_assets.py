"""BusinessAsset helpers — bridge from legacy Product catalog to unified assets."""

from __future__ import annotations

from apps.commerce.products.models import BusinessAsset, Product


_ASSET_TYPE_FROM_OFFERING = {
    Product.OfferingType.PRODUCT: BusinessAsset.AssetType.PRODUCT,
    Product.OfferingType.SERVICE: BusinessAsset.AssetType.SERVICE,
    Product.OfferingType.DIGITAL: BusinessAsset.AssetType.DIGITAL,
}


_SOURCE_FROM_PRODUCT = {
    Product.Source.SNAP: BusinessAsset.Source.SNAP,
    Product.Source.MANUAL: BusinessAsset.Source.MANUAL,
    Product.Source.CSV: BusinessAsset.Source.IMPORT,
    Product.Source.API: BusinessAsset.Source.IMPORT,
    Product.Source.MARKETPLACE: BusinessAsset.Source.IMPORT,
}


def asset_type_for_product(product: Product) -> str:
    return _ASSET_TYPE_FROM_OFFERING.get(product.offering_type, BusinessAsset.AssetType.PRODUCT)


def source_for_product(product: Product, *, override: str = "") -> str:
    if override:
        return override
    return _SOURCE_FROM_PRODUCT.get(product.source, BusinessAsset.Source.MANUAL)


def status_for_product(product: Product) -> str:
    if not product.is_active:
        return BusinessAsset.Status.ARCHIVED
    return BusinessAsset.Status.PUBLISHED


def sync_asset_from_product(
    product: Product,
    *,
    source: str = "",
    status: str = "",
) -> BusinessAsset:
    """Create or update the BusinessAsset row for a Product."""
    asset, _created = BusinessAsset.objects.get_or_create(
        product=product,
        defaults={
            "user": product.user,
            "asset_type": asset_type_for_product(product),
            "title": product.name,
            "description": product.description,
            "status": status or status_for_product(product),
            "source": source_for_product(product, override=source),
            "metadata": {
                "price": str(product.price) if product.price is not None else "",
                "currency": product.currency,
                "commerce_slug": product.commerce_slug,
                "offering_type": product.offering_type,
            },
        },
    )
    if asset.pk:
        asset.user = product.user
        asset.asset_type = asset_type_for_product(product)
        asset.title = product.name
        asset.description = product.description
        if status:
            asset.status = status
        else:
            asset.status = status_for_product(product)
        if source:
            asset.source = source
        metadata = dict(asset.metadata or {})
        metadata.update({
            "price": str(product.price) if product.price is not None else "",
            "currency": product.currency,
            "commerce_slug": product.commerce_slug,
            "offering_type": product.offering_type,
        })
        asset.metadata = metadata
        asset.save()
    if asset.asset_type == BusinessAsset.AssetType.SERVICE:
        pass
    return asset
