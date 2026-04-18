import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.memes.tasks import adapt_single_meme
from apps.utils import fire_task

from .forms import MemePreferencesForm
from .models import KenyanEvent, MemeAdaptation, MemePreferences, TrendingMeme

logger = logging.getLogger(__name__)


# ─── DISCOVER: BROWSE TRENDING MEMES ────────────────────────────────────────

@login_required
def meme_discover(request):
    """Browse trending memes — the main meme intelligence page."""
    category = request.GET.get("category", "")
    lifecycle = request.GET.get("lifecycle", "")
    sort = request.GET.get("sort", "score")

    memes = TrendingMeme.objects.filter(
        lifecycle__in=[
            TrendingMeme.Lifecycle.EMERGING,
            TrendingMeme.Lifecycle.TRENDING,
            TrendingMeme.Lifecycle.PEAKED,
        ],
    )

    if category:
        memes = memes.filter(category=category)
    if lifecycle:
        memes = memes.filter(lifecycle=lifecycle)

    # Sort options
    if sort == "virality":
        memes = memes.order_by("-virality_score")
    elif sort == "safety":
        memes = memes.order_by("-brand_safety_score")
    elif sort == "newest":
        memes = memes.order_by("-detected_at")
    else:
        # Default: combined score (virality + safety + adaptability)
        memes = memes.order_by("-virality_score", "-adaptability_score")

    memes = memes[:30]

    # Get user's existing adaptations for badge indicators
    adapted_ids = set(
        MemeAdaptation.objects.filter(user=request.user)
        .values_list("trending_meme_id", flat=True)
    )

    # Upcoming events for context panel
    today = timezone.now().date()
    upcoming_events = KenyanEvent.objects.filter(
        date__gte=today,
        date__lte=today + timezone.timedelta(days=14),
    ).order_by("date")[:5]

    return render(request, "memes/discover.html", {
        "memes": memes,
        "adapted_ids": adapted_ids,
        "upcoming_events": upcoming_events,
        "current_category": category,
        "current_lifecycle": lifecycle,
        "current_sort": sort,
        "categories": TrendingMeme.Category.choices,
        "page_title": "Meme Intelligence",
    })


# ─── MEME DETAIL ────────────────────────────────────────────────────────────

@login_required
def meme_detail(request, meme_id):
    """View a single meme's details and any existing adaptations."""
    meme = get_object_or_404(TrendingMeme, id=meme_id)

    user_adaptations = MemeAdaptation.objects.filter(
        user=request.user, trending_meme=meme,
    ).order_by("-created_at")

    return render(request, "memes/detail.html", {
        "meme": meme,
        "user_adaptations": user_adaptations,
        "page_title": meme.title,
    })


# ─── ADAPT: TRIGGER AI ADAPTATION ───────────────────────────────────────────

@login_required
@require_POST
def meme_adapt(request, meme_id):
    """Trigger AI adaptation of a meme for the current user's brand."""
    meme = get_object_or_404(TrendingMeme, id=meme_id)

    # Check if already adapted
    existing = MemeAdaptation.objects.filter(
        user=request.user, trending_meme=meme,
    ).first()
    if existing:
        messages.info(request, "You already have an adaptation of this meme.")
        return redirect("memes:detail", meme_id=meme.id)

    # Check weekly quota
    prefs, _ = MemePreferences.objects.get_or_create(user=request.user)
    week_ago = timezone.now() - timezone.timedelta(days=7)
    this_week = MemeAdaptation.objects.filter(
        user=request.user, created_at__gte=week_ago,
    ).count()

    if this_week >= prefs.max_memes_per_week:
        messages.warning(
            request,
            f"You've reached your weekly meme limit ({prefs.max_memes_per_week}). "
            "Adjust in settings or wait for the weekly reset.",
        )
        return redirect("memes:detail", meme_id=meme.id)

    # Fire the adaptation task
    fire_task(adapt_single_meme, args=[str(meme.id), request.user.id])
    messages.success(request, f"Adapting \"{meme.title}\" for your brand — check back in a moment!")

    return redirect("memes:queue")


# ─── QUEUE: USER'S ADAPTATIONS FOR REVIEW ───────────────────────────────────

@login_required
def meme_queue(request):
    """View all meme adaptations for the current user."""
    status_filter = request.GET.get("status", "")

    adaptations = MemeAdaptation.objects.filter(
        user=request.user,
    ).select_related("trending_meme").order_by("-created_at")

    if status_filter:
        adaptations = adaptations.filter(status=status_filter)

    # Stats
    total = adaptations.count()
    drafts = adaptations.filter(status=MemeAdaptation.Status.DRAFT).count()
    approved = adaptations.filter(status=MemeAdaptation.Status.APPROVED).count()
    published = adaptations.filter(status=MemeAdaptation.Status.PUBLISHED).count()

    return render(request, "memes/queue.html", {
        "adaptations": adaptations[:50],
        "total": total,
        "drafts": drafts,
        "approved": approved,
        "published": published,
        "current_status": status_filter,
        "page_title": "Meme Queue",
    })


