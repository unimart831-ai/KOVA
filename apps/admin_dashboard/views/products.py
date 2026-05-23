from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.db.models.functions import Length, TruncDate
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.admin_dashboard.decorators import staff_required
from apps.agents.models import AgentAction
from apps.analytics.models import ShopifyStore
from apps.content.models import ContentSeed, Post
from apps.partners.models import MarketplacePartner, MarketplaceSellerAccount
from apps.products.commerce_links import commerce_link_url, resolve_page_slug
from apps.products.commerce_seo import MIN_SEO_DESCRIPTION_LEN, commerce_seo_checklist
from apps.products.models import CommercePayment, Product, ProductCategory, StockAlert, StockUpdate

COMMERCE_TEMPLATE = "admin_dashboard/commerce/{name}.html"


def _commerce_context(extra=None):
    ctx = {"commerce_section": extra.get("commerce_section") if extra else None}
    if extra:
        ctx.update(extra)
    return ctx


@staff_required
def commerce_overview(request):
    """Platform-wide Kova Commerce health — catalog, shops, payments, integrations."""
    now = timezone.now()
    week_ago = now - timedelta(days=7)

    active_qs = Product.objects.filter(is_active=True)
    total_products = active_qs.count()
    total_users_with_products = active_qs.values("user").distinct().count()

    stock_breakdown = dict(
        active_qs.values_list("stock_status")
        .annotate(c=Count("id"))
        .values_list("stock_status", "c")
    )
    in_stock = stock_breakdown.get("in_stock", 0)
    low_stock = stock_breakdown.get("low_stock", 0)
    out_of_stock = stock_breakdown.get("out_of_stock", 0)
    made_to_order = stock_breakdown.get("made_to_order", 0)
    unlimited = stock_breakdown.get("unlimited", 0)
    featured = active_qs.filter(is_featured=True).count()

    unread_alerts = StockAlert.objects.filter(is_read=False).count()
    recent_alerts = (
        StockAlert.objects
        .select_related("user", "product")
        .filter(created_at__gte=week_ago)
        .order_by("-created_at")[:20]
    )

    updates_7d = (
        StockUpdate.objects
        .filter(created_at__gte=week_ago)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )

    top_users = list(
        active_qs.values("user__email", "user__full_name", "user__id")
        .annotate(
            product_count=Count("id"),
            low=Count("id", filter=Q(stock_status="low_stock")),
            oos=Count("id", filter=Q(stock_status="out_of_stock")),
        )
        .order_by("-product_count")[:20]
    )

    total_categories = ProductCategory.objects.filter(is_active=True).count()
    recent_products = (
        active_qs.select_related("user", "category", "marketplace_partner")
        .order_by("-created_at")[:15]
    )

    catalog_sample_seeds = ContentSeed.objects.filter(notes__startswith="Catalog sample:").count()
    catalog_sample_7d = ContentSeed.objects.filter(
        notes__startswith="Catalog sample:", created_at__gte=week_ago,
    ).count()
    legacy_auto_promo = ContentSeed.objects.filter(notes__startswith="Auto-promoted:").count()
    strategist_product_seeds = ContentSeed.objects.filter(
        product__isnull=False, notes__startswith="[Strategist Agent]",
    ).count()

    products_with_posts = Post.objects.filter(product=OuterRef("pk"))
    never_promoted = active_qs.exclude(Exists(products_with_posts)).count()

    snap_carousel = AgentAction.objects.filter(action_type="snap.carousel").count()
    snap_reel = AgentAction.objects.filter(action_type="snap.reel").count()
    snap_carousel_7d = AgentAction.objects.filter(
        action_type="snap.carousel", created_at__gte=week_ago,
    ).count()
    snap_reel_7d = AgentAction.objects.filter(
        action_type="snap.reel", created_at__gte=week_ago,
    ).count()
    reel_posts = Post.objects.filter(post_format="reel").count()
    reel_posts_7d = Post.objects.filter(post_format="reel", created_at__gte=week_ago).count()

    offering_breakdown = dict(
        active_qs.values_list("offering_type")
        .annotate(c=Count("id"))
        .values_list("offering_type", "c")
    )
    products_count = offering_breakdown.get("product", 0)
    services_count = offering_breakdown.get("service", 0)
    digital_count = offering_breakdown.get("digital", 0)

    snap_actions = AgentAction.objects.filter(action_type__startswith="snap.")
    snap_total = snap_actions.count()
    snap_7d = snap_actions.filter(created_at__gte=week_ago).count()
    snap_single = AgentAction.objects.filter(action_type="snap.vision").count()
    snap_batch = AgentAction.objects.filter(action_type="snap.vision_batch").count()
    multi_image_products = active_qs.exclude(additional_images=[]).count()

    # ── Commerce-specific stats ───────────────────────────────────────
    with_commerce_slug = active_qs.exclude(commerce_slug="").count()
    marketplace_products = active_qs.filter(source=Product.Source.MARKETPLACE).count()
    shopify_products = active_qs.filter(marketplace_metadata__shopify=True).count()
    manual_products = active_qs.filter(source=Product.Source.MANUAL).count()
    snap_products = active_qs.filter(source=Product.Source.SNAP).count()

    seo_ready = (
        active_qs.filter(commerce_slug__gt="")
        .annotate(desc_len=Length("description"))
        .filter(desc_len__gte=MIN_SEO_DESCRIPTION_LEN)
        .filter(Q(image__gt="") | ~Q(additional_images=[]))
        .count()
    )

    public_shops = (
        UserProfile.objects.annotate(
            active_products=Count(
                "user__products",
                filter=Q(user__products__is_active=True),
            ),
        )
        .filter(active_products__gt=0, page_slug__gt="")
        .count()
    )
    autopilot_sellers = UserProfile.objects.filter(commerce_autopilot=True).count()

    payment_stats = CommercePayment.objects.aggregate(
        total=Count("id"),
        completed=Count("id", filter=Q(status=CommercePayment.Status.COMPLETED)),
        pending=Count("id", filter=Q(status=CommercePayment.Status.PENDING)),
        revenue=Sum("amount", filter=Q(status=CommercePayment.Status.COMPLETED)),
    )
    payments_7d = CommercePayment.objects.filter(created_at__gte=week_ago).count()

    shopify_stores = ShopifyStore.objects.filter(is_active=True).count()
    shopify_products_synced = ShopifyStore.objects.aggregate(t=Sum("products_synced"))["t"] or 0
    active_marketplaces = MarketplacePartner.objects.filter(is_active=True).count()
    marketplace_sellers = MarketplaceSellerAccount.objects.filter(status="active").count()

    site_url = getattr(settings, "SITE_URL", "").rstrip("/")

    return render(request, COMMERCE_TEMPLATE.format(name="overview"), _commerce_context({
        "page_title": "Commerce",
        "commerce_section": "overview",
        "site_url": site_url,
        "total_products": total_products,
        "total_users_with_products": total_users_with_products,
        "in_stock": in_stock,
        "low_stock": low_stock,
        "out_of_stock": out_of_stock,
        "made_to_order": made_to_order,
        "unlimited": unlimited,
        "featured": featured,
        "total_categories": total_categories,
        "unread_alerts": unread_alerts,
        "recent_alerts": recent_alerts,
        "updates_7d": list(updates_7d),
        "top_users": top_users,
        "recent_products": recent_products,
        "catalog_sample_seeds": catalog_sample_seeds,
        "catalog_sample_7d": catalog_sample_7d,
        "legacy_auto_promo": legacy_auto_promo,
        "strategist_product_seeds": strategist_product_seeds,
        "never_promoted": never_promoted,
        "products_count": products_count,
        "services_count": services_count,
        "digital_count": digital_count,
        "snap_total": snap_total,
        "snap_7d": snap_7d,
        "snap_single": snap_single,
        "snap_batch": snap_batch,
        "multi_image_products": multi_image_products,
        "snap_carousel": snap_carousel,
        "snap_reel": snap_reel,
        "snap_carousel_7d": snap_carousel_7d,
        "snap_reel_7d": snap_reel_7d,
        "reel_posts": reel_posts,
        "reel_posts_7d": reel_posts_7d,
        "with_commerce_slug": with_commerce_slug,
        "marketplace_products": marketplace_products,
        "shopify_products": shopify_products,
        "manual_products": manual_products,
        "snap_products": snap_products,
        "seo_ready": seo_ready,
        "public_shops": public_shops,
        "autopilot_sellers": autopilot_sellers,
        "payment_total": payment_stats["total"] or 0,
        "payment_completed": payment_stats["completed"] or 0,
        "payment_pending": payment_stats["pending"] or 0,
        "payment_revenue": payment_stats["revenue"] or Decimal("0"),
        "payments_7d": payments_7d,
        "shopify_stores": shopify_stores,
        "shopify_products_synced": shopify_products_synced,
        "active_marketplaces": active_marketplaces,
        "marketplace_sellers": marketplace_sellers,
    }))


