from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required
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

    # ── Auto-Promotion Stats ─────────────────────────────────────────
    from apps.content.models import ContentSeed
    auto_promo_seeds = ContentSeed.objects.filter(
        notes__startswith="[Auto-Promo]",
    ).count()
    auto_promo_7d = ContentSeed.objects.filter(
        notes__startswith="[Auto-Promo]",
        created_at__gte=week_ago,
    ).count()

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
        "auto_promo_seeds": auto_promo_seeds,
        "auto_promo_7d": auto_promo_7d,
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
