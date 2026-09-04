from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.commerce.leads.forms import LeadForm, LeadNoteForm, LeadTagForm
from apps.commerce.leads.models import Lead, LeadActivity


@login_required
def lead_list(request):
    """Lead inbox with filters."""
    leads = Lead.objects.filter(user=request.user).select_related("marketing_campaign")

    # Filters
    status = request.GET.get("status")
    priority = request.GET.get("priority")
    source = request.GET.get("source")
    campaign = request.GET.get("campaign", "").strip()
    q = request.GET.get("q", "").strip()

    if status:
        leads = leads.filter(status=status)
    if priority:
        leads = leads.filter(priority=priority)
    if source:
        leads = leads.filter(source_type=source)
    if campaign:
        leads = leads.filter(marketing_campaign_id=campaign)
    if q:
        from apps.core.utils.search import full_text_search
        leads = full_text_search(leads, q, ["email", "name", "notes"])

    leads = leads.annotate(activity_count=Count("activities"))[:100]

    # Stats
    stats = Lead.objects.filter(user=request.user).aggregate(
        total=Count("id"),
        new=Count("id", filter=Q(status="new")),
        qualified=Count("id", filter=Q(status="qualified")),
        converted=Count("id", filter=Q(status="converted")),
    )

    return render(request, "dashboard/leads.html", {
        "leads": leads,
        "stats": stats,
        "current_status": status,
        "current_priority": priority,
        "current_source": source,
        "current_q": q,
        "page_title": "Lead Inbox",
        "business_model": getattr(getattr(request.user, "profile", None), "business_model", ""),
    })


@login_required
def lead_pipeline(request):
    """Kanban-style pipeline grouped by lead status."""
    base_qs = Lead.objects.filter(user=request.user).order_by("-last_activity_at")
    columns = []
    for status_value, status_label in Lead.Status.choices:
        columns.append({
            "status": status_value,
            "label": status_label,
            "leads": list(base_qs.filter(status=status_value)[:30]),
        })
    return render(request, "dashboard/leads/lead_pipeline.html", {
        "columns": columns,
        "page_title": "Lead Pipeline",
    })


@login_required
def lead_create(request):
    """Manually add a lead."""
    from apps.core.billing.enforcement import check_leads_limit, enforce_or_redirect

    if request.method == "POST":
        allowed, msg = check_leads_limit(request.user, creating=True)
        if blocked := enforce_or_redirect(request, allowed, msg, "leads:list"):
            return blocked

        form = LeadForm(request.POST)
        if form.is_valid():
            lead = form.save(commit=False)
            lead.user = request.user
            lead.save()
            LeadActivity.objects.create(
                lead=lead,
                activity_type=LeadActivity.ActivityType.NOTE_ADDED,
                description="Lead created manually.",
            )
            messages.success(request, f"Lead '{lead.name or lead.email}' added!")
            return redirect("leads:detail", lead_id=lead.pk)
    else:
        form = LeadForm()

    return render(request, "dashboard/leads/lead_form.html", {
        "form": form,
        "page_title": "Add Lead",
        "is_edit": False,
    })


@login_required
def lead_detail(request, lead_id):
    """Lead detail with activity timeline."""
    from apps.commerce.leads.defaults import WELCOME_SEQUENCE_NAME, ensure_default_nurture_sequences
    from apps.commerce.leads.models import LeadEnrollment, NurtureSequence, NurtureStep

    lead = get_object_or_404(Lead, pk=lead_id, user=request.user)
    activities = lead.activities.all()[:50]
    note_form = LeadNoteForm()
    tag_form = LeadTagForm()

    active_enrollment = (
        lead.enrollments.filter(completed=False, paused=False, sequence__is_active=True)
        .select_related("sequence")
        .order_by("-enrolled_at")
        .first()
    )
    current_nurture_step = None
    if active_enrollment:
        current_nurture_step = NurtureStep.objects.filter(
            sequence=active_enrollment.sequence,
            order=active_enrollment.current_step,
        ).first()

    ensure_default_nurture_sequences(request.user)
    suggested_sequence = NurtureSequence.objects.filter(
        user=request.user,
        name=WELCOME_SEQUENCE_NAME,
        is_active=True,
    ).first()
    if not suggested_sequence:
        suggested_sequence = NurtureSequence.objects.filter(
            user=request.user, is_active=True,
        ).first()

    return render(request, "dashboard/leads/lead_detail.html", {
        "lead": lead,
        "activities": activities,
        "note_form": note_form,
        "tag_form": tag_form,
        "active_enrollment": active_enrollment,
        "current_nurture_step": current_nurture_step,
        "suggested_sequence": suggested_sequence,
        "page_title": lead.name or lead.email,
    })


