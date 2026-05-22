from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required
from apps.agents.models import AgentAction
from apps.products.models import Product, ProductCategory, StockAlert, StockUpdate


@staff_required
def products_overview(request):
    """Platform-wide product catalog health for admin."""
    now = timezone.now()

    # ── Global product stats ──────────────────────────────────────────
    total_products = Product.objects.filter(is_active=True).count()
    total_users_with_products = (
        Product.objects.filter(is_active=True)
        .values("user").distinct().count()
    )

    stock_breakdown = dict(
        Product.objects.filter(is_active=True)
        .values_list("stock_status")
        .annotate(c=Count("id"))
        .values_list("stock_status", "c")
    )
    in_stock = stock_breakdown.get("in_stock", 0)
    low_stock = stock_breakdown.get("low_stock", 0)
    out_of_stock = stock_breakdown.get("out_of_stock", 0)
    made_to_order = stock_breakdown.get("made_to_order", 0)
    unlimited = stock_breakdown.get("unlimited", 0)
    featured = Product.objects.filter(is_active=True, is_featured=True).count()

    # ── Alerts (unread, last 7d) ─────────────────────────────────────
    week_ago = now - timedelta(days=7)
    unread_alerts = StockAlert.objects.filter(is_read=False).count()
    recent_alerts = (
        StockAlert.objects
        .select_related("user", "product")
        .filter(created_at__gte=week_ago)
        .order_by("-created_at")[:20]
    )

    # ── Stock updates trend (7d) ─────────────────────────────────────
    updates_7d = (
        StockUpdate.objects
        .filter(created_at__gte=week_ago)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )

    # ── Top users by product count ───────────────────────────────────
    top_users = list(
        Product.objects.filter(is_active=True)
        .values("user__email", "user__full_name", "user__id")
        .annotate(
            product_count=Count("id"),
            low=Count("id", filter=Q(stock_status="low_stock")),
            oos=Count("id", filter=Q(stock_status="out_of_stock")),
        )
        .order_by("-product_count")[:20]
    )

    # ── Categories across platform ───────────────────────────────────
    total_categories = ProductCategory.objects.filter(is_active=True).count()

    # ── Recent products ──────────────────────────────────────────────
    recent_products = (
        Product.objects
        .select_related("user", "category")
        .filter(is_active=True)
        .order_by("-created_at")[:15]
    )

    # ── Auto-Promotion / Catalog Sampling Stats ────────────────────────
    from apps.content.models import ContentSeed, Post
    from django.db.models import Exists, OuterRef

    catalog_sample_seeds = ContentSeed.objects.filter(
        notes__startswith="Catalog sample:",
    ).count()
    catalog_sample_7d = ContentSeed.objects.filter(
        notes__startswith="Catalog sample:",
        created_at__gte=week_ago,
    ).count()
    legacy_auto_promo = ContentSeed.objects.filter(
        notes__startswith="Auto-promoted:",
    ).count()
    strategist_product_seeds = ContentSeed.objects.filter(
        product__isnull=False,
        notes__startswith="[Strategist Agent]",
    ).count()

    products_with_posts = Post.objects.filter(product=OuterRef("pk"))
    never_promoted = Product.objects.filter(is_active=True).exclude(
        Exists(products_with_posts),
    ).count()

    # ── Motion media pipelines ───────────────────────────────────────
    snap_carousel = AgentAction.objects.filter(action_type="snap.carousel").count()
    snap_reel = AgentAction.objects.filter(action_type="snap.reel").count()
    snap_carousel_7d = AgentAction.objects.filter(
        action_type="snap.carousel", created_at__gte=week_ago,
    ).count()
    snap_reel_7d = AgentAction.objects.filter(
        action_type="snap.reel", created_at__gte=week_ago,
    ).count()
    reel_posts = Post.objects.filter(post_format="reel").count()
    reel_posts_7d = Post.objects.filter(
        post_format="reel", created_at__gte=week_ago,
    ).count()

    offering_breakdown = dict(
        Product.objects.filter(is_active=True)
        .values_list("offering_type")
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

    multi_image_products = Product.objects.filter(
        is_active=True,
    ).exclude(additional_images=[]).count()

    return render(request, "admin_dashboard/products/overview.html", {
        "page_title": "Product Intelligence",
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
        # Offering type breakdown
        "products_count": products_count,
        "services_count": services_count,
        "digital_count": digital_count,
        # Snap to Sell stats
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
    })


@staff_required
def product_list_admin(request):
    """Browse all products across all users — filterable."""
    qs = Product.objects.select_related("user", "category").filter(is_active=True).order_by("-created_at")

    # Filters
    status = request.GET.get("status")
    if status in ("in_stock", "low_stock", "out_of_stock", "made_to_order", "unlimited"):
        qs = qs.filter(stock_status=status)

    user_email = request.GET.get("email")
    if user_email:
        qs = qs.filter(user__email__icontains=user_email)

    q = request.GET.get("q")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

    featured_only = request.GET.get("featured")
    if featured_only == "1":
        qs = qs.filter(is_featured=True)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page", 1))

    return render(request, "admin_dashboard/products/product_list.html", {
        "page_title": "All Products",
        "page_obj": page,
        "current_status": status,
        "current_email": user_email or "",
        "current_q": q or "",
        "current_featured": featured_only,
    })


@staff_required
def stock_alerts_admin(request):
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

    return render(request, "admin_dashboard/products/alerts.html", {
        "page_title": "Stock Alerts",
        "page_obj": page,
        "current_type": alert_type,
        "current_unread": unread_only,
    })


@staff_required
def stock_updates_admin(request):
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

    return render(request, "admin_dashboard/products/stock_updates.html", {
        "page_title": "Stock Update History",
        "page_obj": page,
        "current_reason": reason,
    })