@staff_required
def commerce_catalog(request):
    """Browse all catalog items — filterable by stock, source, and commerce readiness."""
    qs = (
        Product.objects
        .select_related("user", "category", "marketplace_partner")
        .filter(is_active=True)
        .order_by("-created_at")
    )

    status = request.GET.get("status")
    if status in ("in_stock", "low_stock", "out_of_stock", "made_to_order", "unlimited"):
        qs = qs.filter(stock_status=status)

    source = request.GET.get("source")
    if source in dict(Product.Source.choices):
        qs = qs.filter(source=source)
    elif source == "shopify":
        qs = qs.filter(marketplace_metadata__shopify=True)

    user_email = request.GET.get("email")
    if user_email:
        qs = qs.filter(user__email__icontains=user_email)

    q = request.GET.get("q")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q) | Q(commerce_slug__icontains=q))

    featured_only = request.GET.get("featured")
    if featured_only == "1":
        qs = qs.filter(is_featured=True)

    commerce_ready = request.GET.get("commerce")
    if commerce_ready == "1":
        qs = qs.exclude(commerce_slug="")
    elif commerce_ready == "0":
        qs = qs.filter(commerce_slug="")

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page", 1))

    return render(request, COMMERCE_TEMPLATE.format(name="catalog"), _commerce_context({
        "page_title": "Catalog",
        "commerce_section": "catalog",
        "page_obj": page,
        "source_choices": Product.Source.choices,
        "current_status": status,
        "current_source": source,
        "current_email": user_email or "",
        "current_q": q or "",
        "current_featured": featured_only,
        "current_commerce": commerce_ready,
    }))


