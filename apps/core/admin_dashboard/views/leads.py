"""Admin dashboard — Leads & nurture pipeline."""

from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from apps.core.admin_dashboard.decorators import staff_required
from apps.commerce.leads.models import Lead, LeadActivity, LeadEnrollment, NurtureSequence

STALE_DAYS = 7


def _stale_leads_qs():
    cutoff = timezone.now() - timedelta(days=STALE_DAYS)
    return Lead.objects.exclude(
        status__in=[Lead.Status.CONVERTED, Lead.Status.LOST],
    ).filter(last_activity_at__lt=cutoff)


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
    due_enrollments = LeadEnrollment.objects.filter(
        completed=False, paused=False, next_step_at__lte=now,
    ).count()
    emails_7d = LeadActivity.objects.filter(
        activity_type="email_sent", created_at__gte=week_ago,
    ).count()
    whatsapp_7d = LeadActivity.objects.filter(
        activity_type="whatsapp_sent", created_at__gte=week_ago,
    ).count()

    stale_count = _stale_leads_qs().count()
    walk_in_leads = Lead.objects.filter(source_type=Lead.Source.WALK_IN).count()
    walk_in_leads_7d = Lead.objects.filter(
        source_type=Lead.Source.WALK_IN, first_seen_at__gte=week_ago,
    ).count()
    bridge_walk_in = Lead.objects.filter(source_type=Lead.Source.WALK_IN).count()
    bridge_booking = Lead.objects.filter(source_type=Lead.Source.BOOKING).count()
    bridge_commerce = Lead.objects.filter(source_type=Lead.Source.COMMERCE_PURCHASE).count()
    bridge_qr = Lead.objects.filter(source_type=Lead.Source.QR_SCAN).count()

    walk_ins_total = 0
    walk_ins_7d = 0
    walk_ins_with_contact = 0

    top_sequences = list(
        NurtureSequence.objects.annotate(
            active=Count(
                "enrollments",
                filter=Q(enrollments__completed=False, enrollments__paused=False),
            ),
        )
        .order_by("-active")[:6]
    )

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
        "due_enrollments": due_enrollments,
        "emails_7d": emails_7d,
        "whatsapp_7d": whatsapp_7d,
        "stale_count": stale_count,
        "stale_cutoff_days": STALE_DAYS,
        "walk_in_leads": walk_in_leads,
        "walk_in_leads_7d": walk_in_leads_7d,
        "bridge_walk_in": bridge_walk_in,
        "bridge_booking": bridge_booking,
        "bridge_commerce": bridge_commerce,
        "bridge_qr": bridge_qr,
        "walk_ins_total": walk_ins_total,
        "walk_ins_7d": walk_ins_7d,
        "walk_ins_with_contact": walk_ins_with_contact,
        "top_sequences": top_sequences,
        "top_users": top_users,
        "recent": recent,
    })


@staff_required
def leads_nurture(request):
    """Platform-wide nurture sequence health."""
    now = timezone.now()
    sequences = (
        NurtureSequence.objects.select_related("user")
        .annotate(
            step_count=Count("steps"),
            active_enrollments=Count(
                "enrollments",
                filter=Q(enrollments__completed=False, enrollments__paused=False),
            ),
            due_now=Count(
                "enrollments",
                filter=Q(
                    enrollments__completed=False,
                    enrollments__paused=False,
                    enrollments__next_step_at__lte=now,
                ),
            ),
            completed_enrollments=Count(
                "enrollments", filter=Q(enrollments__completed=True),
            ),
        )
        .order_by("-active_enrollments", "-created_at")
    )

    is_active = request.GET.get("active")
    if is_active == "1":
        sequences = sequences.filter(is_active=True)
    elif is_active == "0":
        sequences = sequences.filter(is_active=False)

    trigger = request.GET.get("trigger")
    if trigger in dict(NurtureSequence.Trigger.choices):
        sequences = sequences.filter(trigger=trigger)

    paginator = Paginator(sequences, 40)
    page = paginator.get_page(request.GET.get("page", 1))

    totals = NurtureSequence.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
    )
    enrollment_totals = LeadEnrollment.objects.aggregate(
        active=Count("id", filter=Q(completed=False, paused=False)),
        due=Count(
            "id",
            filter=Q(completed=False, paused=False, next_step_at__lte=now),
        ),
        paused=Count("id", filter=Q(paused=True, completed=False)),
    )

    return render(request, "admin_dashboard/leads/nurture.html", {
        "page_title": "Nurture Sequences",
        "page_obj": page,
        "current_active": is_active,
        "current_trigger": trigger or "",
        "trigger_choices": NurtureSequence.Trigger.choices,
        "totals": totals,
        "enrollment_totals": enrollment_totals,
        "stale_count": _stale_leads_qs().count(),
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

    source = request.GET.get("source")
    if source in dict(Lead.Source.choices):
        qs = qs.filter(source_type=source)

    if request.GET.get("stale") == "1":
        qs = _stale_leads_qs()

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

    page_title = "All Leads"
    if request.GET.get("stale") == "1":
        page_title = f"Stale Leads ({STALE_DAYS}+ days inactive)"

    return render(request, "admin_dashboard/leads/list.html", {
        "page_title": page_title,
        "page_obj": page,
        "current_status": status,
        "current_priority": priority,
        "current_source": source or "",
        "current_stale": request.GET.get("stale") == "1",
        "current_email": email or "",
        "current_q": q or "",
        "source_choices": Lead.Source.choices,
    })