@login_required
def lead_edit(request, lead_id):
    """Edit a lead."""
    from apps.core.billing.enforcement import check_leads_can_edit, enforce_or_redirect

    allowed, msg = check_leads_can_edit(request.user)
    if blocked := enforce_or_redirect(request, allowed, msg, "leads:list"):
        return blocked

    lead = get_object_or_404(Lead, pk=lead_id, user=request.user)
    if request.method == "POST":
        form = LeadForm(request.POST, instance=lead)
        if form.is_valid():
            form.save()
            messages.success(request, "Lead updated.")
            return redirect("leads:detail", lead_id=lead.pk)
    else:
        form = LeadForm(instance=lead)

    return render(request, "dashboard/leads/lead_form.html", {
        "form": form,
        "lead": lead,
        "page_title": "Edit Lead",
        "is_edit": True,
    })


@login_required
@require_POST
def lead_change_status(request, lead_id):
    """Quick status change (HTMX-aware)."""
    lead = get_object_or_404(Lead, pk=lead_id, user=request.user)
    new_status = request.POST.get("status")
    if new_status not in dict(Lead.Status.choices):
        raise Http404

    old_status = lead.status
    lead.status = new_status
    update_fields = ["status", "last_activity_at"]
    if new_status == Lead.Status.CONVERTED and not lead.converted_at:
        lead.converted_at = timezone.now()
        update_fields.append("converted_at")
    lead.save(update_fields=update_fields)

    LeadActivity.objects.create(
        lead=lead,
        activity_type=LeadActivity.ActivityType.STATUS_CHANGED,
        description=f"Status changed from {old_status} to {new_status}",
    )

    if request.headers.get("HX-Request"):
        return render(request, "dashboard/leads/partials/lead_status_badge.html", {"lead": lead})
    return redirect("leads:detail", lead_id=lead.pk)


@login_required
@require_POST
def lead_add_note(request, lead_id):
    """Add a note to a lead."""
    lead = get_object_or_404(Lead, pk=lead_id, user=request.user)
    form = LeadNoteForm(request.POST)
    if form.is_valid():
        note_text = form.cleaned_data["note"]
        if lead.notes:
            lead.notes += f"\n\n---\n{note_text}"
        else:
            lead.notes = note_text
        lead.save(update_fields=["notes", "last_activity_at"])

        LeadActivity.objects.create(
            lead=lead,
            activity_type=LeadActivity.ActivityType.NOTE_ADDED,
            description=note_text[:300],
        )

    if request.headers.get("HX-Request"):
        activities = lead.activities.all()[:50]
        return render(request, "dashboard/leads/partials/activity_timeline.html", {"activities": activities, "lead": lead})
    return redirect("leads:detail", lead_id=lead.pk)


@login_required
@require_POST
def lead_add_tag(request, lead_id):
    """Add a tag to a lead."""
    lead = get_object_or_404(Lead, pk=lead_id, user=request.user)
    form = LeadTagForm(request.POST)
    if form.is_valid():
        tag = form.cleaned_data["tag"].strip().lower()
        if tag not in lead.tags:
            lead.tags.append(tag)
            lead.save(update_fields=["tags", "last_activity_at"])
            LeadActivity.objects.create(
                lead=lead,
                activity_type=LeadActivity.ActivityType.TAG_ADDED,
                description=f"Tag added: {tag}",
            )

    if request.headers.get("HX-Request"):
        return render(request, "dashboard/leads/partials/lead_tags.html", {"lead": lead})
    return redirect("leads:detail", lead_id=lead.pk)


@login_required
@require_POST
def lead_remove_tag(request, lead_id):
    """Remove a tag from a lead."""
    lead = get_object_or_404(Lead, pk=lead_id, user=request.user)
    tag = request.POST.get("tag", "").strip().lower()
    if tag in lead.tags:
        lead.tags.remove(tag)
        lead.save(update_fields=["tags", "last_activity_at"])

    if request.headers.get("HX-Request"):
        return render(request, "dashboard/leads/partials/lead_tags.html", {"lead": lead})
    return redirect("leads:detail", lead_id=lead.pk)


