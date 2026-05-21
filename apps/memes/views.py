import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.memes.pipeline import create_posts_from_adaptation
from apps.memes.relevance import get_meme_prefs, rank_memes_for_user
from apps.memes.tasks import adapt_single_meme
from apps.utils import fire_task

from .forms import MemePreferencesForm
from .models import KenyanEvent, MemeAdaptation, MemePreferences, TrendingMeme

logger = logging.getLogger(__name__)


def _build_meme_value_stats(user):
    """ROI-style stats for the value strip."""
    week_ago = timezone.now() - timedelta(days=7)
    month_ago = timezone.now() - timedelta(days=30)

    adaptations = MemeAdaptation.objects.filter(user=user)
    week_adapted = adaptations.filter(created_at__gte=week_ago).exclude(status=MemeAdaptation.Status.FAILED).count()
    month_adapted = adaptations.filter(created_at__gte=month_ago).exclude(status=MemeAdaptation.Status.FAILED).count()
    published = adaptations.filter(status=MemeAdaptation.Status.PUBLISHED).count()
    pending_alerts = 0
    try:
        from apps.memes.models import TrendAlert
        pending_alerts = TrendAlert.objects.filter(
            user=user,
            status__in=[TrendAlert.Status.DETECTED, TrendAlert.Status.READY],
        ).count()
    except Exception:
        pass

    minutes_saved = month_adapted * 12
    return {
        "week_adapted": week_adapted,
        "month_adapted": month_adapted,
        "published": published,
        "pending_alerts": pending_alerts,
        "minutes_saved": minutes_saved,
    }


# ─── DISCOVER: BROWSE TRENDING MEMES ────────────────────────────────────────

@login_required
def meme_discover(request):
    """Browse trending memes — personalized for the user's industry and prefs."""
    profile = request.user.profile
    prefs = get_meme_prefs(request.user)
    category = request.GET.get("category", "")
    lifecycle = request.GET.get("lifecycle", "")
    sort = request.GET.get("sort", "score")
    topic_hint = request.GET.get("topic", "").strip()

    memes_qs = TrendingMeme.objects.filter(
        lifecycle__in=[
            TrendingMeme.Lifecycle.EMERGING,
            TrendingMeme.Lifecycle.TRENDING,
            TrendingMeme.Lifecycle.PEAKED,
        ],
        expires_at__gt=timezone.now(),
    )

    if prefs.excluded_categories:
        memes_qs = memes_qs.exclude(category__in=prefs.excluded_categories)
    if category:
        memes_qs = memes_qs.filter(category=category)
    if lifecycle:
        memes_qs = memes_qs.filter(lifecycle=lifecycle)

    if sort == "virality":
        memes_qs = memes_qs.order_by("-virality_score")
    elif sort == "safety":
        memes_qs = memes_qs.order_by("-brand_safety_score")
    elif sort == "newest":
        memes_qs = memes_qs.order_by("-detected_at")
    elif sort == "cultural":
        memes_qs = memes_qs.order_by("-cultural_relevance_score")
    else:
        memes_qs = memes_qs.order_by("-virality_score", "-adaptability_score")

    memes_list = list(memes_qs[:60 if sort == "score" else 30])

    if sort == "score":
        ranked = rank_memes_for_user(memes_list, profile, prefs, topic_hint=topic_hint)[:30]
    else:
        from apps.memes.relevance import meme_fit_line
        ranked = [
            {"meme": m, "score": m.overall_score, "fit_line": meme_fit_line(m, profile)}
            for m in memes_list
        ]

    adapted_ids = set(
        MemeAdaptation.objects.filter(user=request.user)
        .exclude(status=MemeAdaptation.Status.FAILED)
        .values_list("trending_meme_id", flat=True)
    )

    today = timezone.now().date()
    upcoming_events = KenyanEvent.objects.filter(
        date__gte=today,
        date__lte=today + timedelta(days=14),
    ).order_by("date")[:5]

    week_ago = timezone.now() - timedelta(days=7)
    used_this_week = MemeAdaptation.objects.filter(
        user=request.user, created_at__gte=week_ago,
    ).exclude(status=MemeAdaptation.Status.FAILED).count()
    quota = {
        "used": used_this_week,
        "limit": prefs.max_memes_per_week,
        "remaining": max(0, prefs.max_memes_per_week - used_this_week),
        "percent": int(
            (used_this_week / prefs.max_memes_per_week * 100)
            if prefs.max_memes_per_week else 0
        ),
        "risk_tolerance": prefs.get_risk_tolerance_display(),
    }

    last_discovered = (
        TrendingMeme.objects.filter(
            lifecycle__in=[
                TrendingMeme.Lifecycle.EMERGING,
                TrendingMeme.Lifecycle.TRENDING,
                TrendingMeme.Lifecycle.PEAKED,
            ],
        )
        .order_by("-detected_at")
        .values_list("detected_at", flat=True)
        .first()
    )

    return render(request, "memes/discover.html", {
        "ranked_memes": ranked,
        "adapted_ids": adapted_ids,
        "upcoming_events": upcoming_events,
        "current_category": category,
        "current_lifecycle": lifecycle,
        "current_sort": sort,
        "categories": TrendingMeme.Category.choices,
        "quota": quota,
        "last_discovered": last_discovered,
        "topic_hint": topic_hint,
        "value_stats": _build_meme_value_stats(request.user),
        "company_name": profile.company_name or "your business",
        "page_title": "Memes & Trends",
    })


