import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="check-stock-alerts")
def check_stock_alerts():
    """
    Daily task: scan all active products for stock issues and create alerts.
    - Low stock warnings (quantity below threshold)
    - Out-of-stock items that still have scheduled content
    - Featured products with no recent content
    - Stock-content mismatches (scheduled posts for OOS products)
    - In-stock products with high demand but no content
    """
    from apps.products.models import Product, StockAlert
    from apps.products.utils import (
        detect_stock_content_mismatches,
        invalidate_product_cache,
    )

    from django.contrib.auth import get_user_model
    User = get_user_model()

    users_with_products = (
        User.objects.filter(products__is_active=True)
        .distinct()
    )

    total_alerts = 0

    for user in users_with_products:
        products = Product.objects.filter(user=user, is_active=True)
        alerts_created = 0

        for product in products:
            # Skip services and digital products — no stock to track
            if not product.tracks_stock:
                continue

            # Auto-detect low stock from quantity
            if (
                product.quantity is not None
                and product.stock_status == Product.StockStatus.IN_STOCK
                and product.quantity <= product.low_stock_threshold
            ):
                if product.quantity <= 0:
                    product.stock_status = Product.StockStatus.OUT_OF_STOCK
                else:
                    product.stock_status = Product.StockStatus.LOW_STOCK
                product.save(update_fields=["stock_status"])

            # Low stock alert
            if product.stock_status == Product.StockStatus.LOW_STOCK:
                exists = StockAlert.objects.filter(
                    product=product,
                    alert_type=StockAlert.AlertType.LOW_STOCK,
                    created_at__date=timezone.now().date(),
                ).exists()
                if not exists:
                    StockAlert.objects.create(
                        user=user,
                        product=product,
                        alert_type=StockAlert.AlertType.LOW_STOCK,
                        message=f"⚠️ {product.name} is running low ({product.quantity or 'few'} remaining).",
                    )
                    alerts_created += 1

            # Out of stock alert
            if product.stock_status == Product.StockStatus.OUT_OF_STOCK:
                exists = StockAlert.objects.filter(
                    product=product,
                    alert_type=StockAlert.AlertType.OUT_OF_STOCK,
                    created_at__date=timezone.now().date(),
                ).exists()
                if not exists:
                    StockAlert.objects.create(
                        user=user,
                        product=product,
                        alert_type=StockAlert.AlertType.OUT_OF_STOCK,
                        message=f"🔴 {product.name} is out of stock. Content promoting it should be paused.",
                    )
                    alerts_created += 1

        # ── Featured products with no content in 14 days ─────────────
        try:
            from apps.content.models import Post
            featured_products = products.filter(is_featured=True)
            two_weeks_ago = timezone.now() - timedelta(days=14)

            for product in featured_products:
                # Check if any published post mentions this product recently
                recent_mention = Post.objects.filter(
                    user=user,
                    status=Post.Status.PUBLISHED,
                    published_at__gte=two_weeks_ago,
                    content_text__icontains=product.name,
                ).exists()

                if not recent_mention:
                    exists = StockAlert.objects.filter(
                        product=product,
                        alert_type=StockAlert.AlertType.FEATURED_NO_CONTENT,
                        created_at__date=timezone.now().date(),
                    ).exists()
                    if not exists:
                        StockAlert.objects.create(
                            user=user,
                            product=product,
                            alert_type=StockAlert.AlertType.FEATURED_NO_CONTENT,
                            message=(
                                f"⭐ {product.name} is featured but hasn't been mentioned "
                                f"in any content for 14+ days. Consider creating content for it."
                            ),
                        )
                        alerts_created += 1
        except Exception as e:
            logger.warning("Featured-no-content check failed for %s: %s", user.email, e)

        # ── Stock-content mismatches (OOS products with scheduled posts) ──
        try:
            mismatches = detect_stock_content_mismatches(user)
            for m in mismatches:
                if m["severity"] == "critical":
                    exists = StockAlert.objects.filter(
                        user=user,
                        alert_type=StockAlert.AlertType.OUT_OF_STOCK,
                        message__icontains=m["product_name"],
                        created_at__date=timezone.now().date(),
                    ).exists()
                    if not exists:
                        StockAlert.objects.create(
                            user=user,
                            product=products.filter(name=m["product_name"]).first(),
                            alert_type=StockAlert.AlertType.OUT_OF_STOCK,
                            message=f"🔴 MISMATCH: {m['action']}",
                        )
                        alerts_created += 1
        except Exception as e:
            logger.warning("Stock-content mismatch check failed for %s: %s", user.email, e)

        if alerts_created:
            invalidate_product_cache(user)
            total_alerts += alerts_created

    logger.info("Stock alerts check complete: %d alerts created for %d users", total_alerts, users_with_products.count())
    return {"alerts_created": total_alerts, "users_checked": users_with_products.count()}