@login_required
def lead_analytics(request):
    """Lead funnel analytics with commerce + booking conversion data."""
    leads = Lead.objects.filter(user=request.user)

    by_status = {}
    for s in Lead.Status.choices:
        by_status[s[1]] = leads.filter(status=s[0]).count()

    by_source = {}
    for s in Lead.Source.choices:
        count = leads.filter(source_type=s[0]).count()
        if count:
            by_source[s[1]] = count

    by_priority = {}
    for p in Lead.Priority.choices:
        by_priority[p[1]] = leads.filter(priority=p[0]).count()

    by_temperature = {}
    for t in Lead.Temperature.choices:
        by_temperature[t[1]] = leads.filter(temperature=t[0]).count()

    total = leads.count()
    converted = leads.filter(status=Lead.Status.CONVERTED).count()
    conversion_rate = round((converted / total * 100), 1) if total else 0

    # Commerce conversion metrics
    commerce_leads = leads.filter(source_type=Lead.Source.COMMERCE_PURCHASE).count()
    booking_leads = leads.filter(source_type=Lead.Source.BOOKING).count()
    social_leads = leads.filter(source_type__in=[Lead.Source.SOCIAL_DM, Lead.Source.SOCIAL_COMMENT]).count()
    form_leads = leads.filter(source_type=Lead.Source.FORM_SUBMISSION).count()

    # Revenue attribution from commerce leads
    from apps.commerce.leads.models import LeadActivity
    commerce_activities = LeadActivity.objects.filter(
        lead__user=request.user,
        activity_type=LeadActivity.ActivityType.COMMERCE_PURCHASE,
    )
    total_commerce_revenue = sum(
        float(a.metadata.get("amount", 0)) for a in commerce_activities.only("metadata")[:500]
    )

    return render(request, "dashboard/leads/lead_analytics.html", {
        "by_status": by_status,
        "by_source": by_source,
        "by_priority": by_priority,
        "by_temperature": by_temperature,
        "total": total,
        "converted": converted,
        "conversion_rate": conversion_rate,
        "commerce_leads": commerce_leads,
        "booking_leads": booking_leads,
        "social_leads": social_leads,
        "form_leads": form_leads,
        "total_commerce_revenue": total_commerce_revenue,
        "page_title": "Lead Analytics",
    })


# ─── Lead Nurture Sequences ─────────────────────────────────────────────────


@login_required
def nurture_list(request):
    """List all nurture sequences."""
    from apps.commerce.leads.models import LeadEnrollment, NurtureSequence

    sequences = NurtureSequence.objects.filter(user=request.user).prefetch_related("steps")
    active_count = sequences.filter(is_active=True).count()

    total_enrolled = LeadEnrollment.objects.filter(sequence__user=request.user).count()
    total_completed = LeadEnrollment.objects.filter(sequence__user=request.user, completed=True).count()

    return render(request, "dashboard/leads/nurture_list.html", {
        "sequences": sequences,
        "active_count": active_count,
        "total_enrolled": total_enrolled,
        "total_completed": total_completed,
        "page_title": "Nurture Sequences",
    })


def _nurture_whatsapp_allowed(user) -> bool:
    from apps.core.billing.models import get_user_plan_limits

    from apps.core.billing.whatsapp_access import whatsapp_inbox_allowed

    return whatsapp_inbox_allowed(get_user_plan_limits(user))


