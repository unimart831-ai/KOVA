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


# ── Snap to Sell ─────────────────────────────────────────────────────

@shared_task(name="products.snap_to_sell_analyze")
def snap_to_sell_analyze(product_id: str):
    """
    Vision AI analyzes a product photo, enriches the product description,
    then auto-creates a ContentSeed and fires the content pipeline.

    Called after the user snaps/uploads a photo, provides name + price,
    and hits "Launch".
    """
    from apps.agents.llm import analyze_image, generate, parse_llm_json
    from apps.content.models import ContentSeed
    from apps.content.tasks import generate_from_seed
    from apps.platforms.models import SocialAccount
    from apps.products.models import Product
    from apps.utils import fire_task

    try:
        product = Product.objects.select_related("user", "category").get(pk=product_id)
    except Product.DoesNotExist:
        logger.error("Snap to Sell: product %s not found", product_id)
        return {"error": "Product not found"}

    user = product.user

    # ── Step 1: Vision AI — analyze the product photo ────────────────
    if not product.image:
        logger.warning("Snap to Sell: product %s has no image", product_id)
        return {"error": "No image attached"}

    image_url = product.image.url
    # If it's a relative URL, we can't send it to the API — use base64
    if not image_url.startswith("http"):
        import base64
        with open(product.image.path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        # Detect mime type
        ext = product.image.name.rsplit(".", 1)[-1].lower()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/jpeg")
        image_url = f"data:{mime};base64,{encoded}"

    vision_prompt = (
        "You are a product photography analyst for a social media marketing platform.\n"
        f"Product name: {product.name}\n"
        f"Price: {product.display_price or 'not set'}\n\n"
        "Analyze this product image and return JSON with:\n"
        "{\n"
        '  "description": "A compelling 2-3 sentence product description for social media marketing",\n'
        '  "key_features": ["feature1", "feature2", "feature3"],\n'
        '  "target_audience": "Who would buy this",\n'
        '  "suggested_tags": ["tag1", "tag2", "tag3"],\n'
        '  "visual_style": "Describe the visual aesthetic (colors, mood, quality)",\n'
        '  "campaign_angle": "Best marketing angle for social media"\n'
        "}"
    )

    try:
        vision_resp = analyze_image(
            image_url=image_url,
            prompt=vision_prompt,
            system="You are a product marketing expert. Always respond with valid JSON only.",
            json_mode=True,
            max_tokens=800,
        )
        analysis = parse_llm_json(vision_resp.content)
    except Exception as exc:
        logger.error("Snap to Sell vision failed for %s: %s", product_id, exc)
        analysis = {
            "description": f"Quality {product.name} — perfect for your needs.",
            "key_features": [],
            "target_audience": "General consumers",
            "suggested_tags": [],
            "visual_style": "Product photo",
            "campaign_angle": "Product showcase",
        }

    # ── Step 2: Enrich the product with AI analysis ──────────────────
    if not product.description and analysis.get("description"):
        product.description = analysis["description"]

    if analysis.get("suggested_tags"):
        existing_tags = set(product.tags or [])
        new_tags = list(existing_tags | set(analysis["suggested_tags"][:5]))
        product.tags = new_tags[:8]  # Cap at 8 tags

    product.save(update_fields=["description", "tags", "updated_at"])

    # ── Step 3: Create a content seed and launch the campaign ────────
    platforms = list(
        SocialAccount.objects.filter(user=user, is_active=True)
        .values_list("platform", flat=True)
    )

    features_text = ""
    if analysis.get("key_features"):
        features_text = " Key features: " + ", ".join(analysis["key_features"][:3]) + "."

    audience_text = ""
    if analysis.get("target_audience"):
        audience_text = f" Target audience: {analysis['target_audience']}."

    seed = ContentSeed.objects.create(
        user=user,
        product=product,
        idea=(
            f"📸 Snap to Sell: Promote {product.name}."
            f"{f' Price: {product.display_price}.' if product.display_price else ''}"
            f"{features_text}"
            f" Campaign angle: {analysis.get('campaign_angle', 'product showcase')}."
            f"{audience_text}"
            f" Use the product photo as the hero image."
        ),
        notes=(
            f"AI Vision Analysis:\n"
            f"Description: {analysis.get('description', '')}\n"
            f"Visual style: {analysis.get('visual_style', '')}\n"
            f"Source: Snap to Sell — user-uploaded product photo"
        ),
        target_platforms=platforms[:3] if platforms else [],
    )

    fire_task(generate_from_seed, str(seed.id))

    logger.info(
        "Snap to Sell complete: product=%s, seed=%s, user=%s",
        product_id, seed.id, user.email,
    )
    return {
        "product_id": str(product.pk),
        "seed_id": str(seed.pk),
        "analysis": analysis,
    }