@staff_required
def commerce_product_detail(request, pk):
    """Read-only commerce view for a single product."""
    product = get_object_or_404(
        Product.objects.select_related("user", "user__profile", "category", "marketplace_partner"),
        pk=pk,
    )
    profile = product.user.profile
    seo = commerce_seo_checklist(product, profile)
    posts_count = Post.objects.filter(product=product).count()
    published_posts = Post.objects.filter(product=product, status=Post.Status.PUBLISHED).count()
    payments = product.commerce_payments.order_by("-created_at")[:10]
    payment_total = product.commerce_payments.filter(
        status=CommercePayment.Status.COMPLETED,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    return render(request, COMMERCE_TEMPLATE.format(name="product_detail"), _commerce_context({
        "page_title": product.name,
        "commerce_section": "catalog",
        "product": product,
        "profile": profile,
        "seo": seo,
        "commerce_url": commerce_link_url(product) if product.commerce_slug else "",
        "shop_url": f"{getattr(settings, 'SITE_URL', '').rstrip('/')}/shop/{resolve_page_slug(profile)}/",
        "posts_count": posts_count,
        "published_posts": published_posts,
        "payments": payments,
        "payment_total": payment_total,
    }))


@staff_required
def commerce_shops(request):
    """Public Kova shop pages — sellers with live catalogs."""
    qs = (
        UserProfile.objects
        .select_related("user")
        .annotate(
            active_products=Count(
                "user__products",
                filter=Q(user__products__is_active=True),
            ),
            commerce_links=Count(
                "user__products",
                filter=Q(user__products__is_active=True, user__products__commerce_slug__gt=""),
            ),
        )
        .filter(active_products__gt=0)
        .order_by("-active_products")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(user__email__icontains=q)
            | Q(user__full_name__icontains=q)
            | Q(page_slug__icontains=q)
            | Q(company_name__icontains=q)
        )

    autopilot = request.GET.get("autopilot")
    if autopilot == "1":
        qs = qs.filter(commerce_autopilot=True)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page", 1))
    site_url = getattr(settings, "SITE_URL", "").rstrip("/")

    return render(request, COMMERCE_TEMPLATE.format(name="shops"), _commerce_context({
        "page_title": "Public Shops",
        "commerce_section": "shops",
        "page_obj": page,
        "site_url": site_url,
        "current_q": q,
        "current_autopilot": autopilot,
    }))


@staff_required
def commerce_payments(request):
    """M-Pesa commerce payments across all sellers."""
    qs = (
        CommercePayment.objects
        .select_related("user", "product")
        .order_by("-created_at")
    )

    status = request.GET.get("status")
    if status in dict(CommercePayment.Status.choices):
        qs = qs.filter(status=status)

    source = request.GET.get("source")
    if source in dict(CommercePayment.Source.choices):
        qs = qs.filter(source=source)

    email = request.GET.get("email", "").strip()
    if email:
        qs = qs.filter(user__email__icontains=email)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page", 1))

    totals = CommercePayment.objects.aggregate(
        completed=Sum("amount", filter=Q(status=CommercePayment.Status.COMPLETED)),
        pending_count=Count("id", filter=Q(status=CommercePayment.Status.PENDING)),
    )

    return render(request, COMMERCE_TEMPLATE.format(name="payments"), _commerce_context({
        "page_title": "Commerce Payments",
        "commerce_section": "payments",
        "page_obj": page,
        "status_choices": CommercePayment.Status.choices,
        "source_choices": CommercePayment.Source.choices,
        "current_status": status,
        "current_source": source,
        "current_email": email,
        "total_revenue": totals["completed"] or Decimal("0"),
        "pending_count": totals["pending_count"] or 0,
    }))


@staff_required
def commerce_integrations(request):
    """Shopify stores and marketplace partners in one place."""
    shopify_stores = (
        ShopifyStore.objects
        .select_related("user")
        .order_by("-last_product_sync", "-created_at")
    )
    marketplaces = (
        MarketplacePartner.objects.select_related("partner__user")
        .annotate(
            active_sellers=Count("seller_accounts", filter=Q(seller_accounts__status="active")),
            products_count=Count(
                "synced_products",
                filter=Q(synced_products__is_active=True),
                distinct=True,
            ),
        )
        .order_by("-created_at")
    )

    return render(request, COMMERCE_TEMPLATE.format(name="integrations"), _commerce_context({
        "page_title": "Integrations",
        "commerce_section": "integrations",
        "shopify_stores": shopify_stores,
        "marketplaces": marketplaces,
        "shopify_active": shopify_stores.filter(is_active=True).count(),
        "shopify_products_synced": shopify_stores.aggregate(t=Sum("products_synced"))["t"] or 0,
        "marketplace_active": marketplaces.filter(is_active=True).count(),
    }))


@staff_required
def commerce_stock_alerts(request):
    """Browse all stock alerts across all users."""
    qs = (
        StockAlert.objects
        .select_related("user", "product")
        .order_by("-created_at")
    )

    alert_type = request.GET.get("type")
    if alert_type in ("low_stock", "out_of_stock", "restocked", "featured_no_content", "overstock_no_promo"):
        qs = qs.filter(alert_type=alert_type)

    unread_only = request.GET.get("unread")
    if unread_only == "1":
        qs = qs.filter(is_read=False)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page", 1))

    return render(request, COMMERCE_TEMPLATE.format(name="alerts"), _commerce_context({
        "page_title": "Stock Alerts",
        "commerce_section": "alerts",
        "page_obj": page,
        "current_type": alert_type,
        "current_unread": unread_only,
    }))


@staff_required
def commerce_stock_updates(request):
    """Browse all stock update history across all users."""
    qs = (
        StockUpdate.objects
        .select_related("product", "product__user")
        .order_by("-created_at")
    )

    reason = request.GET.get("reason")
    if reason in ("manual", "sale", "restock", "adjustment"):
        qs = qs.filter(reason=reason)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page", 1))

    return render(request, COMMERCE_TEMPLATE.format(name="stock_updates"), _commerce_context({
        "page_title": "Stock History",
        "commerce_section": "stock",
        "page_obj": page,
        "current_reason": reason,
    }))


# Legacy aliases — old URL names still resolve
products_overview = commerce_overview
product_list_admin = commerce_catalog
stock_alerts_admin = commerce_stock_alerts
stock_updates_admin = commerce_stock_updates