# ─── APPROVE / REJECT / PUBLISH ADAPTATION ──────────────────────────────────

@login_required
@require_POST
def meme_approve(request, adaptation_id):
    """Approve an adaptation — ready for publishing."""
    adaptation = get_object_or_404(
        MemeAdaptation, id=adaptation_id, user=request.user,
    )
    adaptation.status = MemeAdaptation.Status.APPROVED
    adaptation.save(update_fields=["status", "updated_at"])
    messages.success(request, "Meme adaptation approved!")
    return redirect("memes:queue")


@login_required
@require_POST
def meme_reject(request, adaptation_id):
    """Reject an adaptation."""
    adaptation = get_object_or_404(
        MemeAdaptation, id=adaptation_id, user=request.user,
    )
    adaptation.status = MemeAdaptation.Status.REJECTED
    adaptation.save(update_fields=["status", "updated_at"])
    messages.info(request, "Meme adaptation rejected.")
    return redirect("memes:queue")


@login_required
@require_POST
def meme_to_post(request, adaptation_id):
    """Convert an approved adaptation into a Post in the content pipeline."""
    from apps.content.models import Post

    adaptation = get_object_or_404(
        MemeAdaptation, id=adaptation_id, user=request.user,
    )

    if adaptation.status != MemeAdaptation.Status.APPROVED:
        messages.warning(request, "Only approved adaptations can be sent to the content pipeline.")
        return redirect("memes:queue")

    # Determine platform from targets
    platform = "twitter"
    if adaptation.platform_targets:
        platform = adaptation.platform_targets[0]

    # Create the Post — combine adapted text and caption
    content = adaptation.adapted_text
    if adaptation.adapted_caption:
        content += f"\n\n{adaptation.adapted_caption}"

    post = Post.objects.create(
        user=request.user,
        content=content,
        platform=platform,
        content_type="original",
        status="pending_approval",
    )

    # Link the adaptation to the post
    adaptation.post = post
    adaptation.status = MemeAdaptation.Status.PUBLISHED
    adaptation.save(update_fields=["post", "status", "updated_at"])

    messages.success(request, f"Meme sent to content pipeline as a {platform} post!")
    return redirect("content:post_detail", post_id=post.id)


# ─── SETTINGS ────────────────────────────────────────────────────────────────

@login_required
def meme_settings(request):
    """Meme preference settings."""
    prefs, created = MemePreferences.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = MemePreferencesForm(request.POST, instance=prefs)
        if form.is_valid():
            form.save()
            messages.success(request, "Meme preferences updated!")
            return redirect("memes:settings")
    else:
        form = MemePreferencesForm(instance=prefs)

    return render(request, "memes/settings.html", {
        "form": form,
        "prefs": prefs,
        "page_title": "Meme Settings",
    })


# ─── TREND ALERTS ────────────────────────────────────────────────────────────


@login_required
def trend_alerts(request):
    """View AI-detected trend alerts with approve/dismiss actions."""
    from apps.memes.models import TrendAlert

    status_filter = request.GET.get("status", "")
    qs = (
        TrendAlert.objects
        .filter(user=request.user)
        .select_related("content_seed")
        .order_by("-detected_at")
    )

    if status_filter:
        qs = qs.filter(status=status_filter)

    return render(request, "memes/trend_alerts.html", {
        "alerts": qs[:50],
        "status_filter": status_filter,
        "status_choices": TrendAlert.Status.choices,
    })


@login_required
@require_POST
def trend_alert_action(request, pk):
    """Approve or dismiss a trend alert."""
    from apps.memes.models import TrendAlert
    from apps.memes.tasks import generate_trend_ride_content

    alert = get_object_or_404(TrendAlert, pk=pk, user=request.user)
    action = request.POST.get("action")

    if action == "approve" and alert.status in ("detected", "ready"):
        alert.status = "approved"
        alert.save(update_fields=["status", "updated_at"])
        if not alert.content_seed:
            generate_trend_ride_content.delay(str(alert.pk))
        messages.success(request, f"Trend '{alert.trend_topic}' approved — content is being generated!")
    elif action == "dismiss" and alert.status in ("detected", "ready"):
        alert.status = "dismissed"
        alert.save(update_fields=["status", "updated_at"])
        messages.info(request, "Trend alert dismissed.")

    return redirect("memes:trend_alerts")


# ─── HTMX PARTIALS ──────────────────────────────────────────────────────────

@login_required
def meme_card(request, meme_id):
    """HTMX partial — returns a single meme card (for refresh after adapt)."""
    meme = get_object_or_404(TrendingMeme, id=meme_id)
    adapted = MemeAdaptation.objects.filter(
        user=request.user, trending_meme=meme,
    ).exists()

    return render(request, "memes/partials/meme_card.html", {
        "meme": meme,
        "adapted": adapted,
    })