# ─── MEME DETAIL ────────────────────────────────────────────────────────────

@login_required
def meme_detail(request, meme_id):
    """View a single meme's details and any existing adaptations."""
    meme = get_object_or_404(TrendingMeme, id=meme_id)
    profile = request.user.profile

    user_adaptations = MemeAdaptation.objects.filter(
        user=request.user, trending_meme=meme,
    ).order_by("-created_at")

    from apps.memes.relevance import meme_fit_line

    return render(request, "memes/detail.html", {
        "meme": meme,
        "user_adaptations": user_adaptations,
        "fit_line": meme_fit_line(meme, profile),
        "page_title": meme.title,
    })


# ─── ADAPT: TRIGGER AI ADAPTATION ───────────────────────────────────────────

@login_required
@require_POST
def meme_adapt(request, meme_id):
    """Trigger AI adaptation of a meme for the current user's brand."""
    meme = get_object_or_404(TrendingMeme, id=meme_id)

    if not meme.is_usable:
        messages.warning(
            request,
            f"\"{meme.title}\" is no longer usable — it's "
            f"{meme.get_lifecycle_display().lower()}. Pick a fresher trend.",
        )
        return redirect("memes:detail", meme_id=meme.id)

    existing = MemeAdaptation.objects.filter(
        user=request.user, trending_meme=meme,
    ).exclude(status=MemeAdaptation.Status.FAILED).first()
    if existing:
        messages.info(request, "You already have an adaptation of this meme.")
        return redirect("memes:detail", meme_id=meme.id)

    prefs = get_meme_prefs(request.user)
    safety_floor = {
        MemePreferences.RiskTolerance.CONSERVATIVE: 75,
        MemePreferences.RiskTolerance.MODERATE: 50,
        MemePreferences.RiskTolerance.BOLD: 25,
    }.get(prefs.risk_tolerance, 50)
    if meme.brand_safety_score < safety_floor:
        messages.warning(
            request,
            f"This meme's brand-safety score ({meme.brand_safety_score}) is below "
            f"your '{prefs.get_risk_tolerance_display()}' threshold ({safety_floor}).",
        )
        return redirect("memes:detail", meme_id=meme.id)

    if prefs.excluded_categories and meme.category in prefs.excluded_categories:
        messages.warning(
            request,
            f"You've excluded '{meme.get_category_display()}' memes in settings.",
        )
        return redirect("memes:detail", meme_id=meme.id)

    week_ago = timezone.now() - timedelta(days=7)
    this_week = MemeAdaptation.objects.filter(
        user=request.user, created_at__gte=week_ago,
    ).exclude(status=MemeAdaptation.Status.FAILED).count()
    if this_week >= prefs.max_memes_per_week:
        messages.warning(
            request,
            f"You've reached your weekly meme limit ({prefs.max_memes_per_week}).",
        )
        return redirect("memes:detail", meme_id=meme.id)

    MemeAdaptation.objects.filter(
        user=request.user, trending_meme=meme, status=MemeAdaptation.Status.FAILED,
    ).delete()

    fire_task(adapt_single_meme, str(meme.id), request.user.id)
    messages.success(
        request,
        f"Adapting \"{meme.title}\" for your brand — check My Queue in a moment!",
    )
    return redirect("memes:queue")