@shared_task(name="products.auto_promote_products")
def auto_promote_products():
    """
    Daily task: auto-create content seeds for products that haven't been
    promoted recently. Turns stock intelligence into actual content.

    Priority order:
      1. Featured products with no content in 7+ days
      2. Low-stock products (urgency angle)
      3. Never-promoted products
      4. Least-recently-promoted products

    Limits: max 2 auto-seeds per user per day to avoid flooding.
    Skips: out-of-stock physical products, users with no connected platforms.
    """
    from apps.content.models import ContentSeed, Post
    from apps.platforms.models import SocialAccount
    from apps.products.models import Product

    from django.contrib.auth import get_user_model
    User = get_user_model()

    users_with_products = (
        User.objects.filter(products__is_active=True)
        .distinct()
    )

    total_seeds = 0
    now = timezone.now()
    seven_days_ago = now - timedelta(days=7)

    for user in users_with_products:
        # Skip users with no connected platforms
        platforms = list(
            SocialAccount.objects.filter(user=user, is_active=True)
            .values_list("platform", flat=True)
        )
        if not platforms:
            continue

        # Don't exceed 2 auto-seeds per user per day
        today_auto_seeds = ContentSeed.objects.filter(
            user=user,
            notes__startswith="Auto-promoted:",
            created_at__date=now.date(),
        ).count()
        if today_auto_seeds >= 2:
            continue

        remaining = 2 - today_auto_seeds
        promotable = Product.objects.promotable(user).filter(is_active=True)
        if not promotable.exists():
            continue

        # Build priority queue of products needing content
        candidates = []

        for product in promotable:
            # Check for recent content (post or seed) about this product
            has_recent_post = Post.objects.filter(
                user=user,
                product=product,
                status__in=[Post.Status.PUBLISHED, Post.Status.APPROVED, Post.Status.SCHEDULED],
                created_at__gte=seven_days_ago,
            ).exists()
            if has_recent_post:
                continue

            has_recent_seed = ContentSeed.objects.filter(
                user=user,
                product=product,
                created_at__gte=seven_days_ago,
            ).exists()
            if has_recent_seed:
                continue

            # Calculate priority score
            score = 0
            if product.is_featured:
                score += 30
            if product.stock_status == Product.StockStatus.LOW_STOCK:
                score += 20
            # Never-promoted products get a boost
            total_posts = Post.objects.filter(user=user, product=product).count()
            if total_posts == 0:
                score += 15
            # Older products without recent content rank higher
            days_since_update = (now - product.updated_at).days
            score += min(days_since_update, 10)

            candidates.append((score, product))

        # Sort by priority (highest score first)
        candidates.sort(key=lambda x: x[0], reverse=True)

        seeds_created = 0
        for _score, product in candidates[:remaining]:
            # Build context-aware idea based on product type and status
            idea = _build_promotion_idea(product)

            ContentSeed.objects.create(
                user=user,
                product=product,
                idea=idea,
                notes=f"Auto-promoted: {product.name} — no content in 7+ days.",
                target_platforms=platforms[:3],
            )
            seeds_created += 1
            logger.info(
                "Auto-promote seed created: %s for %s (score=%d)",
                product.name, user.email, _score,
            )

        total_seeds += seeds_created

    logger.info("Auto-promote complete: %d seeds created", total_seeds)
    return {"seeds_created": total_seeds, "users_processed": users_with_products.count()}


def _build_promotion_idea(product):
    """Build a rich, type-aware content seed idea for a product."""
    from apps.products.models import Product

    name = product.name
    price = product.display_price

    if product.offering_type == Product.OfferingType.SERVICE:
        idea = (
            f"Promote our service: {name}."
            f"{f' Starting at {price}.' if price else ''}"
            f" Highlight the value, results clients get, and why they should book now."
            f" Use a compelling hook that addresses a pain point this service solves."
        )
    elif product.offering_type == Product.OfferingType.DIGITAL:
        idea = (
            f"Promote our digital product: {name}."
            f"{f' Price: {price}.' if price else ''}"
            f" Focus on instant access, the transformation it delivers, and a strong CTA."
        )
    elif product.stock_status == Product.StockStatus.LOW_STOCK:
        qty = product.quantity
        idea = (
            f"🔥 URGENCY: {name} is running low"
            f"{f' — only {qty} left' if qty else ''}!"
            f"{f' Price: {price}.' if price else ''}"
            f" Create scarcity-driven content. 'Almost gone', 'Don't miss out'."
            f" Drive immediate action."
        )
    elif product.is_featured:
        idea = (
            f"⭐ Spotlight our featured product: {name}."
            f"{f' Price: {price}.' if price else ''}"
            f" This is a hero product — give it premium treatment."
            f" Highlight what makes it special and why customers love it."
        )
    else:
        idea = (
            f"Create engaging content about: {name}."
            f"{f' Price: {price}.' if price else ''}"
            f" Find a fresh angle — could be a use case, customer benefit,"
            f" behind-the-scenes, or a comparison with alternatives."
        )

    if product.product_url:
        idea += f" Include link: {product.product_url}"

    if product.tags:
        idea += f" Keywords: {', '.join(product.tags)}."

    return idea
