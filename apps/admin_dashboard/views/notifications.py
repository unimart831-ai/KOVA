"""Admin dashboard views for in-app notifications."""
from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required
from apps.notifications.models import Notification, NotificationPreference


@staff_required
def notifications_overview(request):
    """Notifications sent (by type, by day) + per-user preference summary."""
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # ── Volume ─────────────────────────────────────────────────────
    total = Notification.objects.count()
    sent_7d = Notification.objects.filter(created_at__gte=week_ago).count()
    sent_30d = Notification.objects.filter(created_at__gte=month_ago).count()
    unread = Notification.objects.filter(is_read=False).count()
    unread_7d = Notification.objects.filter(
        is_read=False, created_at__gte=week_ago,
    ).count()

    # ── Type breakdown ─────────────────────────────────────────────
    type_breakdown = list(
        Notification.objects.filter(created_at__gte=month_ago)
        .values("notification_type")
        .annotate(total=Count("id"), unread=Count("id", filter=Q(is_read=False)))
        .order_by("-total")
    )

    # ── Daily volume (7d) ──────────────────────────────────────────
    daily_volume = list(
        Notification.objects.filter(created_at__gte=week_ago)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )

    # ── Top recipients (last 30 days) ──────────────────────────────
    top_recipients = list(
        Notification.objects.filter(created_at__gte=month_ago)
        .values("user__email", "user__full_name", "user__id")
        .annotate(
            total=Count("id"),
            unread=Count("id", filter=Q(is_read=False)),
        )
        .order_by("-total")[:10]
    )

    # ── Preference engagement ──────────────────────────────────────
    total_pref_rows = NotificationPreference.objects.count()

    # ── Recent stream ──────────────────────────────────────────────
    recent = list(
        Notification.objects
        .select_related("user", "related_post")
        .order_by("-created_at")[:20]
    )

    return render(request, "admin_dashboard/notifications/overview.html", {
        "page_title": "Notifications",
        "total": total,
        "sent_7d": sent_7d,
        "sent_30d": sent_30d,
        "unread": unread,
        "unread_7d": unread_7d,
        "type_breakdown": type_breakdown,
        "daily_volume": daily_volume,
        "top_recipients": top_recipients,
        "total_pref_rows": total_pref_rows,
        "recent": recent,
    })


@staff_required
def notification_log(request):
    """Paginated notifications log filterable by type and read state."""
    notif_type = request.GET.get("type", "")
    read_state = request.GET.get("read", "")

    qs = (
        Notification.objects
        .select_related("user", "related_post")
        .order_by("-created_at")
    )
    if notif_type:
        qs = qs.filter(notification_type=notif_type)
    if read_state == "unread":
        qs = qs.filter(is_read=False)
    elif read_state == "read":
        qs = qs.filter(is_read=True)

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "admin_dashboard/notifications/log.html", {
        "page_title": "Notification Log",
        "page_obj": page_obj,
        "current_type": notif_type,
        "current_read": read_state,
        "types": Notification.NotificationType.choices,
    })
