"""Admin dashboard — QR attribution & walk-ins."""

from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from apps.core.admin_dashboard.decorators import staff_required
from apps.commerce.qr_attribution.models import QRCode, QRScan, WalkInEvent


@staff_required
def qr_overview(request):
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total_codes = QRCode.objects.count()
    active_codes = QRCode.objects.filter(is_active=True).count()
    total_scans = QRScan.objects.count()
    scans_7d = QRScan.objects.filter(scanned_at__gte=week_ago).count()
    scans_30d = QRScan.objects.filter(scanned_at__gte=month_ago).count()
    walk_ins = WalkInEvent.objects.count()
    walk_ins_7d = WalkInEvent.objects.filter(recorded_at__gte=week_ago).count()

    by_template = list(
        QRCode.objects.values("landing_template")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    top_codes = list(
        QRScan.objects.values("qr_code__label", "qr_code__token", "qr_code__id")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    top_users = list(
        QRCode.objects.values("user__email", "user__full_name", "user__id")
        .annotate(codes=Count("id"))
        .order_by("-codes")[:10]
    )

    recent_scans = (
        QRScan.objects.select_related("qr_code", "qr_code__user")
        .order_by("-scanned_at")[:15]
    )
    recent_walkins = (
        WalkInEvent.objects.select_related("user", "qr_code")
        .order_by("-recorded_at")[:10]
    )

    return render(request, "admin_dashboard/qr/overview.html", {
        "page_title": "QR & Walk-ins",
        "total_codes": total_codes,
        "active_codes": active_codes,
        "total_scans": total_scans,
        "scans_7d": scans_7d,
        "scans_30d": scans_30d,
        "walk_ins": walk_ins,
        "walk_ins_7d": walk_ins_7d,
        "by_template": by_template,
        "top_codes": top_codes,
        "top_users": top_users,
        "recent_scans": recent_scans,
        "recent_walkins": recent_walkins,
    })


@staff_required
def qr_list(request):
    qs = QRCode.objects.select_related("user", "campaign", "post").order_by("-created_at")

    active = request.GET.get("active")
    if active == "1":
        qs = qs.filter(is_active=True)
    elif active == "0":
        qs = qs.filter(is_active=False)

    email = request.GET.get("email")
    if email:
        qs = qs.filter(user__email__icontains=email)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page", 1))

    return render(request, "admin_dashboard/qr/list.html", {
        "page_title": "All QR Codes",
        "page_obj": page,
        "current_active": active,
        "current_email": email or "",
    })