@login_required
@require_POST
def meme_retry(request, adaptation_id):
    """Retry a failed adaptation."""
    adaptation = get_object_or_404(
        MemeAdaptation, id=adaptation_id, user=request.user,
        status=MemeAdaptation.Status.FAILED,
    )
    meme = adaptation.trending_meme
    adaptation.delete()
    fire_task(adapt_single_meme, str(meme.id), request.user.id)
    messages.success(request, f"Retrying adaptation for \"{meme.title}\"...")
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

    total = adaptations.count()
    drafts = adaptations.filter(status=MemeAdaptation.Status.DRAFT).count()
    approved = adaptations.filter(status=MemeAdaptation.Status.APPROVED).count()
    published = adaptations.filter(status=MemeAdaptation.Status.PUBLISHED).count()
    failed = adaptations.filter(status=MemeAdaptation.Status.FAILED).count()

    return render(request, "memes/queue.html", {
        "adaptations": adaptations[:50],
        "total": total,
        "drafts": drafts,
        "approved": approved,
        "published": published,
        "failed": failed,
        "current_status": status_filter,
        "value_stats": _build_meme_value_stats(request.user),
        "page_title": "Meme Queue",
    })


# ─── APPROVE / REJECT / PUBLISH ADAPTATION ──────────────────────────────────

@login_required
@require_POST
def meme_approve(request, adaptation_id):
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
    """Convert an approved adaptation into Post row(s) in the content pipeline."""
    adaptation = get_object_or_404(
        MemeAdaptation, id=adaptation_id, user=request.user,
    )

    if adaptation.status != MemeAdaptation.Status.APPROVED:
        messages.warning(request, "Only approved adaptations can be sent to the content pipeline.")
        return redirect("memes:queue")

    created_posts, skipped = create_posts_from_adaptation(adaptation)

    if not created_posts:
        messages.warning(
            request,
            "No matching connected accounts for the targeted platforms. Connect one first.",
        )
        return redirect("memes:queue")

    success = (
        f"Sent to Studio as {len(created_posts)} {'posts' if len(created_posts) != 1 else 'post'} "
        f"({', '.join(p.platform for p in created_posts)})."
    )
    if skipped:
        success += f" Skipped: {', '.join(skipped)} (no connected account)."
    if any(p.media_prompt for p in created_posts):
        success += " Visual memes are generating in the background."
    messages.success(request, success)
    return redirect("content:post_detail", post_id=created_posts[0].id)


# ─── SETTINGS ────────────────────────────────────────────────────────────────

@login_required
def meme_settings(request):
    prefs = get_meme_prefs(request.user)

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
    from apps.memes.models import TrendAlert

    status_filter = request.GET.get("status", "")
    qs = (
        TrendAlert.objects
        .filter(user=request.user)
        .select_related("content_seed", "trending_meme")
        .order_by("-detected_at")
    )

    if status_filter:
        qs = qs.filter(status=status_filter)

    return render(request, "memes/trend_alerts.html", {
        "alerts": qs[:50],
        "status_filter": status_filter,
        "status_choices": TrendAlert.Status.choices,
        "value_stats": _build_meme_value_stats(request.user),
    })


@login_required
@require_POST
def trend_alert_action(request, pk):
    from apps.memes.models import TrendAlert
    from apps.memes.tasks import generate_trend_ride_content

    alert = get_object_or_404(TrendAlert, pk=pk, user=request.user)
    action = request.POST.get("action")

    if action == "approve" and alert.status in (
        TrendAlert.Status.DETECTED, TrendAlert.Status.READY,
    ):
        alert.status = TrendAlert.Status.APPROVED
        alert.approved_at = timezone.now()
        alert.save(update_fields=["status", "approved_at", "updated_at"])
        if not alert.content_seed:
            generate_trend_ride_content.delay(str(alert.pk))
        messages.success(request, f"Trend '{alert.trend_topic}' approved — content is being generated!")
    elif action == "dismiss" and alert.status in (
        TrendAlert.Status.DETECTED, TrendAlert.Status.READY,
    ):
        alert.status = TrendAlert.Status.DISMISSED
        alert.save(update_fields=["status", "updated_at"])
        messages.info(request, "Trend alert dismissed.")

    return redirect("memes:trend_alerts")


# ─── HTMX PARTIALS ──────────────────────────────────────────────────────────

@login_required
def meme_card(request, meme_id):
    meme = get_object_or_404(TrendingMeme, id=meme_id)
    adapted = MemeAdaptation.objects.filter(
        user=request.user, trending_meme=meme,
    ).exclude(status=MemeAdaptation.Status.FAILED).exists()

    from apps.memes.relevance import meme_fit_line

    return render(request, "memes/partials/meme_card.html", {
        "meme": meme,
        "adapted": adapted,
        "fit_line": meme_fit_line(meme, request.user.profile),
    })
