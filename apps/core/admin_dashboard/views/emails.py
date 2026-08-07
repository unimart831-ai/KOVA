"""
Admin dashboard views for the email system.
Provides monitoring, analytics, and management tools.
"""

import json
from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.admin_dashboard.decorators import senior_staff_required, staff_required
from apps.messaging.emails.models import EmailLog


@staff_required
def email_overview(request):
    """Email dashboard — key metrics, charts, recent activity."""
    now = timezone.now()
    today = now.date()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # ── Key metrics ──────────────────────────────────────────────────────
    total_sent = EmailLog.objects.filter(
        status__in=("sent", "delivered", "opened", "clicked"),
    ).count()

    sent_7d = EmailLog.objects.filter(
        created_at__gte=seven_days_ago,
        status__in=("sent", "delivered", "opened", "clicked"),
    ).count()

    sent_today = EmailLog.objects.filter(
        created_at__date=today,
        status__in=("sent", "delivered", "opened", "clicked"),
    ).count()

    failed_7d = EmailLog.objects.filter(
        created_at__gte=seven_days_ago,
        status__in=("failed", "bounced"),
    ).count()

    # Delivery rate
    total_attempted_7d = EmailLog.objects.filter(created_at__gte=seven_days_ago).exclude(status="queued").count()
    delivered_7d = EmailLog.objects.filter(
        created_at__gte=seven_days_ago,
        status__in=("delivered", "opened", "clicked"),
    ).count()
    delivery_rate = round((delivered_7d / total_attempted_7d) * 100, 1) if total_attempted_7d else 100.0

    # Open rate (of delivered)
    opened_7d = EmailLog.objects.filter(
        created_at__gte=seven_days_ago,
        status__in=("opened", "clicked"),
    ).count()
    open_rate = round((opened_7d / delivered_7d) * 100, 1) if delivered_7d else 0.0

    # Click rate (of opened)
    clicked_7d = EmailLog.objects.filter(
        created_at__gte=seven_days_ago,
        status="clicked",
    ).count()
    click_rate = round((clicked_7d / opened_7d) * 100, 1) if opened_7d else 0.0

    # Bounce rate
    bounced_7d = EmailLog.objects.filter(
        created_at__gte=seven_days_ago,
        status="bounced",
    ).count()
    bounce_rate = round((bounced_7d / total_attempted_7d) * 100, 1) if total_attempted_7d else 0.0

    # ── Emails by type (7d) ──────────────────────────────────────────────
    by_type = (
        EmailLog.objects.filter(created_at__gte=seven_days_ago)
        .values("email_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # ── Emails by status (7d) ────────────────────────────────────────────
    by_status = (
        EmailLog.objects.filter(created_at__gte=seven_days_ago)
        .values("status")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # ── Daily volume chart (30 days) ─────────────────────────────────────
    daily_volume = (
        EmailLog.objects.filter(created_at__gte=thirty_days_ago)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    chart_labels = [item["date"].strftime("%b %d") for item in daily_volume]
    chart_data = [item["count"] for item in daily_volume]

    # ── Recent emails ────────────────────────────────────────────────────
    recent_emails = (
        EmailLog.objects.select_related("user")
        .order_by("-created_at")[:20]
    )

    # ── Failed emails ────────────────────────────────────────────────────
    recent_failures = (
        EmailLog.objects.filter(status__in=("failed", "bounced"))
        .select_related("user")
        .order_by("-created_at")[:10]
    )

    context = {
        "total_sent": total_sent,
        "sent_7d": sent_7d,
        "sent_today": sent_today,
        "failed_7d": failed_7d,
        "delivery_rate": delivery_rate,
        "open_rate": open_rate,
        "click_rate": click_rate,
        "bounce_rate": bounce_rate,
        "by_type": by_type,
        "by_status": by_status,
        "chart_labels": json.dumps(chart_labels),
        "chart_data": json.dumps(chart_data),
        "recent_emails": recent_emails,
        "recent_failures": recent_failures,
        "email_type_choices": EmailLog.EmailType.choices,
    }
    return render(request, "admin_dashboard/emails/overview.html", context)


@staff_required
def email_log(request):
    """Paginated email log with filters."""
    emails = EmailLog.objects.select_related("user").order_by("-created_at")

    # Filters
    email_type = request.GET.get("type")
    status = request.GET.get("status")
    search = request.GET.get("q", "").strip()

    if email_type:
        emails = emails.filter(email_type=email_type)
    if status:
        emails = emails.filter(status=status)
    if search:
        emails = emails.filter(
            Q(to_email__icontains=search) |
            Q(subject__icontains=search) |
            Q(user__email__icontains=search)
        )

    context = {
        "emails": emails[:100],
        "email_type_choices": EmailLog.EmailType.choices,
        "status_choices": EmailLog.Status.choices,
        "current_type": email_type,
        "current_status": status,
        "search": search,
    }
    return render(request, "admin_dashboard/emails/log.html", context)


@staff_required
def email_detail(request, pk):
    """View details of a single email log entry."""
    from django.shortcuts import get_object_or_404
    email = get_object_or_404(EmailLog.objects.select_related("user"), pk=pk)
    return render(request, "admin_dashboard/emails/detail.html", {"email": email})


@staff_required
@require_POST
def send_test_email(request):
    """Send a test email to the admin user."""
    from apps.messaging.emails.services import email_service

    email_service._send(
        email_type="system",
        to_email=request.user.email,
        context={"message": "This is a test email from the Kova Agent admin dashboard. If you're reading this, email delivery is working correctly!"},
        user=request.user,
        subject="Test email from Kova Agent Admin",
        metadata={"source": "admin_test"},
    )
    return JsonResponse({"ok": True, "message": f"Test email sent to {request.user.email}"})


@senior_staff_required
@require_POST
def send_broadcast(request):
    """Send a feature announcement or promotional email to all active users. Requires senior staff."""
    from apps.core.accounts.models import UserProfile
    from apps.messaging.emails.tasks import send_feature_announcement_email

    broadcast_type = request.POST.get("broadcast_type", "feature_announcement")
    title = request.POST.get("title", "")
    body = request.POST.get("body", "")
    cta_url = request.POST.get("cta_url", "")

    if not title or not body:
        return JsonResponse({"ok": False, "message": "Title and body are required."}, status=400)

    # Get all active users
    profiles = UserProfile.objects.filter(
        subscription_status__in=("active", "trialing"),
    ).select_related("user")

    queued = 0
    for profile in profiles:
        send_feature_announcement_email.delay(
            str(profile.user.pk), title, body, cta_url,
        )
        queued += 1

    return JsonResponse({"ok": True, "message": f"Broadcast queued for {queued} users."})
