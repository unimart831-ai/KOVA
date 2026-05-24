from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.campaigns.forms import CampaignForm
from apps.campaigns.models import Campaign, CampaignEmail, CampaignNote, CampaignSeed
from apps.content.models import ContentSeed, Post


@login_required
def campaign_list(request):
    """Redirect legacy campaigns list to unified Voice Campaign hub."""
    return redirect("content:voice_campaign")


@login_required
def campaign_create(request):
    """Create a new campaign."""
    from apps.billing.models import get_user_plan_limits
    from apps.billing.plan_limit_ui import plan_limit_redirect

    limits = get_user_plan_limits(request.user)
    max_campaigns = limits.get("max_campaigns", 3)
    current_count = Campaign.objects.filter(user=request.user).count()

    if current_count >= max_campaigns and max_campaigns < 999999:
        return plan_limit_redirect(
            request,
            f"You've reached your plan limit of {max_campaigns} campaigns. Upgrade for more.",
            "content:voice_campaign",
        )

    if request.method == "POST":
        form = CampaignForm(request.POST, user=request.user)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.user = request.user
            campaign.save()
            CampaignNote.objects.create(
                campaign=campaign, user=request.user,
                content="Campaign created", note_type=CampaignNote.NoteType.STATUS_CHANGE,
            )
            messages.success(request, f'Campaign "{campaign.name}" created.')
            return redirect("campaigns:detail", pk=campaign.pk)
    else:
        form = CampaignForm(user=request.user)

    PLATFORM_CHOICES = [
        ("instagram", "Instagram"), ("twitter", "Twitter"), ("linkedin", "LinkedIn"),
        ("facebook", "Facebook"), ("tiktok", "TikTok"), ("youtube", "YouTube"),
    ]

    return render(request, "campaigns/campaign_form.html", {
        "form": form, "editing": False,
        "platform_choices": PLATFORM_CHOICES,
        "current_platforms": [],
    })


@login_required
def campaign_detail(request, pk):
    """Campaign dashboard — performance, linked content, activity."""
    campaign = get_object_or_404(Campaign, pk=pk, user=request.user)

    # Linked seeds with their posts
    campaign_seeds = (
        CampaignSeed.objects.filter(campaign=campaign)
        .select_related("seed")
        .prefetch_related("seed__posts")
        .order_by("sequence_order")
    )

    # Linked email campaigns
    campaign_emails = (
        CampaignEmail.objects.filter(campaign=campaign)
        .select_related("email_campaign")
        .order_by("sequence_order")
    )

    # Activity log
    notes = campaign.notes.select_related("user").order_by("-created_at")[:20]

    # Performance metrics from linked posts
    all_post_ids = []
    for cs in campaign_seeds:
        all_post_ids.extend(cs.seed.posts.values_list("id", flat=True))

    posts_qs = Post.objects.filter(id__in=all_post_ids)
    total_posts = posts_qs.count()
    published = posts_qs.filter(status="published").count()
    scheduled = posts_qs.filter(status="scheduled").count()
    draft = posts_qs.filter(status__in=["draft", "pending_approval", "approved"]).count()

    # Conversion metrics via UTM
    from apps.analytics.models import Conversion
    conversions = Conversion.objects.filter(
        user=request.user, utm_campaign=campaign.utm_campaign_tag
    )
    total_conversions = conversions.count()
    total_revenue = conversions.aggregate(rev=Sum("revenue"))["rev"] or 0

    # Lead count from UTM
    from apps.leads.models import Lead
    campaign_leads = Lead.objects.filter(
        user=request.user,
        metadata__utm_campaign=campaign.utm_campaign_tag,
    ).count()

    # Email metrics
    email_sent = sum(ce.email_campaign.total_sent for ce in campaign_emails)
    email_opened = sum(ce.email_campaign.total_opened for ce in campaign_emails)

    # Available seeds/emails for linking
    available_seeds = (
        ContentSeed.objects.filter(user=request.user)
        .exclude(id__in=campaign.content_seeds.values_list("id", flat=True))
        .order_by("-created_at")[:50]
    )

    from apps.emails.models import EmailCampaign
    available_emails = (
        EmailCampaign.objects.filter(user=request.user)
        .exclude(id__in=campaign.email_campaigns.values_list("id", flat=True))
        .order_by("-created_at")[:50]
    )

    return render(request, "campaigns/campaign_detail.html", {
        "campaign": campaign,
        "campaign_seeds": campaign_seeds,
        "campaign_emails": campaign_emails,
        "notes": notes,
        "available_seeds": available_seeds,
        "available_emails": available_emails,
        "metrics": {
            "total_posts": total_posts,
            "published": published,
            "scheduled": scheduled,
            "draft": draft,
            "conversions": total_conversions,
            "revenue": total_revenue,
            "leads": campaign_leads,
            "email_sent": email_sent,
            "email_opened": email_opened,
        },
    })


