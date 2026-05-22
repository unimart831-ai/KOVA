"""Admin dashboard — Bookings."""

from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required
from apps.bookings.models import Booking, BookingLink


@staff_required
def bookings_overview(request):
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total_links = BookingLink.objects.count()
    active_links = BookingLink.objects.filter(is_active=True).count()
    total_bookings = Booking.objects.count()
    bookings_7d = Booking.objects.filter(created_at__gte=week_ago).count()
    completed = Booking.objects.filter(status=Booking.Status.COMPLETED).count()
    completed_7d = Booking.objects.filter(
        status=Booking.Status.COMPLETED,
        completed_at__gte=week_ago,
    ).count()
    pending = Booking.objects.filter(status=Booking.Status.PENDING).count()
    cancelled = Booking.objects.filter(status=Booking.Status.CANCELLED).count()
    no_show = Booking.objects.filter(status=Booking.Status.NO_SHOW).count()

    by_status = list(
        Booking.objects.values("status").annotate(count=Count("id")).order_by("-count")
    )
    by_template = list(
        BookingLink.objects.values("industry_template")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    top_users = list(
        Booking.objects.values(
            "booking_link__user__email",
            "booking_link__user__full_name",
            "booking_link__user__id",
        )
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    recent = (
        Booking.objects.select_related("booking_link", "booking_link__user")
        .order_by("-created_at")[:15]
    )

    return render(request, "admin_dashboard/bookings/overview.html", {
        "page_title": "Bookings",
        "total_links": total_links,
        "active_links": active_links,
        "total_bookings": total_bookings,
        "bookings_7d": bookings_7d,
        "completed": completed,
        "completed_7d": completed_7d,
        "pending": pending,
        "cancelled": cancelled,
        "no_show": no_show,
        "by_status": by_status,
        "by_template": by_template,
        "top_users": top_users,
        "recent": recent,
    })


@staff_required
def booking_list(request):
    qs = Booking.objects.select_related("booking_link", "booking_link__user").order_by("-created_at")

    status = request.GET.get("status")
    if status in dict(Booking.Status.choices):
        qs = qs.filter(status=status)

    email = request.GET.get("email")
    if email:
        qs = qs.filter(booking_link__user__email__icontains=email)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page", 1))

    return render(request, "admin_dashboard/bookings/list.html", {
        "page_title": "All Bookings",
        "page_obj": page,
        "current_status": status,
        "current_email": email or "",
    })
