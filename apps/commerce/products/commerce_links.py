"""Public Commerce Link helpers — /shop/<page_slug>/<commerce_slug>/"""

from __future__ import annotations

from django.utils.text import slugify


def resolve_page_slug(profile) -> str:
    """Public shop prefix slug for a business."""
    if profile.page_slug:
        return profile.page_slug
    user = profile.user
    if user.username:
        return user.username
    return str(user.pk).replace("-", "")[:12]


def ensure_commerce_slug(product, *, save: bool = True, force: bool = False) -> str:
    """Assign a unique commerce_slug for the product's owner."""
    if product.commerce_slug and not force:
        return product.commerce_slug

    from apps.commerce.products.models import Product

    base = slugify(product.name)[:50] or "item"
    candidate = base
    n = 1
    while Product.objects.filter(
        user=product.user, commerce_slug=candidate,
    ).exclude(pk=product.pk).exists():
        n += 1
        candidate = f"{base}-{n}"[:60]

    product.commerce_slug = candidate
    if save:
        product.save(update_fields=["commerce_slug", "updated_at"])
    return candidate


def commerce_link_path(product, profile=None, *, save_slug: bool = False) -> str:
    """Build the public shop path without reverse() — safe inside post_save signals."""
    profile = profile or product.user.profile
    page_slug = resolve_page_slug(profile)
    slug = product.commerce_slug or ensure_commerce_slug(product, save=save_slug)
    return f"/shop/{page_slug}/{slug}/"


def commerce_link_url(product, request=None) -> str:
    path = commerce_link_path(product)
    if request:
        return request.build_absolute_uri(path)
    from django.conf import settings

    site = getattr(settings, "SITE_URL", "").rstrip("/")
    if site:
        return f"{site}{path}"
    return path


def resolve_public_shop(page_slug: str):
    """Lookup a seller profile and their active commerce products."""
    from apps.core.accounts.models import UserProfile
    from apps.commerce.products.models import Product

    profile = UserProfile.objects.select_related("user").filter(
        page_slug=page_slug,
    ).first()
    if not profile:
        profile = UserProfile.objects.select_related("user").filter(
            user__username=page_slug,
        ).first()
    if not profile:
        return None, []

    products = list(
        Product.objects.filter(
            user=profile.user,
            is_active=True,
        ).exclude(commerce_slug="").select_related("category").order_by(
            "-is_featured", "-created_at",
        )
    )
    return profile, products


def shop_index_path(profile) -> str:
    return f"/shop/{resolve_page_slug(profile)}/"


def resolve_public_product(page_slug: str, commerce_slug: str):
    """Lookup an active product on a public shop page."""
    from apps.core.accounts.models import UserProfile
    from apps.commerce.products.models import Product

    profile = UserProfile.objects.select_related("user").filter(
        page_slug=page_slug,
    ).first()
    if not profile:
        profile = UserProfile.objects.select_related("user").filter(
            user__username=page_slug,
        ).first()
    if not profile:
        return None, None

    product = Product.objects.filter(
        user=profile.user,
        commerce_slug=commerce_slug,
        is_active=True,
    ).select_related("user", "category").first()
    if not product:
        return None, None
    if product.stock_status == Product.StockStatus.OUT_OF_STOCK:
        return profile, product
    return profile, product


def related_public_products(user, exclude_pk, category_id=None, *, limit: int = 4):
    """Lightweight related-product fetch for PDP (avoids full shop reload)."""
    from apps.commerce.products.models import Product

    base = Product.objects.filter(
        user=user,
        is_active=True,
    ).exclude(commerce_slug="").exclude(pk=exclude_pk).select_related("category")

    if category_id:
        same_cat = list(
            base.filter(category_id=category_id).order_by("-is_featured", "-created_at")[:limit]
        )
        if len(same_cat) >= limit:
            return same_cat
        other = list(
            base.exclude(category_id=category_id).order_by("-is_featured", "-created_at")[
                : limit - len(same_cat)
            ]
        )
        return same_cat + other

    return list(base.order_by("-is_featured", "-created_at")[:limit])