@login_required
def campaign_edit(request, pk):
    """Edit a campaign (draft/pending only)."""
    campaign = get_object_or_404(Campaign, pk=pk, user=request.user)
    if not campaign.is_editable:
        messages.error(request, "Active or completed campaigns cannot be edited.")
        return redirect("campaigns:detail", pk=pk)

    if request.method == "POST":
        form = CampaignForm(request.POST, instance=campaign, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Campaign updated.")
            return redirect("campaigns:detail", pk=pk)
    else:
        form = CampaignForm(instance=campaign, user=request.user)

    PLATFORM_CHOICES = [
        ("instagram", "Instagram"), ("twitter", "Twitter"), ("linkedin", "LinkedIn"),
        ("facebook", "Facebook"), ("tiktok", "TikTok"), ("youtube", "YouTube"),
    ]

    return render(request, "campaigns/campaign_form.html", {
        "form": form, "editing": True, "campaign": campaign,
        "platform_choices": PLATFORM_CHOICES,
        "current_platforms": campaign.target_platforms or [],
    })


@login_required
def campaign_status(request, pk):
    """Change campaign status with validation."""
    if request.method != "POST":
        return redirect("campaigns:detail", pk=pk)

    campaign = get_object_or_404(Campaign, pk=pk, user=request.user)
    new_status = request.POST.get("status")

    # Valid transitions
    valid = {
        "draft": ["pending_approval", "cancelled"],
        "pending_approval": ["approved", "draft", "cancelled"],
        "approved": ["active", "draft", "cancelled"],
        "active": ["paused", "completed", "cancelled"],
        "paused": ["active", "cancelled", "completed"],
    }
    allowed = valid.get(campaign.status, [])

    if new_status not in allowed:
        messages.error(request, f"Cannot change from {campaign.get_status_display()} to {new_status}.")
        return redirect("campaigns:detail", pk=pk)

    old_status = campaign.get_status_display()
    campaign.status = new_status
    campaign.save(update_fields=["status", "updated_at"])

    # If activating, push UTM tag to all linked posts
    if new_status == "active":
        _apply_utm_to_posts(campaign)

    new_display = campaign.get_status_display()
    CampaignNote.objects.create(
        campaign=campaign, user=request.user,
        content=f"Status changed: {old_status} → {new_display}",
        note_type=CampaignNote.NoteType.STATUS_CHANGE,
    )
    messages.success(request, f"Campaign is now {new_display}.")
    return redirect("campaigns:detail", pk=pk)


@login_required
def campaign_add_seed(request, pk):
    """Link a ContentSeed to a campaign."""
    if request.method != "POST":
        return redirect("campaigns:detail", pk=pk)

    campaign = get_object_or_404(Campaign, pk=pk, user=request.user)
    seed_id = request.POST.get("seed_id")
    if not seed_id:
        return redirect("campaigns:detail", pk=pk)

    seed = get_object_or_404(ContentSeed, pk=seed_id, user=request.user)

    if not CampaignSeed.objects.filter(campaign=campaign, seed=seed).exists():
        max_order = campaign.campaign_seeds.count()
        CampaignSeed.objects.create(
            campaign=campaign, seed=seed,
            role=request.POST.get("role", "primary"),
            sequence_order=max_order,
        )
        # Apply UTM if campaign is active
        if campaign.status == Campaign.Status.ACTIVE:
            seed.posts.filter(utm_campaign="").update(utm_campaign=campaign.utm_campaign_tag)

        CampaignNote.objects.create(
            campaign=campaign, user=request.user,
            content=f'Content added: "{seed.idea[:50]}"',
            note_type=CampaignNote.NoteType.CONTENT_ADDED,
        )
        messages.success(request, "Content linked to campaign.")

    return redirect("campaigns:detail", pk=pk)


@login_required
def campaign_remove_seed(request, pk, seed_pk):
    """Remove a seed from a campaign."""
    if request.method != "POST":
        return redirect("campaigns:detail", pk=pk)
    campaign = get_object_or_404(Campaign, pk=pk, user=request.user)
    CampaignSeed.objects.filter(campaign=campaign, seed_id=seed_pk).delete()
    messages.success(request, "Content removed from campaign.")
    return redirect("campaigns:detail", pk=pk)


@login_required
def campaign_add_email(request, pk):
    """Link an EmailCampaign to a campaign."""
    if request.method != "POST":
        return redirect("campaigns:detail", pk=pk)

    campaign = get_object_or_404(Campaign, pk=pk, user=request.user)
    email_id = request.POST.get("email_id")
    if not email_id:
        return redirect("campaigns:detail", pk=pk)

    from apps.emails.models import EmailCampaign
    email_campaign = get_object_or_404(EmailCampaign, pk=email_id, user=request.user)

    if not CampaignEmail.objects.filter(campaign=campaign, email_campaign=email_campaign).exists():
        max_order = campaign.campaign_emails.count()
        CampaignEmail.objects.create(
            campaign=campaign, email_campaign=email_campaign,
            role=request.POST.get("role", "announcement"),
            sequence_order=max_order,
        )
        CampaignNote.objects.create(
            campaign=campaign, user=request.user,
            content=f'Email campaign linked: "{email_campaign.name}"',
            note_type=CampaignNote.NoteType.CONTENT_ADDED,
        )
        messages.success(request, "Email campaign linked.")

    return redirect("campaigns:detail", pk=pk)


@login_required
def campaign_remove_email(request, pk, email_pk):
    """Remove an email campaign from a campaign."""
    if request.method != "POST":
        return redirect("campaigns:detail", pk=pk)
    campaign = get_object_or_404(Campaign, pk=pk, user=request.user)
    CampaignEmail.objects.filter(campaign=campaign, email_campaign_id=email_pk).delete()
    messages.success(request, "Email campaign removed.")
    return redirect("campaigns:detail", pk=pk)


@login_required
def campaign_add_note(request, pk):
    """Add a comment to a campaign."""
    if request.method != "POST":
        return redirect("campaigns:detail", pk=pk)

    campaign = get_object_or_404(Campaign, pk=pk, user=request.user)
    content = request.POST.get("content", "").strip()
    if content:
        CampaignNote.objects.create(
            campaign=campaign, user=request.user, content=content,
            note_type=CampaignNote.NoteType.COMMENT,
        )
    return redirect("campaigns:detail", pk=pk)


@login_required
def campaign_delete(request, pk):
    """Delete a campaign (draft only)."""
    if request.method != "POST":
        return redirect("campaigns:detail", pk=pk)

    campaign = get_object_or_404(Campaign, pk=pk, user=request.user)
    if campaign.status not in (Campaign.Status.DRAFT, Campaign.Status.CANCELLED):
        messages.error(request, "Only draft or cancelled campaigns can be deleted.")
        return redirect("campaigns:detail", pk=pk)

    campaign.delete()
    messages.success(request, "Campaign deleted.")
    return redirect("campaigns:list")


def _apply_utm_to_posts(campaign):
    """Push campaign UTM tag to all linked posts that don't have one."""
    for cs in campaign.campaign_seeds.select_related("seed"):
        cs.seed.posts.filter(utm_campaign="").update(utm_campaign=campaign.utm_campaign_tag)


@login_required
def campaign_ai_build(request):
    """Legacy endpoint — redirect to Voice Campaign hub."""
    return redirect("content:voice_campaign")
