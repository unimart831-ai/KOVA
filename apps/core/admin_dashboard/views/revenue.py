from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.contrib import messages

from apps.core.admin_dashboard.decorators import senior_staff_required, staff_required
from apps.insight.analytics.models import (
    Conversion,
    ConversionJourney,
    ConversionTouchpoint,
    ShopifyStore,
)


@staff_required
def revenue_overview(request):
    """Platform-wide revenue attribution overview for admin."""
    now = timezone.now()
    days = int(request.GET.get("days", 30))
    if days not in (7, 14, 30, 90):
        days = 30
    cutoff = now - timedelta(days=days)

    # ── Global revenue stats ──────────────────────────────────────────
    conversions = Conversion.objects.filter(created_at__gte=cutoff)
    totals = conversions.aggregate(
        total_revenue=Sum("revenue"),
        total_conversions=Count("id"),
        total_sales=Count("id", filter=models_Q(conversion_type="sale")),
        total_leads=Count("id", filter=models_Q(conversion_type="lead")),
        total_clicks=Count("id", filter=models_Q(conversion_type="click")),
    )
    totals = {k: v or 0 for k, v in totals.items()}

    # ── Revenue by user (top 20) ─────────────────────────────────────
    top_users = list(
        conversions
        .values("user__email", "user__full_name", "user__id")
        .annotate(revenue=Sum("revenue"), count=Count("id"))
        .order_by("-revenue")[:20]
    )

    # ── Revenue by platform ──────────────────────────────────────────
    platform_revenue = list(
        conversions.exclude(social_account__isnull=True)
        .values("social_account__platform")
        .annotate(revenue=Sum("revenue"), count=Count("id"))
        .order_by("-revenue")
    )

    # ── Revenue by type (sale/lead/click/signup) ─────────────────────
    type_breakdown = list(
        conversions
        .values("conversion_type")
        .annotate(revenue=Sum("revenue"), count=Count("id"))
        .order_by("-revenue")
    )

    # ── Daily trend ──────────────────────────────────────────────────
    daily_trend = list(
        conversions

        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(revenue=Sum("revenue"), count=Count("id"))
        .order_by("date")
    )

    # ── Shopify stores (all) ─────────────────────────────────────────
    shopify_stores = ShopifyStore.objects.select_related("user").order_by("-total_revenue")
    total_shopify_revenue = shopify_stores.aggregate(t=Sum("total_revenue"))["t"] or 0
    total_shopify_orders = shopify_stores.aggregate(t=Sum("orders_tracked"))["t"] or 0

    # ── Conversion journeys stats ────────────────────────────────────
    journey_stats = ConversionJourney.objects.filter(created_at__gte=cutoff).aggregate(
        total_journeys=Count("id"),
        converted=Count("id", filter=models_Q(is_converted=True)),
        total_touchpoints=Sum("touchpoint_count"),
    )
    journey_stats = {k: v or 0 for k, v in journey_stats.items()}

    # ── Recent conversions (paginated) ───────────────────────────────
    recent_qs = (
        Conversion.objects
        .select_related("user", "post", "social_account", "product")
        .order_by("-created_at")
    )
    paginator = Paginator(recent_qs, 25)
    page_num = request.GET.get("page", 1)
    recent_page = paginator.get_page(page_num)

    return render(request, "admin_dashboard/revenue/overview.html", {
        "page_title": "Revenue Attribution",
        "days": days,
        "totals": totals,
        "top_users": top_users,
        "platform_revenue": platform_revenue,
        "type_breakdown": type_breakdown,
        "daily_trend": daily_trend,
        "shopify_stores": shopify_stores,
        "total_shopify_revenue": total_shopify_revenue,
        "total_shopify_orders": total_shopify_orders,
        "journey_stats": journey_stats,
        "recent_page": recent_page,
    })


# Use Q objects for filter expressions
from django.db.models import Q as models_Q


@staff_required
def conversion_list(request):
    """Browse all conversions across all users — filterable."""
    qs = Conversion.objects.select_related("user", "post", "social_account", "product").order_by("-created_at")

    # Filters
    ctype = request.GET.get("type")
    if ctype in ("sale", "lead", "click", "signup"):
        qs = qs.filter(conversion_type=ctype)

    user_email = request.GET.get("email")
    if user_email:
        qs = qs.filter(user__email__icontains=user_email)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page", 1))

    return render(request, "admin_dashboard/revenue/conversions.html", {
        "page_title": "All Conversions",
        "page_obj": page,
        "current_type": ctype,
        "current_email": user_email or "",
    })


@staff_required
def shopify_stores_list(request):
    """Manage all connected Shopify stores across all users."""
    stores = (
        ShopifyStore.objects
        .select_related("user")
        .order_by("-total_revenue")
    )
    return render(request, "admin_dashboard/revenue/shopify_stores.html", {
        "page_title": "Shopify Stores",
        "stores": stores,
    })


@senior_staff_required
def shopify_store_toggle(request, pk):
    """Activate/deactivate a Shopify store connection."""
    if request.method == "POST":
        store = get_object_or_404(ShopifyStore, pk=pk)
        store.is_active = not store.is_active
        store.save(update_fields=["is_active"])
        action = "activated" if store.is_active else "deactivated"
        messages.success(request, f"Shopify store {store.shop_domain} {action}.")
    return redirect("admin_dashboard:shopify_stores")


@staff_required
def journey_list(request):
    """Browse all conversion journeys across users."""
    qs = (
        ConversionJourney.objects
        .select_related("user", "conversion")
        .order_by("-created_at")
    )

    converted_only = request.GET.get("converted")
    if converted_only == "1":
        qs = qs.filter(is_converted=True)
    elif converted_only == "0":
        qs = qs.filter(is_converted=False)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page", 1))

    return render(request, "admin_dashboard/revenue/journeys.html", {
        "page_title": "Conversion Journeys",
        "page_obj": page,
        "current_filter": converted_only,
    })
