"""Admin dashboard — Leads & nurture pipeline."""

from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required
from apps.leads.models import Lead, LeadActivity, LeadEnrollment, NurtureSequence


@staff_required
def leads_overview(request):
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total = Lead.objects.count()
    new_7d = Lead.objects.filter(first_seen_at__gte=week_ago).count()
    new_30d = Lead.objects.filter(first_seen_at__gte=month_ago).count()
    high_priority = Lead.objects.filter(priority="high").exclude(
        status__in=["converted", "lost"],
    ).count()
    converted = Lead.objects.filter(status="converted").count()
    hot = Lead.objects.filter(temperature="hot").exclude(
        status__in=["converted", "lost"],
    ).count()

    by_status = list(
        Lead.objects.values("status").annotate(count=Count("id")).order_by("-count")
    )
    by_source = list(
        Lead.objects.values("source_type").annotate(count=Count("id")).order_by("-count")[:8]
    )

    nurture_sequences = NurtureSequence.objects.filter(is_active=True).count()
    active_enrollments = LeadEnrollment.objects.filter(completed=False, paused=False).count()
    emails_7d = LeadActivity.objects.filter(
        activity_type="email_sent", created_at__gte=week_ago,
    ).count()

    top_users = list(
        Lead.objects.values("user__email", "user__full_name", "user__id")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    recent = (
        Lead.objects.select_related("user")
        .order_by("-first_seen_at")[:15]
    )

    return render(request, "admin_dashboard/leads/overview.html", {
        "page_title": "Leads & Nurture",
        "total": total,
        "new_7d": new_7d,
        "new_30d": new_30d,
        "high_priority": high_priority,
        "converted": converted,
        "hot": hot,
        "by_status": by_status,
        "by_source": by_source,
        "nurture_sequences": nurture_sequences,
        "active_enrollments": active_enrollments,
        "emails_7d": emails_7d,
        "top_users": top_users,
        "recent": recent,
    })


@staff_required
def lead_list(request):
    qs = Lead.objects.select_related("user").order_by("-first_seen_at")

    status = request.GET.get("status")
    if status in dict(Lead.Status.choices):
        qs = qs.filter(status=status)

    priority = request.GET.get("priority")
    if priority in dict(Lead.Priority.choices):
        qs = qs.filter(priority=priority)

    email = request.GET.get("email")
    if email:
        qs = qs.filter(user__email__icontains=email)

    q = request.GET.get("q")
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q),
        )

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page", 1))

    return render(request, "admin_dashboard/leads/list.html", {
        "page_title": "All Leads",
        "page_obj": page,
        "current_status": status,
        "current_priority": priority,
        "current_email": email or "",
        "current_q": q or "",
    })
