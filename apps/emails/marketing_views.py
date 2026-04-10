"""
Email marketing views — campaigns, subscribers, lists, sequences.
Sprint 6D addition to the emails app.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.emails.forms import EmailCampaignForm, EmailListForm, EmailSubscriberForm
from apps.emails.models import (
    EmailCampaign,
    EmailList,
    EmailSequence,
    EmailSubscriber,
)
from apps.billing.models import get_plan_limits


# ────────────────────────────────────────────────────────────────────
# Subscribers
# ────────────────────────────────────────────────────────────────────


@login_required
def subscriber_list(request):
    """List all subscribers with filters."""
    subs = EmailSubscriber.objects.filter(user=request.user)

    status = request.GET.get("status")
    q = request.GET.get("q", "").strip()
    if status:
        subs = subs.filter(status=status)
    if q:
        subs = subs.filter(Q(name__icontains=q) | Q(email__icontains=q))

    stats = EmailSubscriber.objects.filter(user=request.user).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        unsubscribed=Count("id", filter=Q(status="unsubscribed")),
    )

    return render(request, "emails/subscriber_list.html", {
        "subscribers": subs[:200],
        "stats": stats,
        "current_status": status,
        "current_q": q,
        "page_title": "Subscribers",
    })


@login_required
def subscriber_add(request):
    """Add a subscriber manually."""
    limits = get_plan_limits(request.user.profile.plan)
    max_subs = limits.get("email_subscribers", 50)
    current_count = EmailSubscriber.objects.filter(user=request.user).count()
    if current_count >= max_subs:
        messages.warning(request, f"Your plan allows up to {max_subs:,} subscribers. Upgrade for more.")
        return redirect("billing:pricing")

    if request.method == "POST":
        form = EmailSubscriberForm(request.POST)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.user = request.user
            sub.save()
            messages.success(request, f"Subscriber '{sub.email}' added!")
            return redirect("emails:subscribers")
    else:
        form = EmailSubscriberForm()

    return render(request, "emails/subscriber_form.html", {
        "form": form,
        "page_title": "Add Subscriber",
    })


# ────────────────────────────────────────────────────────────────────
# Lists
# ────────────────────────────────────────────────────────────────────


@login_required
def list_index(request):
    """All email lists."""
    lists = EmailList.objects.filter(user=request.user).annotate(
        active_count=Count("subscribers", filter=Q(subscribers__status="active"))
    )

    return render(request, "emails/list_index.html", {
        "lists": lists,
        "page_title": "Email Lists",
    })


@login_required
def list_create(request):
    """Create an email list."""
    limits = get_plan_limits(request.user.profile.plan)
    max_lists = limits.get("email_lists", 1)
    current_count = EmailList.objects.filter(user=request.user).count()
    if current_count >= max_lists:
        messages.warning(request, f"Your plan allows up to {max_lists} email list(s). Upgrade for more.")
        return redirect("billing:pricing")

    if request.method == "POST":
        form = EmailListForm(request.POST)
        if form.is_valid():
            email_list = form.save(commit=False)
            email_list.user = request.user
            email_list.save()
            messages.success(request, f"List '{email_list.name}' created!")
            return redirect("emails:lists")
    else:
        form = EmailListForm()

    return render(request, "emails/list_form.html", {
        "form": form,
        "page_title": "Create List",
        "is_edit": False,
    })


@login_required
def list_detail(request, list_id):
    """View list with its subscribers."""
    email_list = get_object_or_404(EmailList, pk=list_id, user=request.user)
    if email_list.is_smart:
        subscribers = email_list.get_smart_queryset()[:200]
    else:
        subscribers = email_list.subscribers.filter(status=EmailSubscriber.Status.ACTIVE)[:200]

    return render(request, "emails/list_detail.html", {
        "email_list": email_list,
        "subscribers": subscribers,
        "page_title": email_list.name,
    })


@login_required
def list_edit(request, list_id):
    """Edit an email list."""
    email_list = get_object_or_404(EmailList, pk=list_id, user=request.user)
    if request.method == "POST":
        form = EmailListForm(request.POST, instance=email_list)
        if form.is_valid():
            form.save()
            messages.success(request, "List updated.")
            return redirect("emails:list_detail", list_id=email_list.pk)
    else:
        form = EmailListForm(instance=email_list)

    return render(request, "emails/list_form.html", {
        "form": form,
        "email_list": email_list,
        "page_title": "Edit List",
        "is_edit": True,
    })


# ────────────────────────────────────────────────────────────────────
# Campaigns
# ────────────────────────────────────────────────────────────────────


@login_required
def campaign_list(request):
    """All campaigns."""
    campaigns = EmailCampaign.objects.filter(user=request.user)

    status = request.GET.get("status")
    if status:
        campaigns = campaigns.filter(status=status)

    stats = EmailCampaign.objects.filter(user=request.user).aggregate(
        total=Count("id"),
        sent=Count("id", filter=Q(status="sent")),
        total_sent_emails=Sum("total_sent"),
        total_opened_emails=Sum("total_opened"),
    )

    return render(request, "emails/campaign_list.html", {
        "campaigns": campaigns[:50],
        "stats": stats,
        "current_status": status,
        "page_title": "Campaigns",
    })


@login_required
def campaign_create(request):
    """Create a new campaign."""
    limits = get_plan_limits(request.user.profile.plan)
    max_campaigns = limits.get("email_campaigns_per_month", 2)
    current_month_count = EmailCampaign.objects.filter(
        user=request.user,
        created_at__month=timezone.now().month,
        created_at__year=timezone.now().year,
    ).count()
    if current_month_count >= max_campaigns:
        messages.warning(request, f"Your plan allows up to {max_campaigns} campaigns per month. Upgrade for more.")
        return redirect("billing:pricing")

    if request.method == "POST":
        form = EmailCampaignForm(request.POST, user=request.user)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.user = request.user
            campaign.save()
            messages.success(request, f"Campaign '{campaign.name}' created!")
            return redirect("emails:campaign_detail", campaign_id=campaign.pk)
    else:
        form = EmailCampaignForm(user=request.user)

    return render(request, "emails/campaign_form.html", {
        "form": form,
        "page_title": "Create Campaign",
        "is_edit": False,
    })


@login_required
def campaign_detail(request, campaign_id):
    """Campaign overview with metrics."""
    campaign = get_object_or_404(EmailCampaign, pk=campaign_id, user=request.user)

    return render(request, "emails/campaign_detail.html", {
        "campaign": campaign,
        "page_title": campaign.name,
    })


@login_required
def campaign_edit(request, campaign_id):
    """Edit a draft campaign."""
    campaign = get_object_or_404(EmailCampaign, pk=campaign_id, user=request.user)
    if campaign.status not in (EmailCampaign.Status.DRAFT, EmailCampaign.Status.SCHEDULED):
        messages.error(request, "Only draft or scheduled campaigns can be edited.")
        return redirect("emails:campaign_detail", campaign_id=campaign.pk)

    if request.method == "POST":
        form = EmailCampaignForm(request.POST, instance=campaign, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Campaign updated.")
            return redirect("emails:campaign_detail", campaign_id=campaign.pk)
    else:
        form = EmailCampaignForm(instance=campaign, user=request.user)

    return render(request, "emails/campaign_form.html", {
        "form": form,
        "campaign": campaign,
        "page_title": "Edit Campaign",
        "is_edit": True,
    })


# ────────────────────────────────────────────────────────────────────
# Sequences
# ────────────────────────────────────────────────────────────────────


@login_required
def sequence_list(request):
    """All email sequences."""
    sequences = EmailSequence.objects.filter(user=request.user).annotate(
        step_count=Count("steps"),
        enrollment_count=Count("enrollments"),
    )

    return render(request, "emails/sequence_list.html", {
        "sequences": sequences,
        "page_title": "Email Sequences",
    })


@login_required
def sequence_detail(request, sequence_id):
    """Sequence with steps and enrollments."""
    sequence = get_object_or_404(EmailSequence, pk=sequence_id, user=request.user)
    steps = sequence.steps.all()
    enrollments = sequence.enrollments.select_related("subscriber")[:50]

    return render(request, "emails/sequence_detail.html", {
        "sequence": sequence,
        "steps": steps,
        "enrollments": enrollments,
        "page_title": sequence.name,
    })


# ────────────────────────────────────────────────────────────────────
# Email marketing dashboard
# ────────────────────────────────────────────────────────────────────


@login_required
def email_dashboard(request):
    """Email marketing overview."""
    subscriber_stats = EmailSubscriber.objects.filter(user=request.user).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
    )

    campaign_stats = EmailCampaign.objects.filter(user=request.user).aggregate(
        total=Count("id"),
        sent=Count("id", filter=Q(status="sent")),
        total_sent_emails=Sum("total_sent"),
        total_opened_emails=Sum("total_opened"),
        total_clicked_emails=Sum("total_clicked"),
    )

    recent_campaigns = EmailCampaign.objects.filter(
        user=request.user
    ).order_by("-created_at")[:5]

    active_sequences = EmailSequence.objects.filter(
        user=request.user, is_active=True
    ).annotate(enrollment_count=Count("enrollments"))[:5]

    list_count = EmailList.objects.filter(user=request.user).count()

    return render(request, "emails/dashboard.html", {
        "subscriber_stats": subscriber_stats,
        "campaign_stats": campaign_stats,
        "recent_campaigns": recent_campaigns,
        "active_sequences": active_sequences,
        "list_count": list_count,
        "page_title": "Email Marketing",
    })
