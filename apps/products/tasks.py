import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


def _vision_image_url(image_field):
    """Return a public URL or base64 data URI suitable for vision LLM calls."""
    import base64

    from django.core.files.storage import default_storage

    url = image_field.url
    if url.startswith("http"):
        return url

    ext = image_field.name.rsplit(".", 1)[-1].lower() if image_field.name else "jpg"
    mime = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "gif": "image/gif",
    }.get(ext, "image/jpeg")
    try:
        with open(image_field.path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        with default_storage.open(image_field.name, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


@shared_task(name="products.expire_stale_commerce_payments")
def expire_stale_commerce_payments():
    """
    Periodic task: mark PENDING commerce payments older than 10 minutes as EXPIRED.
    Prevents ghost pending records from blocking idempotency and cluttering dashboards.
    """
    from apps.products.models import CommercePayment

    cutoff = timezone.now() - timedelta(minutes=10)
    expired_count = CommercePayment.objects.filter(
        status=CommercePayment.Status.PENDING,
        created_at__lt=cutoff,
    ).update(status=CommercePayment.Status.EXPIRED)

    if expired_count:
        logger.info("Expired %d stale commerce payments older than %s", expired_count, cutoff)
    return {"expired": expired_count}


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

        # ── In-stock products with surplus inventory but no recent promotion ──
        try:
            from apps.content.models import ContentSeed, Post

            two_weeks_ago = timezone.now() - timedelta(days=14)
            for product in products.filter(
                stock_status=Product.StockStatus.IN_STOCK,
                offering_type=Product.OfferingType.PRODUCT,
            ):
                if not product.tracks_stock or product.quantity is None:
                    continue
                if product.quantity <= product.low_stock_threshold * 2:
                    continue

                has_recent = (
                    Post.objects.filter(
                        user=user,
                        product=product,
                        created_at__gte=two_weeks_ago,
                    ).exists()
                    or ContentSeed.objects.filter(
                        user=user,
                        product=product,
                        created_at__gte=two_weeks_ago,
                    ).exists()
                )
                if has_recent:
                    continue

                exists = StockAlert.objects.filter(
                    product=product,
                    alert_type=StockAlert.AlertType.OVERSTOCK_NO_PROMO,
                    created_at__date=timezone.now().date(),
                ).exists()
                if not exists:
                    StockAlert.objects.create(
                        user=user,
                        product=product,
                        alert_type=StockAlert.AlertType.OVERSTOCK_NO_PROMO,
                        message=(
                            f"📦 {product.name} has {product.quantity} units in stock "
                            f"but no content in 14+ days. Consider promoting it."
                        ),
                    )
                    alerts_created += 1
        except Exception as e:
            logger.warning("Overstock-no-promo check failed for %s: %s", user.email, e)

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
    Daily task: randomly sample catalog products into content seeds.

    Not every user every day — ~30% receive one weighted-random product seed
    when they have promotable items not featured recently (3+ day gap).

    Skips: out-of-stock physical products, users with no connected platforms.
    """
    from apps.content.models import ContentSeed
    from apps.platforms.models import SocialAccount
    from apps.products.models import Product
    from apps.products.commerce_autopilot import commerce_autopilot_active
    from apps.products.utils import (
        sample_products_for_content,
        user_should_receive_catalog_sample,
    )

    from django.contrib.auth import get_user_model
    User = get_user_model()

    users_with_products = (
        User.objects.filter(products__is_active=True)
        .distinct()
    )

    total_seeds = 0
    now = timezone.now()

    for user in users_with_products:
        platforms = list(
            SocialAccount.objects.filter(user=user, is_active=True)
            .values_list("platform", flat=True)
        )
        if not platforms:
            continue

        if not commerce_autopilot_active(user):
            if not user_should_receive_catalog_sample(user, now.date()):
                continue

        today_samples = ContentSeed.objects.filter(
            user=user,
            notes__startswith="Catalog sample:",
            created_at__date=now.date(),
        ).count()
        if today_samples >= 1:
            continue

        sampled = sample_products_for_content(user, count=1, min_days_since_promotion=3)
        if not sampled:
            continue

        product = sampled[0]
        idea = _build_promotion_idea(product)

        seed = ContentSeed.objects.create(
            user=user,
            product=product,
            idea=idea,
            notes=f"Catalog sample: {product.name} — rotating catalog promotion.",
            target_platforms=platforms[:3],
        )
        from apps.content.tasks import generate_from_seed
        from apps.utils import fire_task

        fire_task(generate_from_seed, str(seed.id))
        total_seeds += 1
        logger.info(
            "Catalog sample seed created: %s for %s",
            product.name, user.email,
        )

    logger.info("Catalog sample complete: %d seeds created", total_seeds)
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

    from apps.products.product_cta import resolve_product_cta_url

    cta = resolve_product_cta_url(product)
    if cta:
        idea += f" Include link: {cta}"

    if product.tags:
        idea += f" Keywords: {', '.join(product.tags)}."

    return idea


# ── Offering-type-aware prompt builders ──────────────────────────────

def _build_vision_prompt(*, offering_type, name, display_price, num_images, photo_context="", name_is_placeholder=False):
    """Build the vision AI prompt based on offering type."""

    context_line = ""
    if photo_context:
        context_line = f"\nUser context about this photo: {photo_context}\n"

    placeholder_hint = ""
    if name_is_placeholder:
        placeholder_hint = (
            "\n\nCRITICAL — the seller has NOT named this item yet. "
            "Read every visible word on packaging, labels, bottles, boxes, and screens. "
            "Set detected_name and improved_name to the full real product name (brand + product line, "
            "e.g. 'Amara Body Lotion'). Include brand if visible. "
            "Never return generic names like 'New product' or 'body lotion' alone if the label shows more.\n"
        )
    elif name:
        placeholder_hint = (
            f"\n\nThe seller entered a short working title: \"{name}\". "
            "Combine this hint with packaging, labels, and visible specs to set improved_name — "
            "a polished catalog title (brand + size + product type when visible). "
            "Example: user \"32 TV\" → \"Samsung 32\\\" Full HD Smart LED TV\".\n"
        )

    description_block = (
        '  "description_sentences": [\n'
        '    "Plain sentence about what the product/service is",\n'
        '    "Plain sentence about a standout benefit, spec, or quality",\n'
        '    "Plain sentence about who it is perfect for",\n'
        '    "Plain sentence with a subtle reason to buy (4th sentence — include when possible)"\n'
        '  ],\n'
        '  "description": "Join description_sentences into one string — never include Sentence 1/2 labels",\n'
        '  "improved_name": "Marketing-ready catalog title merging seller hint + visible brand/specs",\n'
        'IMPORTANT: description_sentences MUST contain exactly 3 or 4 strings — never fewer than 3. '
        'Each string is one complete customer-ready sentence with no labels or numbering.\n'
    )

    if offering_type == "service":
        prompt = (
            "You are an expert analyst for a social media marketing platform, specialized in SERVICE businesses.\n"
            f"Service name: {name}\n"
            f"Price: {display_price}\n"
            f"{context_line}\n"
            "This photo shows EVIDENCE of work from a service business — it could be:\n"
            "- A portfolio piece (website built, design completed, event organized)\n"
            "- Before/after results of their work\n"
            "- The professional in action (consulting, training, presenting)\n"
            "- Client results, metrics, or testimonials\n\n"
            "Analyze this work evidence and return JSON with:\n"
            "{\n"
            f"{description_block}"
            '  "key_features": ["what makes this service stand out — based on the work evidence"],\n'
            '  "target_audience": "Who would hire this service provider",\n'
            '  "suggested_tags": ["tag1", "tag2", "tag3"],\n'
            '  "visual_style": "Describe what the photo shows (portfolio piece, results, etc.)",\n'
            '  "campaign_angle": "Best angle — focus on AUTHORITY, TRUST, EXPERTISE, and RESULTS rather than just selling",\n'
            '  "work_evidence_type": "portfolio|results|in_action|testimonial|other",\n'
            '  "credibility_hook": "One compelling sentence about why this work evidence proves expertise",\n'
            '  "detected_name": "Service name inferred from the image or null if unknown",\n'
            '  "detected_price": null or number if a price is visible on a tag/sign",\n'
            '  "photo_quality": {\n'
            '    "lighting": "good|dark|uneven",\n'
            '    "sharpness": "sharp|soft|blurry",\n'
            '    "has_distracting_text": false,\n'
            '    "crop": "comfortable|tight|very_tight"\n'
            '  }'
        )
    elif offering_type == "digital":
        prompt = (
            "You are an expert analyst for a social media marketing platform, specialized in DIGITAL PRODUCTS.\n"
            f"Product name: {name}\n"
            f"Price: {display_price}\n"
            f"{context_line}\n"
            "This photo shows a DIGITAL PRODUCT — it could be:\n"
            "- A screenshot of an app, template, or tool\n"
            "- A preview of a course, ebook, or digital guide\n"
            "- Results or outcomes from using the digital product\n\n"
            "Analyze this and return JSON with:\n"
            "{\n"
            f"{description_block}"
            '  "key_features": ["feature1", "feature2", "feature3"],\n'
            '  "target_audience": "Who would buy/download this",\n'
            '  "suggested_tags": ["tag1", "tag2", "tag3"],\n'
            '  "visual_style": "Describe the visual aesthetic of the screenshot/preview",\n'
            '  "campaign_angle": "Best angle — focus on the OUTCOME the buyer gets, not just features",\n'
            '  "detected_name": "Product name inferred from the image or null if unknown",\n'
            '  "detected_price": null or number if a price is visible",\n'
            '  "photo_quality": {\n'
            '    "lighting": "good|dark|uneven",\n'
            '    "sharpness": "sharp|soft|blurry",\n'
            '    "has_distracting_text": false,\n'
            '    "crop": "comfortable|tight|very_tight"\n'
            '  }'
        )
    else:  # product (default)
        prompt = (
            "You are a product photography analyst for a social media marketing platform.\n"
            f"Product name: {name}\n"
            f"Price: {display_price}\n"
            f"Number of product photos available: {num_images}\n\n"
            "Analyze this product image and return JSON with:\n"
            "{\n"
            f"{description_block}"
            '  "key_features": ["feature1", "feature2", "feature3"],\n'
            '  "target_audience": "Who would buy this",\n'
            '  "suggested_tags": ["tag1", "tag2", "tag3"],\n'
            '  "visual_style": "Describe the visual aesthetic (colors, mood, quality)",\n'
            '  "campaign_angle": "Best marketing angle for social media",\n'
            '  "detected_name": "Product name read from packaging/label or inferred from the image, null if unknown",\n'
            '  "detected_price": null or number if a price tag or label is visible,\n'
            '  "brand": "Brand name visible on packaging or null",\n'
            '  "label_text": "All readable text on the product label",\n'
            '  "photo_quality": {\n'
            '    "lighting": "good|dark|uneven",\n'
            '    "sharpness": "sharp|soft|blurry",\n'
            '    "has_distracting_text": false,\n'
            '    "crop": "comfortable|tight|very_tight"\n'
            '  }'
        )

    if num_images > 1:
        prompt += (
            ',\n  "multi_image_angles": ['
            '"Unique content angle for photo 1", "Unique content angle for photo 2", ...'
            f'] (provide {num_images} different angles, one per photo)'
        )
    prompt += "\n}"
    return prompt + placeholder_hint


def _build_seed_idea(*, offering_type, name, display_price, features_text,
                     campaign_angle, audience_text, image_note, description_text=""):
    """Build the ContentSeed idea text based on offering type."""

    if offering_type == "service":
        return (
            f"🛠️ Service Showcase: Demonstrate expertise in {name}."
            f"{f' Starting from {display_price}.' if display_price else ''}"
            f"{features_text}"
            f" Campaign angle: {campaign_angle}."
            f"{audience_text}"
            f" IMPORTANT: This is a SERVICE — content should build AUTHORITY and TRUST."
            f" Focus on expertise, results delivered, and why clients should hire/book."
            f" Use phrases like 'We deliver...', 'Our clients get...', 'See what we built...'."
            f" Avoid product-selling language like 'Buy now' or 'Order today'."
            f" Instead use 'Book a consultation', 'Get started', 'Let\\'s work together'."
            f"{image_note}"
        )
    elif offering_type == "digital":
        return (
            f"💻 Digital Product: Promote {name}."
            f"{f' Price: {display_price}.' if display_price else ''}"
            f"{features_text}"
            f" Campaign angle: {campaign_angle}."
            f"{audience_text}"
            f" IMPORTANT: This is a DIGITAL PRODUCT — focus on the TRANSFORMATION the buyer gets."
            f" Emphasize instant access, no shipping, the value/outcome."
            f" Use CTAs like 'Download now', 'Get instant access', 'Start learning today'."
            f"{image_note}"
        )
    else:  # product
        desc_note = f" Product description: {description_text[:400]}." if description_text else ""
        return (
            f"📸 Snap to Sell: Promote {name}."
            f"{f' Price: {display_price}.' if display_price else ''}"
            f"{desc_note}"
            f"{features_text}"
            f" Campaign angle: {campaign_angle}."
            f"{audience_text}"
            f"{image_note}"
        )


# ── Snap to Sell Carousel ────────────────────────────────────────────

@shared_task(name="products.create_product_carousel_posts")
def create_product_carousel_posts(product_id: str, seed_id: str, key_features: list, analysis: dict | None = None):
    """
    Create carousel posts for a product after Snap to Sell analysis.
    Fires automatically when a product has 2+ images and Instagram/Facebook/LinkedIn is connected.
    """
    from apps.agents.carousel import generate_product_carousel
    from apps.agents.models import AgentAction
    from apps.content.models import ContentSeed, Post
    from apps.platforms.models import SocialAccount
    from apps.products.commerce_autopilot import initial_commerce_post_status
    from apps.products.models import Product
    from apps.utils import fire_task

    CAROUSEL_PLATFORMS = {"instagram", "facebook", "linkedin"}

    try:
        product = Product.objects.select_related("user").get(pk=product_id)
    except Product.DoesNotExist:
        logger.error("create_product_carousel_posts: product %s not found", product_id)
        return

    user = product.user

    try:
        seed = ContentSeed.objects.get(pk=seed_id)
    except ContentSeed.DoesNotExist:
        logger.warning("create_product_carousel_posts: seed %s not found — continuing without seed link", seed_id)
        seed = None

    accounts = SocialAccount.objects.filter(
        user=user, is_active=True, platform__in=CAROUSEL_PLATFORMS,
    )
    if not accounts.exists():
        logger.info("create_product_carousel_posts: no carousel-eligible accounts for user %s", user.email)
        return

    price_label = product.display_price or ""
    base_caption = product.name
    if product.description:
        lead = product.description.split("\n\n")[0].strip()
        if lead:
            base_caption += f"\n\n{lead}"

    posts_created = 0
    initial_status = initial_commerce_post_status(user)
    for account in accounts:
        caption = base_caption
        if key_features:
            from apps.products.product_copy import format_feature_bullets

            caption += "\n\n" + format_feature_bullets(
                key_features,
                seed=str(product.pk),
                platform=account.platform,
            )
        if price_label:
            caption += f"\n\n💰 {price_label}"

        post = Post.objects.create(
            user=user,
            seed=seed,
            product=product,
            social_account=account,
            platform=account.platform,
            content_text=caption,
            content_type="original",
            status=initial_status,
            visual_strategy="carousel",
            media_status="pending",
            generated_by_agent="create",
        )

        media_urls = generate_product_carousel(
            post, product,
            key_features=key_features,
            analysis=analysis or {},
            closing_cta="Shop Now",
        )

        if media_urls:
            posts_created += 1
        else:
            post.media_status = "failed"
            post.save(update_fields=["media_status", "updated_at"])

    AgentAction.objects.create(
        user=user,
        agent_type="create",
        action_type="snap.carousel",
        description=f"Auto-carousel from Snap to Sell: {product.name} ({posts_created} post(s) created)",
        status=AgentAction.ActionStatus.COMPLETED if posts_created else AgentAction.ActionStatus.FAILED,
        input_data={"product_id": str(product.pk), "seed_id": seed_id, "features": key_features},
        output_data={"posts_created": posts_created},
        completed_at=timezone.now(),
    )

    logger.info(
        "create_product_carousel_posts: %d carousel post(s) created for product %s",
        posts_created, product_id,
    )

    if posts_created:
        fire_task(
            create_product_reel_posts,
            str(product.pk),
            str(seed_id) if seed_id else "",
            key_features,
        )


@shared_task(name="products.create_product_reel_posts")
def create_product_reel_posts(product_id: str, seed_id: str, key_features: list):
    """
    Create motion Reel variants from product images (carousel slides or single photo).

    Uses existing product/carousel images — no extra FLUX calls.
    """
    from apps.agents.models import AgentAction
    from apps.content.models import ContentSeed, Post
    from apps.content.tasks import _normalize_reel_image_source, compose_reel_video
    from apps.platforms.models import SocialAccount
    from apps.products.commerce_autopilot import initial_commerce_post_status
    from apps.products.models import Product
    from apps.products.reel_curation import curate_reel_image_urls
    from apps.utils import fire_task

    REEL_PLATFORMS = {"instagram", "facebook", "tiktok", "linkedin"}

    def _product_reel_image_sources(product):
        from apps.products.reel_curation import curate_reel_image_urls

        urls = list(product.all_image_urls)
        curated = curate_reel_image_urls(urls)
        sources = []
        for url in curated:
            normalized = _normalize_reel_image_source(url)
            if normalized:
                sources.append(normalized)
        return sources

    try:
        product = Product.objects.select_related("user").get(pk=product_id)
    except Product.DoesNotExist:
        logger.error("create_product_reel_posts: product %s not found", product_id)
        return

    user = product.user
    seed = None
    if seed_id:
        try:
            seed = ContentSeed.objects.get(pk=seed_id)
        except ContentSeed.DoesNotExist:
            pass

    carousel_posts = Post.objects.filter(
        user=user,
        product=product,
        visual_strategy="carousel",
    ).order_by("-created_at")

    use_carousel = carousel_posts.exists()
    direct_images = [] if use_carousel else _product_reel_image_sources(product)

    if use_carousel:
        pass
    elif direct_images:
        pass
    else:
        logger.info("create_product_reel_posts: no images for product %s", product_id)
        return

    accounts = SocialAccount.objects.filter(
        user=user, is_active=True, platform__in=REEL_PLATFORMS,
    )
    if not accounts.exists():
        logger.info("create_product_reel_posts: no reel-eligible accounts for user %s", user.email)
        return

    price_label = product.display_price or ""

    posts_created = 0
    initial_status = initial_commerce_post_status(user)
    for account in accounts:
        source_post = None
        if use_carousel:
            source_post = carousel_posts.filter(platform=account.platform).first() or carousel_posts.first()
            source_images = list(source_post.media_urls or [])
            if len(source_images) < 2:
                for att in source_post.attachments.filter(file_type="image").order_by("order"):
                    from apps.content.tasks import _public_url_for_file
                    url = _public_url_for_file(att.file.name)
                    if url:
                        source_images.append(url)
            source_images = curate_reel_image_urls(source_images)
            reel_template = "carousel_to_video"
            visual_strategy = "carousel"
        else:
            source_images = list(direct_images)
            reel_template = "slideshow"
            visual_strategy = "single_photo" if len(source_images) == 1 else "carousel"

        if len(source_images) < 1:
            continue

        visual_metadata = {
            "reel_template": reel_template,
            "source_images": source_images,
            "music_mood": "upbeat",
            "video_compose_status": "pending",
        }
        if source_post:
            visual_metadata["source_carousel_post_id"] = str(source_post.pk)

        caption = product.name
        if key_features:
            from apps.products.product_copy import format_feature_bullets

            caption += "\n\n" + format_feature_bullets(
                key_features,
                seed=str(product.pk),
                platform=account.platform,
            )
        if price_label:
            caption += f"\n\n💰 {price_label}"

        post = Post.objects.create(
            user=user,
            seed=seed,
            product=product,
            social_account=account,
            platform=account.platform,
            content_text=caption,
            content_type="original",
            status=initial_status,
            post_format=Post.PostFormat.REEL,
            aspect_ratio=Post.AspectRatio.STORY,
            visual_strategy=visual_strategy,
            media_status=Post.MediaStatus.GENERATED,
            media_urls=source_images,
            visual_metadata=visual_metadata,
            generated_by_agent="create",
        )
        fire_task(compose_reel_video, str(post.pk))
        posts_created += 1

    AgentAction.objects.create(
        user=user,
        agent_type="create",
        action_type="snap.reel",
        description=f"Auto-reel from Snap to Sell: {product.name} ({posts_created} post(s) created)",
        status=AgentAction.ActionStatus.COMPLETED if posts_created else AgentAction.ActionStatus.FAILED,
        input_data={"product_id": str(product.pk), "seed_id": seed_id, "features": key_features},
        output_data={"posts_created": posts_created},
        completed_at=timezone.now(),
    )

    logger.info(
        "create_product_reel_posts: %d reel post(s) created for product %s",
        posts_created, product_id,
    )


# ── Snap to Sell ─────────────────────────────────────────────────────

@shared_task(name="products.quick_post_product_photo")
def quick_post_product_photo(product_id: str):
    """
    Post the product's photo as-is to connected platforms — name, price, shop link.
    Fast path for Commerce Autopilot and the Quick Post button.
    """
    from apps.agents.adapt_agent import auto_schedule_post
    from apps.agents.models import AgentAction
    from apps.content.models import Post
    from apps.content.tasks import _normalize_reel_image_source
    from apps.platforms.models import SocialAccount
    from apps.products.commerce_autopilot import initial_commerce_post_status, should_auto_publish_commerce
    from apps.products.commerce_links import commerce_link_url
    from apps.products.models import Product

    try:
        product = Product.objects.select_related("user").get(pk=product_id)
    except Product.DoesNotExist:
        return {"error": "not_found"}

    user = product.user
    if not product.all_image_urls:
        return {"error": "no_image"}

    image_url = _normalize_reel_image_source(product.all_image_urls[0])
    from apps.products.product_cta import resolve_product_cta_url

    shop_link = resolve_product_cta_url(product)
    caption_parts = [product.name]
    if product.display_price:
        caption_parts.append(f"💰 {product.display_price}")
    if shop_link:
        caption_parts.append(f"🛒 {shop_link}")
    caption = "\n\n".join(caption_parts)

    accounts = SocialAccount.objects.filter(user=user, is_active=True)
    if not accounts.exists():
        return {"error": "no_platforms", "posts_created": 0}

    status = initial_commerce_post_status(user)
    posts_created = 0
    for account in accounts:
        post = Post.objects.create(
            user=user,
            product=product,
            social_account=account,
            platform=account.platform,
            content_text=caption,
            content_type="original",
            status=status,
            post_format=Post.PostFormat.IMAGE,
            aspect_ratio=Post.AspectRatio.SQUARE,
            visual_strategy="ai_photo",
            media_urls=[image_url],
            media_status=Post.MediaStatus.GENERATED,
            generated_by_agent="create",
        )
        posts_created += 1
        if should_auto_publish_commerce(user):
            try:
                auto_schedule_post(post)
            except Exception:
                pass

    AgentAction.objects.create(
        user=user,
        agent_type="create",
        action_type="commerce.quick_post",
        description=f"Quick photo post: {product.name} ({posts_created} platform(s))",
        status=AgentAction.ActionStatus.COMPLETED if posts_created else AgentAction.ActionStatus.FAILED,
        input_data={"product_id": str(product.pk)},
        output_data={"posts_created": posts_created},
        completed_at=timezone.now(),
    )
    logger.info("quick_post_product_photo: %d posts for product %s", posts_created, product_id)
    return {"posts_created": posts_created}


@shared_task(name="products.reidentify_product_from_photo")
def reidentify_product_from_photo(product_id: str):
    """Re-run vision AI to read the product name from packaging (no new posts)."""
    from apps.agents.llm import analyze_image, parse_llm_json
    from apps.products.commerce_autopilot import apply_ai_detected_product_fields, is_placeholder_product_name
    from apps.products.models import Product

    try:
        product = Product.objects.select_related("user").get(pk=product_id)
    except Product.DoesNotExist:
        return {"error": "not_found"}

    all_images = product.all_image_urls
    if not all_images:
        return {"error": "no_image"}

    image_url = all_images[0]
    if not image_url.startswith("http"):
        import base64
        with open(product.image.path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        ext = product.image.name.rsplit(".", 1)[-1].lower()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                "webp": "image/webp"}.get(ext, "image/jpeg")
        image_url = f"data:{mime};base64,{encoded}"

    vision_prompt = _build_vision_prompt(
        offering_type=product.offering_type,
        name=product.name,
        display_price=product.display_price or "not set",
        num_images=len(all_images),
        name_is_placeholder=True,
    )
    try:
        vision_resp = analyze_image(
            image_url=image_url,
            prompt=vision_prompt,
            system="You are a product label reader. Always respond with valid JSON only.",
            json_mode=True,
            max_tokens=600,
        )
        analysis = parse_llm_json(vision_resp.content)
    except Exception as exc:
        logger.error("reidentify_product_from_photo failed: %s", exc)
        return {"error": str(exc)}

    renamed_fields = apply_ai_detected_product_fields(product, analysis)
    if "name" in renamed_fields:
        from apps.products.commerce_links import commerce_link_path
        from django.conf import settings

        path = commerce_link_path(product, product.user.profile)
        site = getattr(settings, "SITE_URL", "").rstrip("/")
        Product.objects.filter(pk=product.pk).update(
            product_url=f"{site}{path}" if site else path,
        )
    return {"product_id": str(product.pk), "name": product.name, "renamed": "name" in renamed_fields}


@shared_task(name="products.expand_product_photo_set", soft_time_limit=180, time_limit=240)
def expand_product_photo_set(product_id: str):
    """Generate studio polish from the product's primary photo (Photoroom Plus)."""
    from apps.agents.models import AgentAction
    from apps.products.models import Product
    from apps.products.photo_variations import expand_product_photos

    try:
        product = Product.objects.select_related("user").get(pk=product_id)
    except Product.DoesNotExist:
        return {"error": "not_found"}

    result = expand_product_photos(product)
    if result.get("variations_created", 0) > 0 and result.get("mode") not in ("pro_scene", "studio_polish"):
        AgentAction.objects.create(
            user=product.user,
            agent_type="create",
            action_type="commerce.photo_variations",
            description=f"Expanded photo set: {product.name} ({result['variations_created']} scenes)",
            status=AgentAction.ActionStatus.COMPLETED,
            input_data={"product_id": str(product.pk)},
            output_data=result,
            completed_at=timezone.now(),
        )
    return result


@shared_task(name="products.fix_and_promote")
def fix_and_promote_product(product_id: str):
    """
    One-tap Commerce Autopilot recovery:
    1. Read product name from photo
    2. Quick photo post (name + price + shop link)
    3. Full AI campaign (platform copy, carousel or reel)
    """
    from apps.agents.models import AgentAction
    from apps.products.models import Product
    from apps.utils import fire_task

    try:
        product = Product.objects.select_related("user").get(pk=product_id)
    except Product.DoesNotExist:
        return {"error": "not_found"}

    user = product.user
    if not product.all_image_urls:
        return {"error": "no_image"}

    id_result = reidentify_product_from_photo(product_id)
    product.refresh_from_db()

    qp_result = quick_post_product_photo(product_id)

    fire_task(snap_to_sell_analyze, product_id, skip_quick_post=True)

    AgentAction.objects.create(
        user=user,
        agent_type="create",
        action_type="commerce.fix_and_promote",
        description=f"Fix & promote: {product.name}",
        status=AgentAction.ActionStatus.COMPLETED,
        input_data={"product_id": str(product.pk)},
        output_data={
            "renamed": id_result.get("renamed", False),
            "name": product.name,
            "quick_posts": qp_result.get("posts_created", 0),
        },
        completed_at=timezone.now(),
    )
    logger.info("fix_and_promote_product: product=%s name=%s", product_id, product.name)
    return {
        "product_id": str(product.pk),
        "name": product.name,
        "renamed": id_result.get("renamed", False),
        "quick_posts": qp_result.get("posts_created", 0),
    }


@shared_task(name="products.snap_to_sell_analyze")
def snap_to_sell_analyze(product_id: str, photo_context: str = "", skip_quick_post: bool = False):
    """
    Vision AI analyzes product photos, enriches the product description,
    then auto-creates a ContentSeed and fires the content pipeline.

    Supports multiple images — analyzes the primary image for product details,
    and tells the content pipeline about all available images so each post
    can use a different photo.

    Offering-type-aware: adapts vision prompt and content strategy for
    physical products, services, and digital products.

    Called after the user snaps/uploads photos, provides name + price,
    and hits "Launch".
    """
    from apps.agents.llm import analyze_image, generate, parse_llm_json
    from apps.agents.models import AgentAction
    from apps.content.models import ContentSeed
    from apps.content.tasks import generate_from_seed
    from apps.platforms.models import SocialAccount
    from apps.products.commerce_autopilot import (
        apply_ai_detected_product_fields,
        commerce_autopilot_active,
        is_placeholder_product_name,
    )
    from apps.products.models import Product
    from apps.utils import fire_task

    try:
        product = Product.objects.select_related("user", "category").get(pk=product_id)
    except Product.DoesNotExist:
        logger.error("Snap to Sell: product %s not found", product_id)
        return {"error": "Product not found"}

    user = product.user

    # ── Gather all product images ────────────────────────────────────
    all_images = product.all_image_urls  # primary + additional_images
    if not all_images:
        logger.warning("Snap to Sell: product %s has no images", product_id)
        return {"error": "No images attached"}

    # ── Step 1: Vision AI — analyze the primary product photo ────────
    image_url = all_images[0]
    # If it's a relative URL, we can't send it to the API — use base64
    if not image_url.startswith("http"):
        import base64
        try:
            from django.core.files.storage import default_storage
            if product.image:
                file_path = product.image.path
            else:
                # Additional image stored via default_storage
                file_path = default_storage.path(image_url.lstrip("/"))
            with open(file_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            ext = file_path.rsplit(".", 1)[-1].lower()
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                    "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/jpeg")
            image_url = f"data:{mime};base64,{encoded}"
        except Exception as exc:
            logger.warning("Snap to Sell: could not read image file: %s", exc)
            import base64
            with open(product.image.path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            ext = product.image.name.rsplit(".", 1)[-1].lower()
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                    "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/jpeg")
            image_url = f"data:{mime};base64,{encoded}"

    num_images = len(all_images)
    offering_type = product.offering_type

    # ── Build offering-type-aware vision prompt ──────────────────────
    vision_prompt = _build_vision_prompt(
        offering_type=offering_type,
        name=product.name,
        display_price=product.display_price or "not set",
        num_images=num_images,
        photo_context=photo_context,
        name_is_placeholder=is_placeholder_product_name(product.name),
    )

    try:
        system_prompts = {
            "product": "You are a product marketing expert. Always respond with valid JSON only.",
            "service": "You are a service business marketing expert. Analyze work evidence to build authority. Always respond with valid JSON only.",
            "digital": "You are a digital product marketing expert. Focus on buyer transformation. Always respond with valid JSON only.",
        }
        vision_resp = analyze_image(
            image_url=image_url,
            prompt=vision_prompt,
            system=system_prompts.get(offering_type, system_prompts["product"]),
            json_mode=True,
            max_tokens=1000,
        )
        analysis = parse_llm_json(vision_resp.content)

        # Log the vision call as an AgentAction so costs are tracked
        AgentAction.objects.create(
            user=user,
            agent_type="create",
            action_type="snap.vision",
            description=f"Snap to Sell vision analysis: {product.name} ({offering_type})",
            status=AgentAction.ActionStatus.COMPLETED,
            model_used=vision_resp.model or "gpt-4o-mini",
            input_tokens=vision_resp.input_tokens,
            output_tokens=vision_resp.output_tokens,
            tokens_used=vision_resp.total_tokens,
            duration_ms=vision_resp.duration_ms,
            input_data={"product_id": str(product.pk), "offering_type": offering_type, "num_images": num_images},
            output_data={"analysis_keys": list(analysis.keys())},
            completed_at=timezone.now(),
        )
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
    renamed_fields = apply_ai_detected_product_fields(product, analysis)
    from apps.products.product_cta import uses_marketplace_cta

    if renamed_fields and not uses_marketplace_cta(product):
        from apps.products.commerce_links import commerce_link_path
        from django.conf import settings

        path = commerce_link_path(product, product.user.profile)
        site = getattr(settings, "SITE_URL", "").rstrip("/")
        product.product_url = f"{site}{path}" if site else path
        product.save(update_fields=["product_url", "updated_at"])

    product.refresh_from_db()

    if analysis.get("suggested_tags"):
        existing_tags = set(product.tags or [])
        new_tags = list(existing_tags | set(analysis["suggested_tags"][:5]))
        product.tags = new_tags[:8]
        product.save(update_fields=["tags", "updated_at"])

    # ── Step 2b: Studio polish (Photoroom Plus + promo frame) ────────
    from apps.products.photo_variations import expand_product_photos

    variation_result = expand_product_photos(product, analysis=analysis)
    product.refresh_from_db()
    num_images = len(product.all_image_urls)

    if variation_result.get("variations_created", 0) > 0:
        if variation_result.get("mode") not in ("pro_scene", "studio_polish"):
            AgentAction.objects.create(
                user=user,
                agent_type="create",
                action_type="commerce.photo_variations",
                description=(
                    f"Expanded photo set: {product.name} "
                    f"({variation_result['variations_created']} scene versions)"
                ),
                status=AgentAction.ActionStatus.COMPLETED,
                input_data={"product_id": str(product.pk), "source": "snap_to_sell"},
                output_data=variation_result,
                completed_at=timezone.now(),
            )
    elif variation_result.get("reason") == "as_is":
        logger.info("Snap to Sell: as-is photos for product %s", product.pk)

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

    # Multi-image angles for specialized content per photo
    multi_angles = analysis.get("multi_image_angles", [])
    image_note = ""
    if num_images > 1:
        image_note = (
            f" This product has {num_images} different photos available."
            f" Create varied content — each post should use a DIFFERENT photo"
            f" from the product's image gallery for visual variety."
        )
        if multi_angles:
            angles_text = "; ".join(f"Photo {i+1}: {a}" for i, a in enumerate(multi_angles[:num_images]))
            image_note += f" Suggested angles per photo: {angles_text}."

    seed = ContentSeed.objects.create(
        user=user,
        product=product,
        idea=_build_seed_idea(
            offering_type=offering_type,
            name=product.name,
            display_price=product.display_price,
            features_text=features_text,
            campaign_angle=analysis.get("campaign_angle", "showcase"),
            audience_text=audience_text,
            image_note=image_note,
            description_text=product.description or "",
        ),
        notes=(
            f"AI Vision Analysis:\n"
            f"Offering type: {offering_type}\n"
            f"Description: {analysis.get('description', '')}\n"
            f"Visual style: {analysis.get('visual_style', '')}\n"
            f"Product images: {num_images}\n"
            f"Image URLs: {', '.join(all_images)}\n"
            f"Source: Snap to Sell — user-uploaded photos"
        ),
        target_platforms=platforms[:3] if platforms else [],
    )

    fire_task(generate_from_seed, str(seed.id))

    if commerce_autopilot_active(user) and not skip_quick_post:
        fire_task(quick_post_product_photo, str(product.pk))

    # Auto-generate carousel (2+ photos) or reel-only (single photo)
    _CAROUSEL_PLATFORMS = {"instagram", "facebook", "linkedin"}
    _REEL_PLATFORMS = {"instagram", "facebook", "tiktok", "linkedin"}
    features = analysis.get("key_features", [])
    if num_images >= 2 and any(p in _CAROUSEL_PLATFORMS for p in platforms):
        fire_task(
            create_product_carousel_posts,
            str(product.pk),
            str(seed.pk),
            features,
            analysis,
        )
    elif num_images >= 1 and any(p in _REEL_PLATFORMS for p in platforms):
        fire_task(
            create_product_reel_posts,
            str(product.pk),
            str(seed.pk),
            features,
        )

    logger.info(
        "Snap to Sell complete: product=%s, seed=%s, user=%s",
        product_id, seed.id, user.email,
    )

    if product.marketplace_partner_id:
        from apps.partners.webhooks import notify_content_generated

        posts_count = product.posts.filter(seed=seed).count()
        notify_content_generated(product, posts_created=posts_count, seed_id=str(seed.pk))

    return {
        "product_id": str(product.pk),
        "seed_id": str(seed.pk),
        "analysis": analysis,
    }


# ── Batch Snap (Market Day Mode) ─────────────────────────────────────

def _batch_item_form_prices(session, product_ids: list) -> dict[str, object]:
    """Prices captured at launch time, keyed by product id string."""
    stored = (session.stall_context or {}).get("_form_prices") or {}
    return stored


@shared_task(name="products.snap_batch_process")
def snap_batch_process(session_id: str):
    """
    Market Day Mode — process every product in a BatchSnapSession.

    1. Parse stall voice/text brief into structured context
    2. Vision-identify each item with batch-aware prompts
    3. Apply stall pricing rules + AI naming
    4. Create per-item ContentSeeds
    5. Finalize stall launch bundle (collection post + showcase reel)
    """
    from apps.agents.llm import analyze_image, parse_llm_json
    from apps.agents.models import AgentAction
    from apps.content.models import ContentSeed
    from apps.content.tasks import generate_from_seed
    from apps.platforms.models import SocialAccount
    from apps.products.batch_snap_intelligence import (
        build_batch_identification_prompt,
        build_batch_seed_idea,
        build_batch_vision_system_prompt,
        is_batch_placeholder_name,
        parse_stall_brief,
        resolve_batch_item_price,
    )
    from apps.products.commerce_seo import ensure_commerce_seo_copy
    from apps.products.models import BatchSnapSession, Product
    from apps.utils import fire_task

    try:
        session = BatchSnapSession.objects.select_related("user", "user__profile").get(pk=session_id)
    except BatchSnapSession.DoesNotExist:
        logger.error("Batch Snap: session %s not found", session_id)
        return {"error": "session_not_found"}

    user = session.user
    products = list(
        Product.objects.filter(batch_snap_session=session, user=user).order_by("batch_index", "created_at")
    )
    if not products:
        session.status = BatchSnapSession.Status.FAILED
        session.error_message = "No products linked to this batch session."
        session.save(update_fields=["status", "error_message"])
        return {"error": "no_products"}

    product_ids = [str(p.pk) for p in products]
    form_prices = _batch_item_form_prices(session, product_ids)

    if not session.stall_context:
        session.stall_context = parse_stall_brief(
            transcript=session.voice_transcript,
            stall_title=session.stall_title,
            default_price=session.default_price,
            default_currency=session.default_currency,
            offering_type=session.offering_type,
            item_count=len(products),
            stall_notes=session.stall_notes,
        )
        session.stall_context["_form_prices"] = form_prices
        session.save(update_fields=["stall_context"])

    stall_context = session.stall_context or {}
    offering_type = session.offering_type
    sibling_names: list[str] = []
    results = []

    for product in products:
        pid = str(product.pk)
        if not product.all_image_urls:
            results.append({"product_id": pid, "error": "No image"})
            continue

        image_url = product.all_image_urls[0]
        if not image_url.startswith("http"):
            import base64

            try:
                from django.core.files.storage import default_storage

                if product.image:
                    file_path = product.image.path
                else:
                    file_path = default_storage.path(image_url.lstrip("/"))
                with open(file_path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
                ext = file_path.rsplit(".", 1)[-1].lower()
                mime = {
                    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                    "webp": "image/webp", "gif": "image/gif",
                }.get(ext, "image/jpeg")
                image_url = f"data:{mime};base64,{encoded}"
            except Exception as exc:
                logger.error("Batch Snap: could not read image for %s: %s", pid, exc)
                results.append({"product_id": pid, "error": str(exc)})
                continue

        needs_name = is_batch_placeholder_name(product.name)
        batch_index = product.batch_index if product.batch_index is not None else 0
        photo_context = (stall_context.get("item_contexts") or {}).get(pid, "")

        identification_prompt = build_batch_identification_prompt(
            offering_type=offering_type,
            name=product.name,
            display_price=product.display_price or "not set",
            photo_context=photo_context,
            stall_context=stall_context,
            batch_index=batch_index,
            batch_total=len(products),
            sibling_names=sibling_names,
            needs_name=needs_name,
        )

        try:
            vision_resp = analyze_image(
                image_url=image_url,
                prompt=identification_prompt,
                system=build_batch_vision_system_prompt(
                    offering_type=offering_type,
                    stall_context=stall_context,
                ),
                json_mode=True,
                max_tokens=900,
            )
            analysis = parse_llm_json(vision_resp.content)

            AgentAction.objects.create(
                user=user,
                agent_type="create",
                action_type="snap.vision_batch",
                description=f"Batch Snap vision: {product.name} ({offering_type})",
                status=AgentAction.ActionStatus.COMPLETED,
                model_used=vision_resp.model or "gpt-4o-mini",
                input_tokens=vision_resp.input_tokens,
                output_tokens=vision_resp.output_tokens,
                tokens_used=vision_resp.total_tokens,
                duration_ms=vision_resp.duration_ms,
                input_data={
                    "product_id": pid,
                    "session_id": str(session.pk),
                    "offering_type": offering_type,
                    "batch_index": batch_index,
                },
                output_data={"analysis_keys": list(analysis.keys())},
                completed_at=timezone.now(),
            )
        except Exception as exc:
            logger.error("Batch Snap vision failed for %s: %s", pid, exc)
            fallback_desc = {
                "product": "Fresh from today's stall — quality you can trust.",
                "service": "Professional service — see our work!",
                "digital": "Premium digital product — instant access.",
            }
            analysis = {
                "product_name": product.name,
                "description": fallback_desc.get(offering_type, fallback_desc["product"]),
                "key_features": [],
                "target_audience": stall_context.get("category_hint") or "Local buyers",
                "suggested_tags": [],
                "visual_style": "Market stall photo",
                "campaign_angle": stall_context.get("collection_angle") or "showcase",
                "product_category": stall_context.get("category_hint") or "",
            }

        if needs_name:
            ai_name = (
                analysis.get("improved_name")
                or analysis.get("product_name")
                or analysis.get("detected_name")
            )
            if ai_name:
                from apps.products.commerce_autopilot import sanitize_product_name

                ai_name = sanitize_product_name(str(ai_name))[:200]
                if ai_name:
                    base_name = ai_name
                    suffix = 0
                    while Product.objects.filter(user=user, name=ai_name).exclude(pk=product.pk).exists():
                        suffix += 1
                        ai_name = f"{base_name} ({suffix})"
                    product.name = ai_name

        form_price = form_prices.get(pid)
        resolved_price, price_source = resolve_batch_item_price(
            product=product,
            analysis=analysis,
            stall_context=stall_context,
            form_price=form_price,
        )
        if resolved_price is not None:
            product.price = resolved_price
            if stall_context.get("pricing_rules", {}).get("default_currency"):
                product.currency = stall_context["pricing_rules"]["default_currency"]

        if not product.description and analysis.get("description"):
            product.description = analysis["description"]

        ensure_commerce_seo_copy(product, user.profile, analysis)

        if analysis.get("suggested_tags"):
            existing_tags = set(product.tags or [])
            new_tags = list(existing_tags | set(analysis["suggested_tags"][:5]))
            product.tags = new_tags[:8]

        product.save(update_fields=["name", "description", "price", "currency", "tags", "updated_at"])
        sibling_names.append(product.name)

        platforms = list(
            SocialAccount.objects.filter(user=user, is_active=True).values_list("platform", flat=True)
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
            idea=build_batch_seed_idea(
                offering_type=offering_type,
                product=product,
                analysis=analysis,
                stall_context=stall_context,
                features_text=features_text,
                audience_text=audience_text,
                image_note=" Use the uploaded stall photo as the hero image.",
            ),
            notes=(
                f"AI Vision Analysis (Batch Snap — Market Day):\n"
                f"Session: {session.stall_title or session.pk}\n"
                f"Offering type: {offering_type}\n"
                f"Identified as: {product.name}\n"
                f"Price source: {price_source}\n"
                f"Description: {analysis.get('description', '')}\n"
                f"Market context: {stall_context.get('market_context', '')}\n"
                f"Campaign tone: {stall_context.get('campaign_tone', '')}"
            ),
            target_platforms=platforms[:3] if platforms else [],
        )

        fire_task(generate_from_seed, str(seed.id))

        session.items_processed = (session.items_processed or 0) + 1
        session.save(update_fields=["items_processed"])

        results.append({
            "product_id": pid,
            "product_name": product.name,
            "seed_id": str(seed.pk),
            "ai_named": needs_name,
            "price_source": price_source,
        })

    logger.info(
        "Batch Snap items complete: session=%s processed=%d/%d",
        session_id, len(results), len(products),
    )

    if session.launch_bundle:
        fire_task(finalize_batch_snap_session, str(session.pk))
    else:
        session.status = BatchSnapSession.Status.COMPLETED
        session.finalized_at = timezone.now()
        session.save(update_fields=["status", "finalized_at"])

    return {"processed": len(results), "results": results, "session_id": str(session.pk)}


@shared_task(name="products.finalize_batch_snap_session")
def finalize_batch_snap_session(session_id: str):
    """Stall launch bundle: collection seed, showcase reel, seller WhatsApp ping."""
    from apps.agents.models import AgentAction
    from apps.content.models import ContentSeed, Post
    from apps.content.tasks import compose_reel_video, generate_from_seed, _normalize_reel_image_source
    from apps.platforms.models import SocialAccount
    from apps.products.batch_snap_intelligence import build_stall_launch_campaign
    from apps.products.commerce_autopilot import initial_commerce_post_status
    from apps.products.commerce_links import resolve_page_slug
    from apps.products.models import BatchSnapSession, Product
    from apps.utils import fire_task

    try:
        session = BatchSnapSession.objects.select_related("user", "user__profile").get(pk=session_id)
    except BatchSnapSession.DoesNotExist:
        return {"error": "session_not_found"}

    session.status = BatchSnapSession.Status.FINALIZING
    session.save(update_fields=["status"])

    user = session.user
    profile = user.profile
    products = list(
        Product.objects.filter(batch_snap_session=session, user=user, is_active=True)
        .order_by("batch_index", "created_at")
    )

    from django.conf import settings

    page_slug = resolve_page_slug(profile)
    site = getattr(settings, "SITE_URL", "").rstrip("/")
    shop_url = f"{site}/shop/{page_slug}/" if site else f"/shop/{page_slug}/"
    session.shop_url = shop_url

    stall_context = session.stall_context or {}
    campaign = build_stall_launch_campaign(
        stall_context=stall_context,
        products=products,
        profile=profile,
        shop_url=shop_url,
    )
    session.whatsapp_message = campaign.get("whatsapp_message", "")

    platforms = list(
        SocialAccount.objects.filter(user=user, is_active=True).values_list("platform", flat=True)
    )

    collection_seed = ContentSeed.objects.create(
        user=user,
        idea=campaign.get("collection_idea", ""),
        notes=(
            f"Batch Snap stall launch — {session.stall_title or 'Market Day'}\n"
            f"Products: {', '.join(p.name for p in products[:15])}\n"
            f"Shop: {shop_url}\n"
            f"WhatsApp hook: {campaign.get('whatsapp_message', '')}"
        ),
        target_platforms=platforms[:4] if platforms else [],
    )
    session.bundle_seed = collection_seed
    fire_task(generate_from_seed, str(collection_seed.pk))

    REEL_PLATFORMS = {"instagram", "facebook", "tiktok", "linkedin"}
    reel_accounts = SocialAccount.objects.filter(
        user=user, is_active=True, platform__in=REEL_PLATFORMS,
    )

    image_sources = []
    for product in products[:10]:
        if product.image:
            normalized = _normalize_reel_image_source(product.image.url)
            if normalized:
                image_sources.append(normalized)

    bundle_post_ids = []
    initial_status = initial_commerce_post_status(user)
    reel_caption = campaign.get("reel_caption") or f"Shop today: {shop_url}"

    if len(image_sources) >= 2 and reel_accounts.exists():
        for account in reel_accounts:
            post = Post.objects.create(
                user=user,
                platform=account.platform,
                content_text=reel_caption[:2200],
                status=initial_status,
                visual_strategy="carousel",
                visual_metadata={
                    "reel_template": "slideshow",
                    "source_images": image_sources,
                    "music_mood": "upbeat",
                    "video_compose_status": "pending",
                    "batch_snap_session_id": str(session.pk),
                    "reel_hook_text": campaign.get("reel_hook_text", ""),
                },
            )
            bundle_post_ids.append(str(post.pk))
            fire_task(compose_reel_video, str(post.pk))

    session.bundle_post_ids = bundle_post_ids

    AgentAction.objects.create(
        user=user,
        agent_type="create",
        action_type="snap.stall_launch",
        description=(
            f"Stall launch bundle: {len(products)} items, "
            f"{len(bundle_post_ids)} showcase reel(s)"
        ),
        status=AgentAction.ActionStatus.COMPLETED,
        input_data={"session_id": str(session.pk), "product_count": len(products)},
        output_data={
            "shop_url": shop_url,
            "collection_seed_id": str(collection_seed.pk),
            "reel_post_ids": bundle_post_ids,
        },
        completed_at=timezone.now(),
    )

    sent = _send_batch_snap_seller_whatsapp(user, session.whatsapp_message, shop_url)
    session.whatsapp_sent = sent
    session.status = BatchSnapSession.Status.COMPLETED
    session.finalized_at = timezone.now()
    session.save(update_fields=[
        "shop_url", "whatsapp_message", "bundle_seed", "bundle_post_ids",
        "whatsapp_sent", "status", "finalized_at",
    ])

    logger.info("Batch Snap finalized: session=%s shop=%s", session_id, shop_url)
    return {
        "session_id": str(session.pk),
        "shop_url": shop_url,
        "collection_seed_id": str(collection_seed.pk),
        "reel_posts": bundle_post_ids,
        "whatsapp_sent": sent,
    }


def _send_batch_snap_seller_whatsapp(user, message: str, shop_url: str) -> bool:
    """Notify seller their stall is live — template if configured, else skip gracefully."""
    from django.conf import settings

    if not message:
        message = f"Your stall is live! Share: {shop_url}"

    template_name = getattr(settings, "KOVA_BATCH_SNAP_TEMPLATE_NAME", "") or ""
    phone_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "") or ""
    token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "") or ""

    from apps.accounts.phone_utils import phone_to_whatsapp_digits

    to_number = phone_to_whatsapp_digits(getattr(user, "phone_number", "") or "")
    if not (to_number and phone_id and token):
        logger.debug("Batch Snap WhatsApp: missing phone or creds — skipping")
        return False

    from apps.platforms.providers.whatsapp import WhatsAppProvider

    provider = WhatsAppProvider()
    first_name = (user.full_name or user.email or "there").split(" ")[0]

    if template_name:
        components = [{
            "type": "body",
            "parameters": [
                {"type": "text", "text": first_name[:40]},
                {"type": "text", "text": shop_url[:200]},
            ],
        }]
        result = provider.send_template_message(
            access_token=token,
            to=to_number,
            template_name=template_name,
            language_code=getattr(settings, "KOVA_BATCH_SNAP_TEMPLATE_LANG", "en"),
            components=components,
            phone_number_id=phone_id,
        )
        if result.get("success"):
            return True
        logger.warning("Batch Snap template send failed: %s", result.get("error"))

    return False


# ══════════════════════════════════════════════════════════════════════════════
# RECEIPT TO RESTOCK — Snap a receipt → AI extracts items → auto-restock + content
# ══════════════════════════════════════════════════════════════════════════════


@shared_task(name="products.process_restock_scan")
def process_restock_scan(scan_id: str):
    """
    Process a receipt/invoice photo into stock updates + restock content.

    Pipeline: Receipt photo → Vision AI extraction (items, quantities, prices) →
    fuzzy-match to existing products → update stock levels → create StockUpdates →
    generate 'back in stock' ContentSeed.
    """
    from django.utils import timezone
    from apps.products.models import RestockScan, Product, StockUpdate, StockAlert
    from apps.content.models import ContentSeed
    from apps.agents.models import AgentAction

    try:
        scan = RestockScan.objects.select_related("user", "user__profile").get(pk=scan_id)
    except RestockScan.DoesNotExist:
        logger.error("RestockScan %s not found", scan_id)
        return {"error": "not_found"}

    user = scan.user

    try:
        # ── Step 1: Vision Analysis ──
        scan.status = RestockScan.Status.ANALYZING
        scan.save(update_fields=["status"])

        from apps.agents.llm import analyze_image, parse_llm_json

        vision_prompt = (
            "Analyze this receipt/invoice/delivery note photo. Extract all items listed.\n\n"
            "Return a JSON object:\n"
            "- items: array of objects, each with:\n"
            "  - name: product name as written on receipt\n"
            "  - quantity: number of units (integer)\n"
            "  - unit_price: price per unit (number, or null if not visible)\n"
            "- supplier_name: business/supplier name on the receipt (or null)\n"
            "- receipt_date: date on receipt in YYYY-MM-DD format (or null)\n"
            "- receipt_total: total amount (number, or null)\n"
            "- currency: currency code (KES, USD, etc.) default KES\n"
            "Return ONLY valid JSON. If you can't read something, set it to null."
        )

        image_url = _vision_image_url(scan.image)
        vision_resp = analyze_image(
            image_url=image_url,
            prompt=vision_prompt,
            system="You are a receipt OCR expert. Always respond with valid JSON only.",
            json_mode=True,
            max_tokens=1200,
        )
        extraction = parse_llm_json(vision_resp.content)

        raw_items = extraction.get("items", [])
        scan.supplier_name = (extraction.get("supplier_name") or "")[:200]
        scan.receipt_currency = extraction.get("currency", "KES")[:5]
        scan.receipt_total = extraction.get("receipt_total")

        if extraction.get("receipt_date"):
            try:
                from datetime import date
                scan.receipt_date = date.fromisoformat(extraction["receipt_date"])
            except (ValueError, TypeError):
                pass

        scan.save(update_fields=["supplier_name", "receipt_currency", "receipt_total", "receipt_date"])

        # ── Step 2: Match to existing products ──
        scan.status = RestockScan.Status.MATCHING
        scan.save(update_fields=["status"])

        user_products = list(Product.objects.filter(user=user, is_active=True).values("pk", "name"))
        extracted_items = []
        matched_products = []
        not_matched = []

        for item in raw_items:
            item_name = item.get("name", "").strip()
            if not item_name:
                continue

            quantity = item.get("quantity", 0)
            unit_price = item.get("unit_price")

            # Fuzzy match: check if product name is contained or similar
            best_match = None
            best_confidence = 0

            item_lower = item_name.lower()
            for prod in user_products:
                prod_lower = prod["name"].lower()
                # Exact substring match
                if item_lower in prod_lower or prod_lower in item_lower:
                    best_match = prod
                    best_confidence = 0.95
                    break
                # Word overlap scoring
                item_words = set(item_lower.split())
                prod_words = set(prod_lower.split())
                if item_words and prod_words:
                    overlap = len(item_words & prod_words) / max(len(item_words), len(prod_words))
                    if overlap > best_confidence and overlap >= 0.5:
                        best_match = prod
                        best_confidence = round(overlap, 2)

            entry = {
                "name": item_name,
                "quantity": quantity,
                "unit_price": float(unit_price) if unit_price else None,
                "matched_product_id": str(best_match["pk"]) if best_match else None,
                "match_confidence": best_confidence,
            }
            extracted_items.append(entry)

            if best_match:
                matched_products.append((best_match["pk"], quantity, item_name))
            else:
                not_matched.append(item_name)

        scan.extracted_items = extracted_items
        scan.products_matched = len(matched_products)
        scan.items_not_matched = not_matched
        scan.save(update_fields=["extracted_items", "products_matched", "items_not_matched"])

        # ── Step 3: Update stock ──
        scan.status = RestockScan.Status.UPDATING
        scan.save(update_fields=["status"])

        restocked_names = []
        for product_pk, quantity, item_name in matched_products:
            try:
                product = Product.objects.get(pk=product_pk)
                old_quantity = product.quantity or 0
                new_quantity = old_quantity + quantity
                old_status = product.stock_status

                product.quantity = new_quantity
                if product.tracks_stock and new_quantity > product.low_stock_threshold:
                    product.stock_status = Product.StockStatus.IN_STOCK
                product.save(update_fields=["quantity", "stock_status"])

                from apps.products.stock_actions import log_stock_change

                log_stock_change(
                    product,
                    previous_status=old_status,
                    previous_quantity=old_quantity,
                    reason=StockUpdate.Reason.RESTOCK,
                    notes=f"[Receipt to Restock] +{quantity} from {scan.supplier_name or 'receipt scan'}",
                )

                restocked_names.append(product.name)
            except Product.DoesNotExist:
                continue

        scan.products_updated = len(restocked_names)

        # ── Step 4: Generate 'back in stock' content ──
        if restocked_names:
            names_text = ", ".join(restocked_names[:5])
            if len(restocked_names) > 5:
                names_text += f" and {len(restocked_names) - 5} more"

            seed = ContentSeed.objects.create(
                user=user,
                idea=(
                    f"🔥 RESTOCKED: {names_text}!\n\n"
                    f"These products are back in stock and ready to ship. "
                    f"Create exciting 'back in stock' announcement posts. "
                    f"Build urgency — they sold out before, they'll sell out again."
                ),
                notes=f"[Receipt to Restock] {len(restocked_names)} products restocked via receipt scan",
            )
            scan.content_seed = seed

            from apps.content.tasks import generate_from_seed
            generate_from_seed.delay(str(seed.pk))

        # ── Complete ──
        scan.status = RestockScan.Status.COMPLETED
        scan.completed_at = timezone.now()
        scan.save()

        AgentAction.objects.create(
            user=user,
            agent_type="analyst",
            action_type="receipt_to_restock",
            description=f"Receipt to Restock: {len(extracted_items)} items, {scan.products_updated} updated",
            status=AgentAction.ActionStatus.COMPLETED,
            input_data={"scan_id": str(scan.pk), "items_found": len(extracted_items)},
            output_data={
                "matched": scan.products_matched,
                "updated": scan.products_updated,
                "not_matched": not_matched,
                "restocked": restocked_names,
            },
            tokens_used=vision_resp.total_tokens,
            input_tokens=vision_resp.input_tokens,
            output_tokens=vision_resp.output_tokens,
            model_used=vision_resp.model or "",
            duration_ms=vision_resp.duration_ms,
            completed_at=timezone.now(),
        )

        logger.info(
            "Restock scan %s complete: %d items found, %d matched, %d updated",
            scan_id, len(extracted_items), scan.products_matched, scan.products_updated,
        )
        return {
            "status": "completed",
            "items_found": len(extracted_items),
            "products_updated": scan.products_updated,
        }

    except Exception as e:
        logger.exception("Restock scan %s failed: %s", scan_id, e)
        scan.status = RestockScan.Status.FAILED
        scan.error_message = str(e)[:1000]
        scan.save(update_fields=["status", "error_message"])
        return {"error": str(e)}
