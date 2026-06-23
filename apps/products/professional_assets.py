"""Create portfolio / case-study BusinessAssets (no Product required)."""

from __future__ import annotations

from apps.products.models import BusinessAsset


def create_professional_asset(
    user,
    *,
    asset_type: str,
    title: str,
    description: str = "",
    metadata: dict | None = None,
    status: str = "",
) -> BusinessAsset:
    """Create a standalone professional asset."""
    valid = {
        BusinessAsset.AssetType.PORTFOLIO,
        BusinessAsset.AssetType.CASE_STUDY,
        BusinessAsset.AssetType.TESTIMONIAL,
    }
    if asset_type not in valid:
        asset_type = BusinessAsset.AssetType.PORTFOLIO

    return BusinessAsset.objects.create(
        user=user,
        asset_type=asset_type,
        title=title[:200],
        description=description,
        metadata=metadata or {},
        status=status or BusinessAsset.Status.PUBLISHED,
        source=BusinessAsset.Source.MANUAL,
    )


def create_portfolio_item(
    user,
    *,
    title: str,
    client: str = "",
    outcome: str = "",
    description: str = "",
) -> BusinessAsset:
    return create_professional_asset(
        user,
        asset_type=BusinessAsset.AssetType.PORTFOLIO,
        title=title,
        description=description,
        metadata={"client": client, "outcome": outcome, "asset_role": "portfolio"},
    )


def create_case_study(
    user,
    *,
    title: str,
    client: str = "",
    pain: str = "",
    outcome: str = "",
    description: str = "",
) -> BusinessAsset:
    return create_professional_asset(
        user,
        asset_type=BusinessAsset.AssetType.CASE_STUDY,
        title=title,
        description=description,
        metadata={
            "client": client,
            "pain": pain,
            "outcome": outcome,
            "asset_role": "case_study",
        },
    )


EDITABLE_ASSET_TYPES = frozenset({
    BusinessAsset.AssetType.PRODUCT,
    BusinessAsset.AssetType.PORTFOLIO,
    BusinessAsset.AssetType.CASE_STUDY,
})


def asset_context_for_product(product) -> dict:
    """Template context for professional asset fields on edit forms."""
    from apps.products.business_assets import sync_asset_from_product

    asset = getattr(product, "business_asset", None)
    if asset is None:
        try:
            asset = sync_asset_from_product(product)
        except Exception:
            asset = None
    meta = (asset.metadata or {}) if asset else {}
    asset_type = asset.asset_type if asset else BusinessAsset.AssetType.PRODUCT
    if asset_type not in EDITABLE_ASSET_TYPES:
        asset_type = BusinessAsset.AssetType.PRODUCT
    return {
        "asset": asset,
        "asset_type": asset_type,
        "asset_client": meta.get("client", ""),
        "asset_outcome": meta.get("outcome", ""),
        "asset_pain": meta.get("pain", ""),
    }


def apply_professional_asset_from_post(product, post_data) -> BusinessAsset | None:
    """Sync BusinessAsset type/metadata from product edit or studio edit POST."""
    from apps.products.business_assets import sync_asset_from_product

    asset_type = (post_data.get("asset_type") or "product").strip() or "product"
    if asset_type not in EDITABLE_ASSET_TYPES:
        asset_type = BusinessAsset.AssetType.PRODUCT

    asset = sync_asset_from_product(product)
    client = (post_data.get("asset_client") or post_data.get("client") or "").strip()[:120]
    outcome = (post_data.get("asset_outcome") or post_data.get("outcome") or "").strip()[:200]
    pain = (post_data.get("asset_pain") or post_data.get("pain") or "").strip()[:200]

    if asset_type == BusinessAsset.AssetType.PORTFOLIO:
        asset.asset_type = BusinessAsset.AssetType.PORTFOLIO
        asset.metadata = {
            **(asset.metadata or {}),
            "client": client,
            "outcome": outcome,
            "snap_mode": "portfolio",
        }
    elif asset_type == BusinessAsset.AssetType.CASE_STUDY:
        asset.asset_type = BusinessAsset.AssetType.CASE_STUDY
        asset.metadata = {
            **(asset.metadata or {}),
            "client": client,
            "pain": pain,
            "outcome": outcome,
            "snap_mode": "case_study",
        }
    else:
        from apps.products.business_assets import asset_type_for_product

        asset.asset_type = asset_type_for_product(product)
        meta = dict(asset.metadata or {})
        for key in ("client", "outcome", "pain", "snap_mode"):
            meta.pop(key, None)
        asset.metadata = meta

    asset.save(update_fields=["asset_type", "metadata", "updated_at"])
    return asset


def create_authority_post_from_asset(user, asset: BusinessAsset):
    """
    One-click: ContentSeed + blueprint + Create Agent for a showcase asset.
    Returns the seed; posts appear in Studio for approval.
    """
    from apps.content.models import ContentSeed
    from apps.content.blueprint_pipeline import attach_blueprint_to_seed
    from apps.content.tasks import generate_from_seed
    from apps.platforms.models import SocialAccount
    from apps.utils import fire_task

    type_labels = {
        BusinessAsset.AssetType.PORTFOLIO: "portfolio authority",
        BusinessAsset.AssetType.CASE_STUDY: "case study",
        BusinessAsset.AssetType.TESTIMONIAL: "client testimonial",
    }
    role = type_labels.get(asset.asset_type, "showcase")
    meta = asset.metadata or {}
    client = meta.get("client", "")
    idea_parts = [f"Authority post: {asset.title}"]
    if client:
        idea_parts.append(f"for {client}")
    idea_parts.append(f"— {role}")

    connected = list(
        SocialAccount.objects.filter(user=user, is_active=True).values_list("platform", flat=True)
    )
    preferred = ["linkedin", "facebook", "instagram"]
    platforms = [p for p in preferred if p in connected] or connected[:3]

    seed = ContentSeed.objects.create(
        user=user,
        product=asset.product,
        idea=" ".join(idea_parts),
        notes=asset.description or f"From showcase: {asset.title}",
        target_platforms=platforms,
        status=ContentSeed.SeedStatus.PROCESSING,
    )
    attach_blueprint_to_seed(
        seed,
        asset=asset,
        product=asset.product,
        platforms=platforms,
        objective="authority",
    )
    fire_task(generate_from_seed, str(seed.id))
    return seed