@login_required
def nurture_create(request):
    """Create a new nurture sequence with steps."""
    from apps.commerce.leads.models import NurtureSequence, NurtureStep

    whatsapp_enabled = _nurture_whatsapp_allowed(request.user)

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        trigger = request.POST.get("trigger", "all_new")
        trigger_platform = request.POST.get("trigger_platform", "").strip()

        if not name:
            messages.error(request, "Sequence name is required.")
            return redirect("leads:nurture_create")

        sequence = NurtureSequence.objects.create(
            user=request.user,
            name=name,
            trigger=trigger,
            trigger_platform=trigger_platform,
        )

        step_count = int(request.POST.get("step_count", 0))
        for i in range(step_count):
            delay = int(request.POST.get(f"step_{i}_delay", 1))
            action = request.POST.get(f"step_{i}_action", "send_email")
            if action == NurtureStep.ActionType.SEND_WHATSAPP and not whatsapp_enabled:
                messages.error(
                    request,
                    "WhatsApp nurture steps require a Pro or Agency plan with WhatsApp enabled.",
                )
                sequence.delete()
                return redirect("leads:nurture_create")
            NurtureStep.objects.create(
                sequence=sequence,
                order=i,
                delay_hours=max(0, delay),
                action_type=action,
                email_subject=request.POST.get(f"step_{i}_subject", ""),
                email_body=request.POST.get(f"step_{i}_body", ""),
                tag_value=request.POST.get(f"step_{i}_tag", "").strip().lower(),
                status_value=request.POST.get(f"step_{i}_status", ""),
            )

        messages.success(request, f"Nurture sequence '{name}' created!")
        return redirect("leads:nurture_detail", sequence_id=sequence.pk)

    return render(request, "dashboard/leads/nurture_form.html", {
        "page_title": "New Nurture Sequence",
        "is_edit": False,
        "whatsapp_enabled": whatsapp_enabled,
    })


@login_required
def nurture_detail(request, sequence_id):
    """View a nurture sequence with steps and enrolled leads."""
    from apps.commerce.leads.models import NurtureSequence

    sequence = get_object_or_404(NurtureSequence, pk=sequence_id, user=request.user)
    steps = sequence.steps.all()
    enrollments = sequence.enrollments.select_related("lead").all()[:50]

    return render(request, "dashboard/leads/nurture_detail.html", {
        "sequence": sequence,
        "steps": steps,
        "enrollments": enrollments,
        "page_title": sequence.name,
    })


@login_required
@require_POST
def nurture_toggle(request, sequence_id):
    """Toggle a nurture sequence active/paused."""
    from apps.commerce.leads.models import NurtureSequence

    sequence = get_object_or_404(NurtureSequence, pk=sequence_id, user=request.user)
    sequence.is_active = not sequence.is_active
    sequence.save(update_fields=["is_active"])
    status = "activated" if sequence.is_active else "paused"
    messages.success(request, f"Sequence '{sequence.name}' {status}.")
    return redirect("leads:nurture_list")


@login_required
@require_POST
def lead_enroll_nurture(request, lead_id):
    """Manually enroll a lead in a nurture sequence (default: Welcome new leads)."""
    from datetime import timedelta

    from apps.commerce.leads.defaults import WELCOME_SEQUENCE_NAME, ensure_default_nurture_sequences
    from apps.commerce.leads.models import LeadEnrollment, NurtureSequence, NurtureStep

    lead = get_object_or_404(Lead, pk=lead_id, user=request.user)

    if lead.enrollments.filter(completed=False, paused=False, sequence__is_active=True).exists():
        messages.info(request, "This lead is already in an active nurture sequence.")
        return redirect("leads:detail", lead_id=lead.pk)

    ensure_default_nurture_sequences(request.user)
    sequence_id = request.POST.get("sequence_id", "").strip()
    if sequence_id:
        sequence = get_object_or_404(NurtureSequence, pk=sequence_id, user=request.user)
    else:
        sequence = NurtureSequence.objects.filter(
            user=request.user, name=WELCOME_SEQUENCE_NAME, is_active=True,
        ).first()
        if not sequence:
            sequence = NurtureSequence.objects.filter(
                user=request.user, is_active=True,
            ).first()

    if not sequence:
        messages.error(request, "No active nurture sequence — create one first.")
        return redirect("leads:nurture_create")

    if LeadEnrollment.objects.filter(lead=lead, sequence=sequence).exists():
        messages.info(request, f"Already enrolled in “{sequence.name}”.")
        return redirect("leads:detail", lead_id=lead.pk)

    first_step = NurtureStep.objects.filter(sequence=sequence, order=0).first()
    if not first_step:
        messages.error(request, "That sequence has no steps yet.")
        return redirect("leads:nurture_detail", sequence_id=sequence.pk)

    now = timezone.now()
    LeadEnrollment.objects.create(
        lead=lead,
        sequence=sequence,
        current_step=0,
        next_step_at=now + timedelta(hours=first_step.delay_hours),
    )
    messages.success(request, f"Enrolled in “{sequence.name}” — follow-up starts automatically.")
    return redirect("leads:detail", lead_id=lead.pk)
