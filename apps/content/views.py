import json
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST, require_http_methods
from django_ratelimit.decorators import ratelimit

from apps.content.forms import ContentSeedForm, PostEditForm
from apps.content.models import ContentSeed, Post
from apps.content.tasks import generate_from_seed
from apps.teams.permissions import can_approve_post, can_edit_post, get_teammate_ids
from apps.utils import fire_task


@login_required
def content_studio(request):
    """Content creation studio — compose seeds and review AI-generated posts."""
    seed_groups, ungrouped, total_pending = _get_studio_posts(
        request.user,
        status_filter=request.GET.get("status"),
        platform_filter=request.GET.get("platform"),
        format_filter=request.GET.get("post_format"),
        search_query=request.GET.get("q"),
        source_filter=request.GET.get("source"),
    )

    # Recent seeds for processing status — auto-fail any stuck longer than 5 min
    from datetime import timedelta
    from django.utils import timezone as tz

    stale_cutoff = tz.now() - timedelta(minutes=5)
    request.user.content_seeds.filter(
        status__in=["new", "processing"],
        updated_at__lt=stale_cutoff,
    ).update(status="failed", error_message="Generation timed out. Please try again.")

    active_seeds = request.user.content_seeds.filter(
        status__in=["new", "processing"]
    )[:10]
    failed_seeds = request.user.content_seeds.filter(status="failed")[:5]

    connected_platforms = list(
        request.user.social_accounts.filter(is_active=True).values("platform", "username")
    )

    seed_form = ContentSeedForm()

    # Industry Playbook seed suggestions (cold-start help)
    from apps.agents.playbooks import get_seed_suggestions
    seed_suggestions = get_seed_suggestions(request.user)

    # Check if user's plan supports AI image generation
    from apps.billing.enforcement import get_seed_usage
    from apps.billing.models import get_user_plan_limits

    plan_limits = get_user_plan_limits(request.user)
    can_generate_images = plan_limits.get("ai_image_generation", False)

    all_posts = [p for g in seed_groups for p in g["posts"]] + list(ungrouped)
    pending_images = sum(1 for p in all_posts if p.media_status == "pending")

    seed_usage = get_seed_usage(request.user)
    at_seed_limit = seed_usage["at_limit"]
    plan_limit_notice = None
    if at_seed_limit:
        plan_limit_notice = (
            f"You've used all {seed_usage['max']} content seeds this month "
            f"({seed_usage['plan_label']})."
        )

    return render(request, "content/studio.html", {
        "seed_groups": seed_groups,
        "ungrouped_posts": ungrouped,
        "active_seeds": active_seeds,
        "failed_seeds": failed_seeds,
        "seed_form": seed_form,
        "connected_platforms": json.dumps(connected_platforms),
        "connected_platform_count": len(connected_platforms),
        "total_pending": total_pending,
        "pending_images": pending_images,
        "seed_suggestions": seed_suggestions,
        "can_generate_images": can_generate_images,
        "seed_usage": seed_usage,
        "at_seed_limit": at_seed_limit,
        "plan_limit_notice": plan_limit_notice,
        "studio_value": _build_studio_value_stats(request.user),
        "current_status": request.GET.get("status", ""),
        "current_platform": request.GET.get("platform", ""),
        "current_format": request.GET.get("post_format", ""),
        "current_search": request.GET.get("q", ""),
        "current_source": request.GET.get("source", ""),
        "page_title": "Studio",
        "generating_seed_id": request.GET.get("generating", ""),
    })


def _get_studio_posts(user, status_filter=None, platform_filter=None, format_filter=None, search_query=None, source_filter=None):
    """Return (seed_groups, ungrouped, total_pending) for the studio."""
    visible_user_ids = get_teammate_ids(user)

    default_statuses = ["draft", "pending_approval", "rejected"]
    filter_statuses = [status_filter] if status_filter and status_filter in dict(Post.Status.choices) else default_statuses

    posts = Post.objects.filter(
        user_id__in=visible_user_ids,
        status__in=filter_statuses,
    ).select_related("social_account", "seed", "user").order_by("-created_at")

    if platform_filter:
        posts = posts.filter(platform=platform_filter)
    if format_filter:
        posts = posts.filter(post_format=format_filter)
    if search_query:
        from apps.utils.search import full_text_search
        posts = full_text_search(posts, search_query, ["content_text", "first_comment"])
    if source_filter == "holiday":
        # Filter to only holiday-watcher generated posts
        posts = posts.filter(generated_by_agent="holiday_watcher")

    seed_groups = []
    grouped = defaultdict(list)
    ungrouped = []

    for post in posts:
        if post.seed_id:
            grouped[post.seed_id].append(post)
        else:
            ungrouped.append(post)

    seed_ids = list(grouped.keys())
    seeds_map = {s.id: s for s in ContentSeed.objects.filter(id__in=seed_ids)}
    for seed_id, seed_posts in grouped.items():
        seed_obj = seeds_map.get(seed_id)
        if seed_obj:
            seed_groups.append(_enrich_seed_group(seed_obj, seed_posts))

    seed_groups.sort(key=lambda g: g["seed"].created_at, reverse=True)
    return seed_groups, ungrouped, posts.count()


def _enrich_seed_group(seed_obj, seed_posts):
    """Attach batch-approve metadata and value hints to a seed group."""
    pending_statuses = ("pending_approval", "draft")
    approvable = [
        p for p in seed_posts
        if p.status in pending_statuses and not p.needs_media
    ]
    media_blocked = [
        p for p in seed_posts
        if p.status in pending_statuses and p.needs_media
    ]
    # Rough manual-equivalent minutes: ~35 min per platform-native post
    minutes_saved = len(seed_posts) * 35
    return {
        "seed": seed_obj,
        "posts": seed_posts,
        "platform_count": len(seed_posts),
        "all_pending": all(p.status in pending_statuses for p in seed_posts),
        "can_batch_approve": len(approvable) > 0,
        "approvable_count": len(approvable),
        "media_blocked_count": len(media_blocked),
        "minutes_saved_estimate": minutes_saved,
    }


def _build_studio_value_stats(user):
    """ROI metrics shown on Studio — helps users see value for money."""
    from datetime import timedelta

    from django.utils import timezone

    week_ago = timezone.now() - timedelta(days=7)

    posts_created = Post.objects.filter(user=user, created_at__gte=week_ago).count()
    posts_published = Post.objects.filter(
        user=user, status="published", published_at__gte=week_ago,
    ).count()
    seeds_completed = ContentSeed.objects.filter(
        user=user, created_at__gte=week_ago, status="completed",
    ).count()
    platform_count = user.social_accounts.filter(is_active=True).count()
    scheduled = Post.objects.filter(
        user=user, status__in=["approved", "scheduled"],
    ).count()
    pending_review = Post.objects.filter(
        user=user, status__in=["draft", "pending_approval"],
    ).count()

    hours_saved = round((posts_created * 35) / 60, 1)

    return {
        "posts_created_week": posts_created,
        "posts_published_week": posts_published,
        "seeds_week": seeds_completed,
        "platform_count": platform_count,
        "scheduled_count": scheduled,
        "pending_review": pending_review,
        "hours_saved_week": hours_saved,
    }


@login_required
def studio_posts(request):
    """HTMX partial: return just the posts-to-review section."""
    seed_groups, ungrouped, total_pending = _get_studio_posts(
        request.user,
        status_filter=request.GET.get("status"),
        platform_filter=request.GET.get("platform"),
        format_filter=request.GET.get("post_format"),
        search_query=request.GET.get("q"),
        source_filter=request.GET.get("source"),
    )
    all_posts = [p for g in seed_groups for p in g["posts"]] + list(ungrouped)
    pending_images = sum(1 for p in all_posts if p.media_status == "pending")
    return render(request, "content/_studio_posts.html", {
        "seed_groups": seed_groups,
        "ungrouped_posts": ungrouped,
        "total_pending": total_pending,
        "pending_images": pending_images,
        "current_source": request.GET.get("source", ""),
    })


@login_required
def post_card(request, post_id):
    """Return a single post card partial — used by HTMX polling on pending-media cards."""
    post = get_object_or_404(
        Post.objects.select_related("social_account", "seed", "user"), id=post_id
    )
    if post.user_id not in get_teammate_ids(request.user):
        raise Http404
    return render(request, "components/post_card.html", {"post": post, "show_angle": True})


@login_required
@ratelimit(key="user", rate="10/m", block=True)
def submit_seed(request):
    """Handle content seed submission (the 'Drop your idea here' form)."""
    if request.method != "POST":
        return redirect("content:studio")

    from apps.billing.enforcement import check_seed_limit, seed_limit_block_response

    allowed, msg = check_seed_limit(request.user)
    if not allowed:
        return seed_limit_block_response(request, msg)

    is_htmx = request.headers.get("HX-Request") == "true"

    form = ContentSeedForm(request.POST)
    if form.is_valid():
        seed = form.save(commit=False)
        seed.user = request.user
        seed.generation_log = []
        seed.save()

        from apps.agents.create_agent import log_gen_step
        log_gen_step(seed, "queued", "Queued your idea.", seed.idea[:120])

        fire_task(generate_from_seed, str(seed.id))

        redirect_url = f"{reverse('content:studio')}?generating={seed.id}"
        if is_htmx:
            response = HttpResponse(status=200)
            response["HX-Redirect"] = redirect_url
            return response

        messages.success(request, "Your idea is being processed! Posts will appear below shortly.")
        return redirect(redirect_url)

    if is_htmx:
        return HttpResponse(
            '<div class="text-sm text-red-600 dark:text-red-400 px-4 py-3">Please enter your content idea.</div>',
            status=422,
        )

    messages.error(request, "Please enter your content idea.")
    return redirect("content:studio")


@login_required
@require_POST
@ratelimit(key="user", rate="10/m", block=True)
def voice_to_seed(request):
    """
    Accept a voice memo recording, transcribe with Whisper, return text.

    Two modes:
    - mode=transcribe (default): Returns {"text": "..."} JSON for the user to review
    - mode=submit: Transcribes AND creates a ContentSeed (full pipeline)
    """
    from apps.content.voice import transcribe_audio

    audio_file = request.FILES.get("audio")
    if not audio_file:
        return JsonResponse({"error": "No audio file provided."}, status=400)

    content_type = audio_file.content_type or "audio/webm"
    result = transcribe_audio(audio_file, content_type)

    if "error" in result:
        return JsonResponse({"error": result["error"]}, status=422)

    text = result["text"]
    mode = request.POST.get("mode", "transcribe")

    if mode == "submit":
        from apps.billing.enforcement import check_seed_limit

        allowed, msg = check_seed_limit(request.user)
        if not allowed:
            return JsonResponse({
                "error": msg,
                "upgrade_url": reverse("billing:pricing"),
            }, status=402)

        # Create seed directly from transcription
        target_platforms = request.POST.get("target_platforms", "[]")
        try:
            platforms_list = json.loads(target_platforms) if target_platforms else []
        except (json.JSONDecodeError, TypeError):
            platforms_list = []

        seed = ContentSeed.objects.create(
            user=request.user,
            idea=text,
            notes=request.POST.get("notes", ""),
            target_platforms=platforms_list,
        )
        fire_task(generate_from_seed, str(seed.id))

        return JsonResponse({
            "text": text,
            "duration": result.get("duration", 0),
            "seed_id": str(seed.id),
            "submitted": True,
        })

    # Default: transcribe only — let user review before submitting
    return JsonResponse({
        "text": text,
        "duration": result.get("duration", 0),
        "submitted": False,
    })


@login_required
@require_POST
def dismiss_failed_seeds(request):
    """Clear all failed seeds so they don't clutter the studio."""
    deleted, _ = request.user.content_seeds.filter(status="failed").delete()
    if request.headers.get("HX-Request") == "true":
        return HttpResponse("")
    messages.success(request, f"Cleared {deleted} failed generation(s).")
    return redirect("content:studio")


@login_required
@require_POST
def refresh_suggestions(request):
    """HTMX endpoint: clear cached suggestions and regenerate from AI."""
    from django.core.cache import cache

    cache.delete(f"ai_seed_suggestions:{request.user.pk}")

    from apps.agents.playbooks import get_seed_suggestions

    seed_suggestions = get_seed_suggestions(request.user)

    return render(request, "content/_suggestions.html", {
        "seed_suggestions": seed_suggestions,
    })


@login_required
def seed_status(request, seed_id):
    """HTMX endpoint: poll seed processing status."""
    from datetime import timedelta
    from django.utils import timezone as tz

    seed = get_object_or_404(ContentSeed, id=seed_id, user=request.user)

    # Auto-fail seeds stuck in processing for over 5 minutes
    if seed.status in ("new", "processing"):
        if seed.updated_at < tz.now() - timedelta(minutes=5):
            seed.status = "failed"
            seed.error_message = "Generation timed out. Please try again."
            seed.save(update_fields=["status", "error_message", "updated_at"])

    posts = seed.posts.select_related("social_account", "user", "brand").all()
    profile = getattr(request.user, "profile", None)
    auto_approve_posts = bool(profile and profile.auto_approve_posts)
    pending_for_review_count = posts.filter(status__in=["pending_approval", "draft"]).count()
    response = render(request, "content/_seed_status.html", {
        "seed": seed,
        "posts": posts,
        "auto_approve_posts": auto_approve_posts,
        "pending_for_review_count": pending_for_review_count,
    })
    if seed.status == "completed":
        response["HX-Trigger"] = "refreshStudioPosts"
    return response


@login_required
def seed_generation_status(request, seed_id):
    """JSON status for live Studio generation modal."""
    seed = get_object_or_404(ContentSeed, id=seed_id, user=request.user)

    from datetime import timedelta
    from django.utils import timezone as tz

    if seed.status in ("new", "processing"):
        if seed.updated_at < tz.now() - timedelta(minutes=5):
            seed.status = "failed"
            seed.error_message = "Generation timed out. Please try again."
            seed.save(update_fields=["status", "error_message", "updated_at"])

    posts = seed.posts.select_related("social_account").all()
    profile = getattr(request.user, "profile", None)
    auto_approve_posts = bool(profile and profile.auto_approve_posts)
    pending_count = posts.filter(status__in=["pending_approval", "draft"]).count()
    terminal = seed.status in ("completed", "failed")
    return JsonResponse({
        "seed_id": str(seed.pk),
        "status": seed.status,
        "idea": seed.idea[:200],
        "generation_log": seed.generation_log or [],
        "batch_strategy": seed.batch_strategy or "",
        "posts": [
            {
                "id": str(p.id),
                "platform": p.social_account.get_platform_display() if p.social_account else p.platform,
                "angle": p.ai_angle or "",
                "preview": p.content_text[:120],
                "media_status": p.media_status,
                "post_format": p.post_format,
                "video_compose_status": p.reel_compose_status,
                "reel_compose_pending": p.reel_compose_pending,
                "reel_has_video": p.reel_has_video,
                "status": p.status,
            }
            for p in posts
        ],
        "post_count": posts.count(),
        "pending_count": pending_count,
        "auto_approve_posts": auto_approve_posts,
        "queue_url": reverse("content:queue"),
        "error_message": seed.error_message or "",
        "terminal": terminal,
    })


def _apply_queue_filters(qs, platform_filter=None, search_query=None):
    if platform_filter:
        qs = qs.filter(platform=platform_filter)
    if search_query:
        from apps.utils.search import full_text_search
        qs = full_text_search(qs, search_query, ["content_text", "first_comment"])
    return qs


def _group_queue_by_seed(posts_list):
    """Group posts by seed batch — newest campaigns first, posts in generation order."""
    grouped = defaultdict(list)
    ungrouped = []
    for post in posts_list:
        if post.seed_id:
            grouped[post.seed_id].append(post)
        else:
            ungrouped.append(post)

    batches = []
    seed_ids = list(grouped.keys())
    if seed_ids:
        seeds_map = {s.id: s for s in ContentSeed.objects.filter(id__in=seed_ids)}
        for seed_id, seed_posts in grouped.items():
            seed_obj = seeds_map.get(seed_id)
            if not seed_obj:
                continue
            seed_posts.sort(key=lambda p: p.created_at)
            batches.append({
                "seed": seed_obj,
                "posts": seed_posts,
                "platform_count": len(seed_posts),
                "generated_at": seed_obj.created_at,
            })

    batches.sort(key=lambda b: b["generated_at"], reverse=True)
    ungrouped.sort(key=lambda p: p.created_at, reverse=True)
    return batches, ungrouped


def _get_queue_context(user, section_filter=None, platform_filter=None, search_query=None):
    """Build queue sections, stats, and filter state."""
    from django.db.models import Q

    visible_user_ids = get_teammate_ids(user)
    base = Post.objects.filter(user_id__in=visible_user_ids).select_related(
        "social_account", "seed", "user",
    )

    failed_qs = _apply_queue_filters(
        base.filter(status="failed").order_by("-created_at"),
        platform_filter, search_query,
    )
    publishing_qs = _apply_queue_filters(
        base.filter(status="publishing").order_by("-created_at"),
        platform_filter, search_query,
    )
    ready_qs = _apply_queue_filters(
        base.filter(status="approved", scheduled_at__isnull=True).order_by("-created_at"),
        platform_filter, search_query,
    )
    scheduled_qs = _apply_queue_filters(
        base.filter(
            Q(status="scheduled") | Q(status="approved", scheduled_at__isnull=False)
        ).order_by("-created_at"),
        platform_filter, search_query,
    )
    published_qs = _apply_queue_filters(
        base.filter(status="published").order_by("-published_at")[:50],
        platform_filter, search_query,
    )

    # Stats use unfiltered counts so tab badges stay accurate while browsing
    stats_base = Post.objects.filter(user_id__in=visible_user_ids)
    queue_stats = {
        "ready_count": stats_base.filter(status="approved", scheduled_at__isnull=True).count(),
        "scheduled_count": stats_base.filter(
            Q(status="scheduled") | Q(status="approved", scheduled_at__isnull=False)
        ).count(),
        "publishing_count": stats_base.filter(status="publishing").count(),
        "failed_count": stats_base.filter(status="failed").count(),
        "published_count": stats_base.filter(status="published").count(),
    }

    failed = list(failed_qs)
    publishing = list(publishing_qs)
    ready = list(ready_qs)
    scheduled = list(scheduled_qs)
    published = list(published_qs)

    ready_batches, ready_ungrouped = _group_queue_by_seed(ready)
    scheduled_batches, scheduled_ungrouped = _group_queue_by_seed(scheduled)
    published_batches, published_ungrouped = _group_queue_by_seed(published)

    section = section_filter if section_filter in ("ready", "scheduled", "live", "attention") else "all"

    return {
        "section": section,
        "queue_stats": queue_stats,
        "failed": failed,
        "publishing": publishing,
        "ready_batches": ready_batches,
        "ready_ungrouped": ready_ungrouped,
        "ready_count": len(ready),
        "scheduled_batches": scheduled_batches,
        "scheduled_ungrouped": scheduled_ungrouped,
        "scheduled_count": len(scheduled),
        "published_batches": published_batches,
        "published_ungrouped": published_ungrouped,
        "published_count": len(published),
        "current_section": section,
        "current_platform": platform_filter or "",
        "current_search": search_query or "",
    }


@login_required
def content_queue(request):
    """Pipeline view — approved, scheduled, and published posts grouped by campaign."""
    ctx = _get_queue_context(
        request.user,
        section_filter=request.GET.get("section"),
        platform_filter=request.GET.get("platform"),
        search_query=request.GET.get("q"),
    )
    ctx["page_title"] = "Content Queue"
    return render(request, "content/queue.html", ctx)


@login_required
def queue_sections(request):
    """HTMX partial: filtered queue sections."""
    ctx = _get_queue_context(
        request.user,
        section_filter=request.GET.get("section"),
        platform_filter=request.GET.get("platform"),
        search_query=request.GET.get("q"),
    )
    return render(request, "content/_queue_sections.html", ctx)


@login_required
def calendar_view(request):
    """Timeline view — scheduled + published posts grouped by day, then by seed."""
    visible_user_ids = get_teammate_ids(request.user)
    team_posts = Post.objects.filter(user_id__in=visible_user_ids)

    scheduled_posts = team_posts.filter(
        status__in=["approved", "scheduled", "published"],
        scheduled_at__isnull=False,
    ).select_related("social_account", "seed", "user").order_by("scheduled_at")

    unscheduled_posts = team_posts.filter(
        status__in=["approved", "scheduled"],
        scheduled_at__isnull=True,
    ).select_related("social_account", "seed", "user").order_by("-updated_at")

    # Group scheduled posts by date
    raw_by_date = defaultdict(list)
    for post in scheduled_posts:
        raw_by_date[post.scheduled_at.date()].append(post)

    # Within each date, sub-group by seed
    def group_day_by_seed(day_posts):
        """Return list of seed groups + ungrouped posts for a single day."""
        grouped = defaultdict(list)
        ungrouped = []
        for post in day_posts:
            if post.seed_id:
                grouped[post.seed_id].append(post)
            else:
                ungrouped.append(post)
        batches = []
        if grouped:
            seed_ids = list(grouped.keys())
            seeds_map = {s.id: s for s in ContentSeed.objects.filter(id__in=seed_ids)}
            for seed_id, seed_posts in grouped.items():
                seed_obj = seeds_map.get(seed_id)
                if seed_obj:
                    batches.append({"seed": seed_obj, "posts": seed_posts})
        return batches, ungrouped

    posts_by_date = {}
    for date, day_posts in raw_by_date.items():
        batches, ungrouped = group_day_by_seed(day_posts)
        posts_by_date[date] = {
            "batches": batches,
            "ungrouped": ungrouped,
            "total": len(day_posts),
        }

    # Group unscheduled by seed too
    unscheduled_grouped = defaultdict(list)
    unscheduled_ungrouped = []
    for post in unscheduled_posts:
        if post.seed_id:
            unscheduled_grouped[post.seed_id].append(post)
        else:
            unscheduled_ungrouped.append(post)
    unscheduled_batches = []
    if unscheduled_grouped:
        seed_ids = list(unscheduled_grouped.keys())
        seeds_map = {s.id: s for s in ContentSeed.objects.filter(id__in=seed_ids)}
        for seed_id, seed_posts in unscheduled_grouped.items():
            seed_obj = seeds_map.get(seed_id)
            if seed_obj:
                unscheduled_batches.append({"seed": seed_obj, "posts": seed_posts})

    return render(request, "content/calendar.html", {
        "posts_by_date": posts_by_date,
        "unscheduled_batches": unscheduled_batches,
        "unscheduled_ungrouped": unscheduled_ungrouped,
        "unscheduled_count": unscheduled_posts.count(),
        "page_title": "Content Calendar",
    })


@login_required
@login_required
@require_POST
def reschedule_post(request, post_id):
    """P4.3 — Move a scheduled post to a new time. JSON or form POST.

    Body: `scheduled_at` — ISO datetime (or any parseable format).
    Returns: JSON {ok, scheduled_at} on success.

    The calendar UI drives this from drag-and-drop; the queue card has
    a simple inline form fallback.
    """
    from datetime import datetime as dt
    from django.http import JsonResponse, HttpResponseBadRequest
    from django.utils import timezone

    post = get_object_or_404(
        Post.objects.select_related("user"), id=post_id,
    )
    if post.user_id != request.user.id and not _has_team_access(request.user, post):
        raise Http404
    if post.status not in (
        Post.Status.APPROVED, Post.Status.SCHEDULED, Post.Status.DRAFT,
        Post.Status.PENDING_APPROVAL,
    ):
        return HttpResponseBadRequest("Cannot reschedule a published or failed post.")

    raw = (request.POST.get("scheduled_at") or "").strip()
    if not raw:
        return HttpResponseBadRequest("scheduled_at required")
    try:
        when = dt.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return HttpResponseBadRequest("scheduled_at must be ISO datetime")
    if timezone.is_naive(when):
        when = timezone.make_aware(when, timezone.get_current_timezone())
    if when < timezone.now():
        return HttpResponseBadRequest("scheduled_at must be in the future")

    post.scheduled_at = when
    if post.status == Post.Status.APPROVED:
        post.status = Post.Status.SCHEDULED
    post.save(update_fields=["scheduled_at", "status", "updated_at"])

    return JsonResponse({
        "ok": True,
        "scheduled_at": post.scheduled_at.isoformat(),
        "status": post.status,
    })


def _has_team_access(user, post):
    try:
        from apps.teams.models import get_teammate_ids
        return post.user_id in get_teammate_ids(user)
    except Exception:
        return False


def approve_post(request, post_id):
    """Approve a post with intent-based scheduling."""
    from datetime import datetime as dt

    from django.utils import timezone

    from apps.content.scheduling import (
        get_next_best_slot,
        get_quick_schedule_time,
        get_smart_queue_slot,
    )

    post = get_object_or_404(Post.objects.select_related("social_account", "user"), id=post_id)
    if not can_approve_post(request.user, post):
        raise Http404
    is_htmx = bool(request.headers.get("HX-Request"))

    if post.status not in (Post.Status.DRAFT, Post.Status.PENDING_APPROVAL):
        if is_htmx:
            return render(request, "components/post_card.html", {"post": post})
        return redirect("content:post_detail", post_id=post.id)

    # Block approval if platform requires media and none exists
    if post.needs_media:
        from django.contrib import messages
        platform_name = post.social_account.get_platform_display() if post.social_account else "This platform"
        messages.warning(
            request,
            f"{platform_name} requires an image. Upload one before approving.",
        )
        if is_htmx:
            return render(request, "components/post_card.html", {"post": post})
        return redirect("content:post_detail", post_id=post.id)

    intent = request.POST.get("schedule_intent", "next_best")
    platform = post.social_account.platform if post.social_account else None

    if intent == "post_now":
        post.scheduled_at = timezone.now()
    elif intent == "next_best":
        post.scheduled_at = get_next_best_slot(request.user, platform)
    elif intent == "smart_queue":
        post.scheduled_at = get_smart_queue_slot(request.user)
    elif intent.startswith("quick:"):
        option = intent.split(":", 1)[1]
        post.scheduled_at = get_quick_schedule_time(option)
    elif intent == "exact":
        exact_str = request.POST.get("exact_datetime", "")
        if exact_str:
            try:
                naive = dt.fromisoformat(exact_str)
                post.scheduled_at = timezone.make_aware(
                    naive, timezone.get_current_timezone()
                )
            except (ValueError, TypeError):
                post.scheduled_at = get_next_best_slot(request.user, platform)
        else:
            post.scheduled_at = get_next_best_slot(request.user, platform)
    else:
        post.scheduled_at = get_next_best_slot(request.user, platform)

    post.status = Post.Status.APPROVED
    post.save(update_fields=["status", "scheduled_at", "updated_at"])

    # If "post_now" — fire the publish task immediately
    if intent == "post_now":
        from apps.content.tasks import publish_post
        fire_task(publish_post, str(post.id))

    if is_htmx:
        return render(request, "components/post_card.html", {"post": post})
    return redirect("content:post_detail", post_id=post.id)


@login_required
def batch_approve(request, seed_id):
    """Approve ALL posts from a seed at once with the same scheduling intent."""
    from datetime import datetime as dt
    from django.utils import timezone
    from apps.content.scheduling import (
        get_next_best_slot,
        get_quick_schedule_time,
        get_smart_queue_slot,
    )

    seed = get_object_or_404(ContentSeed, id=seed_id)
    visible_user_ids = get_teammate_ids(request.user)
    if seed.user_id not in visible_user_ids:
        raise Http404
    posts = Post.objects.filter(
        seed=seed,
        user_id__in=visible_user_ids,
        status__in=(Post.Status.DRAFT, Post.Status.PENDING_APPROVAL),
    ).select_related("social_account")

    if not posts.exists():
        return redirect("content:studio")

    intent = request.POST.get("schedule_intent", "next_best")
    now = timezone.now()

    approved_count = 0
    skipped_media = 0
    post_now_ids = []

    for post in posts:
        if post.needs_media:
            skipped_media += 1
            continue

        platform = post.social_account.platform if post.social_account else None

        if intent == "post_now":
            post.scheduled_at = now
        elif intent == "next_best":
            post.scheduled_at = get_next_best_slot(request.user, platform)
        elif intent == "smart_queue":
            post.scheduled_at = get_smart_queue_slot(request.user)
        elif intent.startswith("quick:"):
            option = intent.split(":", 1)[1]
            post.scheduled_at = get_quick_schedule_time(option)
        elif intent == "exact":
            exact_str = request.POST.get("exact_datetime", "")
            if exact_str:
                try:
                    naive = dt.fromisoformat(exact_str)
                    post.scheduled_at = timezone.make_aware(
                        naive, timezone.get_current_timezone()
                    )
                except (ValueError, TypeError):
                    post.scheduled_at = get_next_best_slot(request.user, platform)
            else:
                post.scheduled_at = get_next_best_slot(request.user, platform)
        else:
            post.scheduled_at = get_next_best_slot(request.user, platform)

        post.status = Post.Status.APPROVED
        post.save(update_fields=["status", "scheduled_at", "updated_at"])
        approved_count += 1

        if intent == "post_now":
            post_now_ids.append(str(post.id))

    if intent == "post_now":
        from apps.content.tasks import publish_post
        for post_id in post_now_ids:
            fire_task(publish_post, post_id)

    if approved_count == 0 and skipped_media:
        messages.warning(
            request,
            f"No posts approved — {skipped_media} need images before they can go live.",
        )
    elif skipped_media:
        messages.warning(
            request,
            f"Approved {approved_count} posts. {skipped_media} skipped — upload images first.",
        )
    elif approved_count:
        messages.success(request, f"All {approved_count} posts approved and scheduled!")
    return redirect("content:studio")


@login_required
def reject_post(request, post_id):
    """Reject a pending post."""
    post = get_object_or_404(Post.objects.select_related("social_account", "user"), id=post_id)
    if not can_approve_post(request.user, post):
        raise Http404
    if post.status in (Post.Status.DRAFT, Post.Status.PENDING_APPROVAL):
        post.status = Post.Status.REJECTED
        post.save(update_fields=["status", "updated_at"])
    if request.headers.get("HX-Request"):
        return render(request, "components/post_card.html", {"post": post})
    return redirect("content:post_detail", post_id=post.id)


@login_required
@require_POST
def rate_post(request, post_id):
    """
    Quick-rate a post's AI quality (HTMX).

    Accepts rating=1 (poor), 2 (good), 3 (great).
    Returns an updated rating widget fragment.
    """
    post = get_object_or_404(Post, id=post_id, user=request.user)
    try:
        rating = int(request.POST.get("rating", 0))
    except (ValueError, TypeError):
        rating = 0

    if rating in (1, 2, 3):
        post.user_rating = rating
        post.save(update_fields=["user_rating", "updated_at"])

    return render(request, "components/_rating_widget.html", {"post": post})


@login_required
@require_POST
def delete_post(request, post_id):
    """Soft-delete a post (HTMX). Removes it from the studio."""
    post = get_object_or_404(Post.objects.select_related("user"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404
    # Only allow deleting non-published posts
    if post.status in (Post.Status.PUBLISHED, Post.Status.PUBLISHING):
        return HttpResponse("Cannot delete a published post", status=400)
    post.soft_delete()
    # Return empty response to remove the card from the DOM
    return HttpResponse("")


@login_required
def regenerate_post(request, post_id):
    """Kick off async regeneration and return a polling card."""
    from apps.content.tasks import regenerate_post_async

    post = get_object_or_404(Post.objects.select_related("social_account", "user"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404

    if request.method != "POST":
        return HttpResponse(status=405)

    # Only allow regeneration for editable statuses
    if post.status not in (
        Post.Status.DRAFT,
        Post.Status.PENDING_APPROVAL,
        Post.Status.REJECTED,
    ):
        return render(request, "components/post_card.html", {"post": post})

    # Stash the old content_text so we can detect when regeneration completes
    request.session[f"regen_{post.id}"] = post.content_text[:100]

    # Fire async
    fire_task(regenerate_post_async, str(post.id))

    # Return a card with a spinner that polls for completion
    return render(request, "components/_post_regenerating.html", {"post": post})


@login_required
def regenerate_status(request, post_id):
    """HTMX polling endpoint: returns updated post card once regeneration is done."""
    post = get_object_or_404(Post.objects.select_related("social_account", "user"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404

    old_snippet = request.session.get(f"regen_{post.id}", "")
    current_snippet = post.content_text[:100]

    # If the content changed, regeneration is done
    if old_snippet and current_snippet != old_snippet:
        request.session.pop(f"regen_{post.id}", None)
        return render(request, "components/post_card.html", {"post": post})

    # Still regenerating — return the spinner card again (keeps polling)
    return render(request, "components/_post_regenerating.html", {"post": post})


@login_required
def edit_post(request, post_id):
    """Edit a post's content."""
    post = get_object_or_404(Post.objects.select_related("social_account", "seed", "user"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404
    if request.method == "POST":
        form = PostEditForm(request.POST, instance=post)
        if form.is_valid():
            old_content = post.content_text
            post = form.save(commit=False)

            # Only reset to DRAFT if the actual content changed
            content_changed = post.content_text != old_content
            if content_changed and post.status in (
                Post.Status.PENDING_APPROVAL,
                Post.Status.APPROVED,
                Post.Status.SCHEDULED,
            ):
                post.status = Post.Status.DRAFT

            # Rejected posts get promoted to PENDING_APPROVAL after editing
            if content_changed and post.status == Post.Status.REJECTED:
                post.status = Post.Status.PENDING_APPROVAL

            update_fields = ["content_text", "updated_at"]
            if content_changed:
                update_fields.append("status")
            # CTA fields
            update_fields.extend(["cta_type", "cta_text", "cta_url", "first_comment"])
            # Auto-populate UTM when CTA is set
            if post.cta_type != "none" and post.cta_url:
                post.populate_utm()
                update_fields.extend(["utm_source", "utm_medium", "utm_campaign", "utm_content"])
            post.save(update_fields=update_fields)

            # Intelligence: track edit feedback for agent learning
            if content_changed:
                from apps.agents.memory import record_edit_feedback
                from apps.content.models import PostVersion
                record_edit_feedback(post)
                # Save version snapshot
                last_ver = post.versions.order_by("-version_number").values_list("version_number", flat=True).first()
                PostVersion.objects.create(
                    post=post,
                    version_number=(last_ver or 0) + 1,
                    content_text=post.content_text,
                    source="user_edit",
                    edited_by=request.user,
                )

            messages.success(request, "Post updated.")
            return redirect("content:studio")
    else:
        form = PostEditForm(instance=post)

    return render(request, "content/edit.html", {
        "post": post,
        "form": form,
        "page_title": "Edit Post",
        "user_kova_pages": request.user.kova_pages.filter(is_published=True).only("slug", "title")[:10],
    })


@login_required
def upload_media(request, post_id):
    """Upload an image to a post."""
    from io import BytesIO

    from PIL import Image

    from apps.content.models import MediaAttachment

    post = get_object_or_404(Post.objects.select_related("user"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404
    if request.method == "POST" and request.FILES.get("file"):
        uploaded = request.FILES["file"]
        # Basic validation
        if uploaded.size > 10 * 1024 * 1024:  # 10MB limit
            return HttpResponse("File too large (max 10MB)", status=400)

        allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
        if uploaded.content_type not in allowed_types:
            return HttpResponse("Unsupported file type", status=400)

        # Validate actual file content via magic bytes (not just Content-Type header)
        try:
            img = Image.open(uploaded)
            img.verify()  # checks file integrity without loading full image
            actual_format = img.format  # JPEG, PNG, GIF, WEBP
            if actual_format not in ("JPEG", "PNG", "GIF", "WEBP"):
                return HttpResponse("Invalid image file", status=400)
        except Exception:
            return HttpResponse("Invalid or corrupted image file", status=400)

        # Strip EXIF data (GPS, camera info) for privacy — re-save clean image
        uploaded.seek(0)
        if actual_format in ("JPEG", "PNG", "WEBP"):
            try:
                img = Image.open(uploaded)
                clean = BytesIO()
                # Re-save without EXIF by creating a new image from pixel data
                clean_img = Image.new(img.mode, img.size)
                clean_img.putdata(list(img.getdata()))
                save_fmt = actual_format if actual_format != "JPEG" else "JPEG"
                save_kwargs = {"format": save_fmt}
                if save_fmt == "JPEG":
                    save_kwargs["quality"] = 95
                clean_img.save(clean, **save_kwargs)
                clean.seek(0)
                # Replace the uploaded file content with the clean version
                from django.core.files.uploadedfile import InMemoryUploadedFile
                uploaded = InMemoryUploadedFile(
                    clean, "file", uploaded.name, uploaded.content_type,
                    clean.getbuffer().nbytes, uploaded.charset,
                )
            except Exception:
                uploaded.seek(0)  # fallback to original if stripping fails

        file_type = "image"
        if uploaded.content_type == "image/gif":
            file_type = "gif"

        order = post.attachments.count()
        attachment = MediaAttachment.objects.create(
            post=post,
            file=uploaded,
            file_type=file_type,
            alt_text=request.POST.get("alt_text", ""),
            order=order,
        )
        # Update media_status to reflect manual upload
        if post.media_status != Post.MediaStatus.GENERATED:
            post.media_status = Post.MediaStatus.UPLOADED
            post.save(update_fields=["media_status", "updated_at"])
        return render(request, "content/_media_item.html", {"attachment": attachment})

    return HttpResponse(status=405)


@login_required
@require_POST
def retry_image(request, post_id):
    """Retry AI image generation for a post that failed."""
    post = get_object_or_404(Post.objects.select_related("user", "social_account"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404
    if post.media_status != Post.MediaStatus.FAILED:
        return HttpResponse("Post image did not fail", status=400)

    prompt = post.media_prompt or ""
    if not prompt.strip():
        messages.error(request, "No image prompt available to retry.")
        return redirect("content:edit", post_id=post.id)

    post.media_status = Post.MediaStatus.PENDING
    post.save(update_fields=["media_status", "updated_at"])

    # Re-run image generation via Celery
    from apps.content.tasks import retry_image_generation
    fire_task(retry_image_generation, str(post.id))

    if request.headers.get("HX-Request"):
        return HttpResponse(
            '<span class="text-[10px] font-medium px-2 py-0.5 rounded-md '
            'bg-yellow-50 text-yellow-600 dark:bg-yellow-950 dark:text-yellow-400">'
            '⏳ Retrying…</span>'
        )
    messages.info(request, "Retrying image generation…")
    return redirect("content:edit", post_id=post.id)


@login_required
@require_POST
def retry_reel(request, post_id):
    """Retry motion reel composition for a failed or stuck reel post."""
    post = get_object_or_404(Post.objects.select_related("user", "social_account"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404
    if post.post_format != Post.PostFormat.REEL:
        return HttpResponse("Not a reel post", status=400)

    from apps.content.tasks import _queue_reel_compose

    meta = dict(post.visual_metadata or {})
    meta.pop("video_compose_error", None)
    post.visual_metadata = meta
    post.media_status = Post.MediaStatus.GENERATED
    post.save(update_fields=["visual_metadata", "media_status", "updated_at"])

    _queue_reel_compose(str(post.id))

    if request.headers.get("HX-Request"):
        return render(request, "components/post_card.html", {"post": post})
    messages.info(request, "Re-composing motion reel…")
    return redirect("content:edit", post_id=post.id)


@login_required
@require_POST
def retry_publish(request, post_id):
    """Retry publishing a failed post — resets to APPROVED and fires publish task."""
    post = get_object_or_404(Post.objects.select_related("user", "social_account"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404
    if post.status != Post.Status.FAILED:
        return HttpResponse("Post is not in failed state", status=400)

    from django.utils import timezone
    from apps.content.tasks import publish_post
    from apps.utils import fire_task

    post.status = Post.Status.APPROVED
    post.scheduled_at = timezone.now()
    post.ai_reasoning = ""
    post.publish_error = ""
    post.save(update_fields=["status", "scheduled_at", "ai_reasoning", "publish_error", "updated_at"])

    fire_task(publish_post, str(post.id))

    if request.headers.get("HX-Request"):
        return render(request, "components/post_card.html", {"post": post})
    messages.info(request, "Retrying publish…")
    return redirect("content:queue")


@login_required
@require_POST
def update_carousel_slides(request, post_id):
    """Save edited carousel slide content (heading, body, image_prompt)."""
    post = get_object_or_404(Post.objects.select_related("user"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404
    if post.post_format != Post.PostFormat.CAROUSEL:
        return HttpResponse("Not a carousel post", status=400)

    try:
        slides_raw = json.loads(request.POST.get("carousel_slides_json", "[]"))
        if not isinstance(slides_raw, list):
            raise ValueError
        clean_slides = []
        for s in slides_raw:
            if not isinstance(s, dict):
                continue
            clean_slides.append({
                "heading": str(s.get("heading", ""))[:200],
                "body": str(s.get("body", ""))[:2000],
                "image_prompt": str(s.get("image_prompt", ""))[:500],
                "image_url": str(s.get("image_url", "")),
            })
    except (json.JSONDecodeError, ValueError):
        if request.headers.get("HX-Request"):
            return HttpResponse("Invalid slide data", status=400)
        messages.error(request, "Invalid slide data.")
        return redirect("content:edit", post_id=post.id)

    post.carousel_slides = clean_slides
    post.save(update_fields=["carousel_slides", "updated_at"])

    if request.headers.get("HX-Request"):
        return HttpResponse(
            '<span id="slides-save-feedback" class="text-xs text-emerald-600 dark:text-emerald-400 font-medium">'
            '✓ Slides saved</span>'
        )
    messages.success(request, "Slides updated.")
    return redirect("content:edit", post_id=post.id)


@login_required
@require_POST
def generate_image(request, post_id):
    """Generate an AI image for a post that doesn't have one yet (opt-in for text-first platforms)."""
    post = get_object_or_404(
        Post.objects.select_related("user", "user__profile", "social_account"), id=post_id,
    )
    if not can_edit_post(request.user, post):
        raise Http404

    # Only allow for posts without images
    if post.media_status in (Post.MediaStatus.GENERATED, Post.MediaStatus.PENDING):
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<span class="text-[10px] font-medium px-2 py-0.5 rounded-md '
                'bg-yellow-50 text-yellow-600 dark:bg-yellow-950 dark:text-yellow-400">'
                'Image already exists or is generating</span>'
            )
        return redirect("content:edit", post_id=post.id)

    # Check plan allows AI images
    from apps.billing.models import get_user_plan_limits
    from apps.billing.plan_limit_ui import plan_limit_banner_html, plan_limit_redirect

    plan_limits = get_user_plan_limits(post.user)
    if not plan_limits.get("ai_image_generation", False):
        if request.headers.get("HX-Request"):
            return HttpResponse(
                plan_limit_banner_html("Your plan doesn't include AI image generation."),
                status=403,
            )
        return plan_limit_redirect(
            request,
            "Your plan doesn't include AI image generation.",
            "content:edit",
            post_id=post.id,
        )

    # Check monthly limit
    from django.utils import timezone as tz
    monthly_limit = plan_limits.get("ai_images_per_month", 5)
    month_start = tz.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    images_this_month = Post.objects.filter(
        user=post.user, media_status="generated", created_at__gte=month_start,
    ).count()
    if images_this_month >= monthly_limit:
        limit_msg = f"Monthly image limit reached ({images_this_month}/{monthly_limit})."
        if request.headers.get("HX-Request"):
            return HttpResponse(plan_limit_banner_html(limit_msg), status=403)
        return plan_limit_redirect(
            request,
            limit_msg,
            "content:edit",
            post_id=post.id,
        )

    # Use stored prompt or generate a basic one from content
    prompt = post.media_prompt
    if not prompt:
        prompt = f"Social media image for: {post.content_text[:200]}"
        post.media_prompt = prompt

    post.media_status = Post.MediaStatus.PENDING
    post.save(update_fields=["media_status", "media_prompt", "updated_at"])

    from apps.content.tasks import async_generate_image
    visual_strategy_data = post.visual_metadata.get("strategy_data") if post.visual_metadata else None
    fire_task(async_generate_image, str(post.id), prompt, visual_strategy_data)

    if request.headers.get("HX-Request"):
        return render(request, "components/post_card.html", {"post": post})
    messages.info(request, "Generating AI image…")
    return redirect("content:edit", post_id=post.id)


@login_required
@require_http_methods(["POST", "DELETE"])
def delete_media(request, post_id, attachment_id):
    """Delete a media attachment from a post via HTMX."""
    from apps.content.models import MediaAttachment

    post = get_object_or_404(Post.objects.select_related("user"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404
    attachment = get_object_or_404(MediaAttachment, id=attachment_id, post=post)

    # Delete the file from storage and the DB record
    if attachment.file:
        attachment.file.delete(save=False)
    attachment.delete()

    # Update media_status if no attachments remain
    if not post.attachments.exists() and not post.media_urls:
        post.media_status = Post.MediaStatus.NONE
        post.save(update_fields=["media_status", "updated_at"])

    return HttpResponse("")  # empty response removes the element via hx-swap


@login_required
@require_POST
def clear_ai_media(request, post_id):
    """Remove AI-generated images from a post (clear media_urls)."""
    post = get_object_or_404(Post.objects.select_related("user", "social_account"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404

    post.media_urls = []
    if not post.attachments.exists():
        post.media_status = Post.MediaStatus.NONE
    post.save(update_fields=["media_urls", "media_status", "updated_at"])

    if request.headers.get("HX-Request"):
        return render(request, "components/post_card.html", {"post": post})
    return redirect("content:edit", post_id=post.id)


@login_required
@require_POST
def regenerate_image(request, post_id):
    """Discard the current AI image and generate a fresh one using the stored prompt."""
    from apps.utils import fire_task

    post = get_object_or_404(
        Post.objects.select_related("user", "social_account", "user__profile"), id=post_id,
    )
    if not can_edit_post(request.user, post):
        raise Http404
    if post.status not in (Post.Status.DRAFT, Post.Status.PENDING_APPROVAL):
        return HttpResponse("Cannot regenerate image for this post", status=400)

    # Carousel posts use real product photos — there is no text prompt to regenerate from.
    if post.visual_strategy == "carousel":
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<span class="text-xs text-amber-600 dark:text-amber-400 px-1">'
                'Update the product to change carousel images.</span>'
            )
        return redirect("content:edit", post_id=post.id)

    post.media_urls = []
    post.media_status = Post.MediaStatus.PENDING
    post.save(update_fields=["media_urls", "media_status", "updated_at"])

    from apps.content.tasks import retry_image_generation
    fire_task(retry_image_generation, str(post.id))

    if request.headers.get("HX-Request"):
        return render(request, "components/post_card.html", {"post": post, "show_angle": True})
    return redirect("content:edit", post_id=post.id)


@login_required
@require_POST
def card_upload_media(request, post_id):
    """Upload an image from the post card. Returns the updated card."""
    from io import BytesIO

    from PIL import Image

    from apps.content.models import MediaAttachment

    post = get_object_or_404(Post.objects.select_related("user", "social_account", "seed"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404

    uploaded = request.FILES.get("file")
    if not uploaded:
        return render(request, "components/post_card.html", {"post": post})

    # Validate size
    if uploaded.size > 10 * 1024 * 1024:
        messages.error(request, "File too large (max 10MB).")
        return render(request, "components/post_card.html", {"post": post})

    # Validate content type
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if uploaded.content_type not in allowed_types:
        messages.error(request, "Unsupported file type.")
        return render(request, "components/post_card.html", {"post": post})

    # Validate via PIL magic bytes
    try:
        img = Image.open(uploaded)
        img.verify()
        actual_format = img.format
        if actual_format not in ("JPEG", "PNG", "GIF", "WEBP"):
            messages.error(request, "Invalid image file.")
            return render(request, "components/post_card.html", {"post": post})
    except Exception:
        messages.error(request, "Invalid or corrupted image.")
        return render(request, "components/post_card.html", {"post": post})

    # Strip EXIF for privacy
    uploaded.seek(0)
    if actual_format in ("JPEG", "PNG", "WEBP"):
        try:
            img = Image.open(uploaded)
            clean = BytesIO()
            clean_img = Image.new(img.mode, img.size)
            clean_img.putdata(list(img.getdata()))
            save_fmt = actual_format if actual_format != "JPEG" else "JPEG"
            save_kwargs = {"format": save_fmt}
            if save_fmt == "JPEG":
                save_kwargs["quality"] = 95
            clean_img.save(clean, **save_kwargs)
            clean.seek(0)
            from django.core.files.uploadedfile import InMemoryUploadedFile
            uploaded = InMemoryUploadedFile(
                clean, "file", uploaded.name, uploaded.content_type,
                clean.getbuffer().nbytes, uploaded.charset,
            )
        except Exception:
            uploaded.seek(0)

    file_type = "gif" if uploaded.content_type == "image/gif" else "image"
    order = post.attachments.count()
    MediaAttachment.objects.create(
        post=post,
        file=uploaded,
        file_type=file_type,
        alt_text="",
        order=order,
    )

    post.media_status = Post.MediaStatus.UPLOADED
    post.save(update_fields=["media_status", "updated_at"])

    return render(request, "components/post_card.html", {"post": post})


@login_required
def post_preview(request, post_id):
    """HTMX partial: platform-specific visual preview of a post."""
    post = get_object_or_404(
        Post.objects.select_related("social_account", "user"),
        id=post_id,
    )
    if not can_edit_post(request.user, post):
        raise Http404
    return render(request, "content/preview.html", {"post": post})


@login_required
def post_detail(request, post_id):
    """Full detail view for a single post with metrics and activity."""
    post = get_object_or_404(
        Post.objects.select_related("social_account", "seed", "user"),
        id=post_id,
    )
    if not can_edit_post(request.user, post):
        raise Http404

    metrics = None
    try:
        metrics = post.metrics
    except Exception:
        pass

    notifications = []
    try:
        from apps.notifications.models import Notification
        notifications = Notification.objects.filter(
            related_post=post,
        ).select_related("related_post").order_by("-created_at")[:10]
    except Exception:
        pass

    return render(request, "content/detail.html", {
        "post": post,
        "metrics": metrics,
        "notifications": notifications,
        "page_title": "Post Detail",
    })


# ─── A/B Testing Views ──────────────────────────────────────────────────────

@login_required
def ab_test_list(request):
    """List user's A/B tests."""
    from apps.billing.enforcement import check_ab_testing, enforce_or_redirect

    allowed, msg = check_ab_testing(request.user)
    if blocked := enforce_or_redirect(request, allowed, msg, "content:ab_test_list"):
        return blocked

    tests = request.user.ab_tests.select_related(
        "social_account", "seed", "winner",
    ).order_by("-created_at")

    return render(request, "content/ab_tests/list.html", {
        "tests": tests,
        "page_title": "A/B Tests",
    })


@login_required
def ab_test_create(request):
    """Create a new A/B test."""
    from apps.billing.enforcement import check_ab_testing, check_seed_limit, enforce_or_redirect
    from apps.content.models import ABTest, ContentSeed
    from apps.content.tasks import generate_ab_test_variants
    from apps.platforms.models import SocialAccount

    allowed, msg = check_ab_testing(request.user)
    if blocked := enforce_or_redirect(request, allowed, msg, "content:ab_test_list"):
        return blocked

    accounts = SocialAccount.objects.filter(user=request.user, is_active=True)
    if not accounts.exists():
        messages.error(request, "Connect a social account first.")
        return redirect("content:ab_test_list")

    if request.method == "POST":
        idea = request.POST.get("idea", "").strip()
        notes = request.POST.get("notes", "").strip()
        account_id = request.POST.get("social_account", "")
        variant_count = int(request.POST.get("variant_count", "3"))
        duration = int(request.POST.get("test_duration_hours", "48"))

        if not idea:
            messages.error(request, "Please enter a content idea.")
            return redirect("content:ab_test_create")

        seed_allowed, seed_msg = check_seed_limit(request.user)
        if blocked := enforce_or_redirect(request, seed_allowed, seed_msg, "content:ab_test_list"):
            return blocked

        account = get_object_or_404(SocialAccount, id=account_id, user=request.user)
        variant_count = max(2, min(variant_count, 5))
        duration = max(12, min(duration, 168))

        # Create seed
        seed = ContentSeed.objects.create(
            user=request.user,
            idea=idea,
            notes=notes,
            target_platforms=[account.platform],
            status=ContentSeed.SeedStatus.PROCESSING,
        )

        # Create ABTest
        ab_test = ABTest.objects.create(
            user=request.user,
            name=idea[:255],
            seed=seed,
            social_account=account,
            variant_count=variant_count,
            test_duration_hours=duration,
            status=ABTest.Status.GENERATING,
        )

        # Fire async generation
        fire_task(generate_ab_test_variants, str(ab_test.id))

        messages.success(request, f"A/B test created! Generating {variant_count} variants...")
        return redirect("content:ab_test_detail", test_id=ab_test.id)

    return render(request, "content/ab_tests/create.html", {
        "accounts": accounts,
        "page_title": "New A/B Test",
    })


@login_required
def ab_test_detail(request, test_id):
    """View A/B test with variant comparison."""
    from apps.content.models import ABTest

    ab_test = get_object_or_404(
        ABTest.objects.select_related("social_account", "seed", "winner"),
        id=test_id, user=request.user,
    )

    variants = (
        ab_test.variants.select_related("social_account", "metrics")
        .order_by("variant_label")
    )

    # Build comparison data
    variant_data = []
    for v in variants:
        entry = {
            "post": v,
            "metrics": None,
            "total_engagement": 0,
        }
        try:
            m = v.metrics
            entry["metrics"] = m
            entry["total_engagement"] = m.likes + m.comments + m.shares + m.saves
        except Exception:
            pass
        variant_data.append(entry)

    return render(request, "content/ab_tests/detail.html", {
        "ab_test": ab_test,
        "variant_data": variant_data,
        "page_title": f"A/B Test: {ab_test.name[:50]}",
    })


@login_required
@require_POST
def ab_test_conclude(request, test_id):
    """Manually conclude an A/B test (evaluate and pick winner)."""
    from apps.content.models import ABTest
    from apps.agents.analyst_agent import evaluate_ab_test

    ab_test = get_object_or_404(ABTest, id=test_id, user=request.user)

    if ab_test.status not in (ABTest.Status.RUNNING, ABTest.Status.DRAFT):
        messages.info(request, "This test has already been concluded.")
        return redirect("content:ab_test_detail", test_id=ab_test.id)

    result = evaluate_ab_test(ab_test)

    if "error" in result:
        messages.warning(request, result["error"])
    else:
        messages.success(
            request,
            f"Test concluded! Variant {result['winner_label']} wins."
        )

    return redirect("content:ab_test_detail", test_id=ab_test.id)


@login_required
@require_POST
def ab_test_start(request, test_id):
    """Mark an A/B test as running (after user publishes all variants)."""
    from apps.content.models import ABTest
    from django.utils import timezone as tz

    ab_test = get_object_or_404(ABTest, id=test_id, user=request.user)

    if ab_test.status != ABTest.Status.DRAFT:
        messages.info(request, "This test is not in draft state.")
        return redirect("content:ab_test_detail", test_id=ab_test.id)

    # Check that at least 2 variants are approved/scheduled/published
    ready = ab_test.variants.filter(
        status__in=[Post.Status.APPROVED, Post.Status.SCHEDULED, Post.Status.PUBLISHED]
    ).count()

    if ready < 2:
        messages.error(request, "Approve at least 2 variants before starting the test.")
        return redirect("content:ab_test_detail", test_id=ab_test.id)

    ab_test.status = ABTest.Status.RUNNING
    ab_test.started_at = tz.now()
    ab_test.save(update_fields=["status", "started_at", "updated_at"])

    messages.success(request, f"A/B test started! Results will be evaluated in {ab_test.test_duration_hours} hours.")
    return redirect("content:ab_test_detail", test_id=ab_test.id)


@login_required
@require_POST
def ab_test_cancel(request, test_id):
    """Cancel an A/B test."""
    from apps.content.models import ABTest

    ab_test = get_object_or_404(ABTest, id=test_id, user=request.user)

    if ab_test.status in (ABTest.Status.CONCLUDED,):
        messages.info(request, "Cannot cancel a concluded test.")
        return redirect("content:ab_test_detail", test_id=ab_test.id)

    ab_test.status = ABTest.Status.CANCELLED
    ab_test.save(update_fields=["status", "updated_at"])

    messages.success(request, "A/B test cancelled.")
    return redirect("content:ab_test_list")


# ─── VOICE TO CAMPAIGN ──────────────────────────────────────────────────────


@login_required
def voice_campaign(request):
    """Listen & Launch — cross-channel campaigns from voice or text."""
    from django.urls import reverse

    from apps.campaigns.models import Campaign
    from apps.content.models import VoiceBrief
    from apps.content.tasks import process_voice_brief
    from apps.campaigns.tasks import ai_build_campaign

    if request.method == "POST":
        action = request.POST.get("action", "voice")

        if action == "prompt":
            prompt = request.POST.get("prompt", "").strip()
            if not prompt:
                messages.error(request, "Describe what you want your campaign to achieve.")
                return redirect("content:voice_campaign")

            duration = request.POST.get("duration_days", "7")
            try:
                duration_days = max(1, min(int(duration), 90))
            except (ValueError, TypeError):
                duration_days = 7

            include_email = request.POST.get("include_email") == "on"
            include_status = request.POST.get("include_whatsapp_status") == "on"
            fire_task(
                ai_build_campaign,
                str(request.user.id),
                prompt,
                duration_days,
                include_email,
                include_status,
            )
            channels = ["social Queue"]
            if include_email:
                channels.append("email")
            if include_status:
                channels.append("WhatsApp Status")
            messages.success(
                request,
                f"Listen & Launch is building your campaign — {' + '.join(channels)}.",
            )
            return redirect("content:voice_campaign")

        audio = request.FILES.get("audio")
        if not audio:
            messages.error(request, "Please upload or record an audio clip.")
            return redirect("content:voice_campaign")

        allowed_types = [
            "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
            "audio/ogg", "audio/webm", "audio/mp4", "audio/m4a",
            "audio/x-m4a",
        ]
        if audio.content_type not in allowed_types and not audio.name.endswith(
            (".mp3", ".wav", ".ogg", ".webm", ".m4a")
        ):
            messages.error(request, "Unsupported audio format. Use MP3, WAV, OGG, WebM, or M4A.")
            return redirect("content:voice_campaign")

        if audio.size > 25 * 1024 * 1024:
            messages.error(request, "Audio file too large. Maximum 25 MB.")
            return redirect("content:voice_campaign")

        vb = VoiceBrief.objects.create(user=request.user, audio_file=audio)
        fire_task(process_voice_brief, str(vb.pk))
        messages.success(
            request,
            "Voice captured! Listen & Launch is transcribing and building across your channels.",
        )
        return redirect("content:voice_campaign")

    briefs = (
        VoiceBrief.objects
        .filter(user=request.user)
        .select_related("campaign", "email_campaign")
        .order_by("-created_at")[:20]
    )
    campaigns = (
        Campaign.objects
        .filter(user=request.user)
        .order_by("-created_at")[:15]
    )

    return render(request, "content/voice_campaign.html", {
        "briefs": briefs,
        "campaigns": campaigns,
        "transcribe_url": reverse("content:voice_campaign_transcribe"),
    })


@login_required
@require_POST
def voice_campaign_transcribe(request):
    """Transcribe live mic audio for Listen & Launch prompt field."""
    from apps.content.voice import transcribe_audio

    audio = request.FILES.get("audio")
    if not audio:
        return JsonResponse({"error": "No audio file provided."}, status=400)

    content_type = audio.content_type or "audio/webm"
    result = transcribe_audio(audio, content_type)
    if result.get("error"):
        return JsonResponse({"error": result["error"]}, status=400)
    return JsonResponse({"text": result.get("text", ""), "duration": result.get("duration")})


# ─── AUTOPILOT ──────────────────────────────────────────────────────────────

@login_required
def autopilot_dashboard(request):
    """Autopilot overview: preview plans, approve strategy, track execution."""
    from apps.content.autopilot import (
        AUTOPILOT_ACTIVE_STATUSES,
        _next_monday,
        get_plan_live_stats,
        log_plan_step,
        plan_user_week,
        recover_stale_planning,
        _planning_worker_started,
    )
    from apps.content.models import WeeklyContentPlan
    from django.urls import reverse

    profile = request.user.profile
    plans = list(
        WeeklyContentPlan.objects.filter(user=request.user)
        .order_by("-week_start")[:20]
    )
    for p in plans:
        if p.status == WeeklyContentPlan.Status.PLANNING:
            recover_stale_planning(p)
    current_plan = next(
        (p for p in plans if p.status in AUTOPILOT_ACTIVE_STATUSES),
        None,
    )
    pending_plan = next(
        (p for p in plans if p.status == WeeklyContentPlan.Status.PENDING_REVIEW),
        None,
    )
    planning_plan = next(
        (p for p in plans if p.status == WeeklyContentPlan.Status.PLANNING),
        None,
    )
    plan_stats = {str(p.pk): get_plan_live_stats(p) for p in plans}
    current_plan_stats = plan_stats.get(str(current_plan.pk), {}) if current_plan else {}
    plans_with_stats = [{"plan": p, "stats": plan_stats.get(str(p.pk), {})} for p in plans]

    if request.method == "POST" and request.POST.get("action") == "trigger":
        from datetime import timedelta
        from apps.utils import fire_task

        week_start = _next_monday()
        week_end = week_start + timedelta(days=6)
        existing = WeeklyContentPlan.objects.filter(
            user=request.user,
            week_start=week_start,
        ).exclude(
            status__in=[
                WeeklyContentPlan.Status.FAILED,
                WeeklyContentPlan.Status.CANCELLED,
            ],
        ).first()
        if existing:
            if existing.status == WeeklyContentPlan.Status.PLANNING:
                recover_stale_planning(existing)
                existing.refresh_from_db()
                if existing.status == WeeklyContentPlan.Status.PLANNING:
                    if not _planning_worker_started(existing):
                        log_plan_step(
                            existing, "queued",
                            "Restarting your weekly strategy preview.",
                            f"Week of {week_start.strftime('%b %d, %Y')}",
                        )
                        fire_task(
                            plan_user_week,
                            str(request.user.pk),
                            week_start.isoformat(),
                            str(existing.pk),
                        )
                return redirect(f"{reverse('content:autopilot')}?planning={existing.pk}")
            if existing.status == WeeklyContentPlan.Status.PENDING_REVIEW:
                messages.info(
                    request,
                    f"A plan preview for the week of {week_start.strftime('%b %d')} is already waiting for your approval.",
                )
            else:
                messages.info(
                    request,
                    f"You already have an active plan for the week of {week_start.strftime('%b %d')}.",
                )
            return redirect("content:autopilot_detail", plan_id=existing.pk)

        failed_plan = WeeklyContentPlan.objects.filter(
            user=request.user,
            week_start=week_start,
            status=WeeklyContentPlan.Status.FAILED,
        ).first()
        if failed_plan:
            failed_plan.status = WeeklyContentPlan.Status.PLANNING
            failed_plan.error_message = ""
            failed_plan.planning_log = []
            failed_plan.strategy = {}
            failed_plan.strategy_reasoning = ""
            failed_plan.week_end = week_end
            failed_plan.save(update_fields=[
                "status", "error_message", "planning_log", "strategy",
                "strategy_reasoning", "week_end",
            ])
            log_plan_step(
                failed_plan, "queued",
                "Queued your weekly strategy preview.",
                f"Week of {week_start.strftime('%b %d, %Y')}",
            )
            fire_task(
                plan_user_week,
                str(request.user.pk),
                week_start.isoformat(),
                str(failed_plan.pk),
            )
            return redirect(f"{reverse('content:autopilot')}?planning={failed_plan.pk}")

        plan = WeeklyContentPlan.objects.create(
            user=request.user,
            week_start=week_start,
            week_end=week_end,
            status=WeeklyContentPlan.Status.PLANNING,
            planning_log=[],
        )
        log_plan_step(plan, "queued", "Queued your weekly strategy preview.", f"Week of {week_start.strftime('%b %d, %Y')}")
        fire_task(plan_user_week, str(request.user.pk), week_start.isoformat(), str(plan.pk))
        return redirect(f"{reverse('content:autopilot')}?planning={plan.pk}")

    return render(request, "content/autopilot.html", {
        "plans": plans,
        "plans_with_stats": plans_with_stats,
        "current_plan": current_plan,
        "current_plan_stats": current_plan_stats,
        "pending_plan": pending_plan,
        "planning_plan": planning_plan,
        "planning_plan_id": request.GET.get("planning", "") or (str(planning_plan.pk) if planning_plan else ""),
        "autopilot_enabled": profile.autopilot_enabled,
        "auto_approve_posts": profile.auto_approve_posts,
        "autopilot_posts_per_week": profile.autopilot_posts_per_week or 5,
    })


@login_required
def autopilot_plan_status(request, plan_id):
    """JSON status for live planning modal (polled from the dashboard)."""
    from apps.content.autopilot import recover_stale_planning
    from apps.content.models import WeeklyContentPlan
    from django.urls import reverse

    plan = get_object_or_404(WeeklyContentPlan, pk=plan_id, user=request.user)
    recover_stale_planning(plan)
    plan.refresh_from_db()
    strategy = plan.strategy or {}
    topics = strategy.get("daily_topics", [])
    terminal = plan.status in (
        WeeklyContentPlan.Status.PENDING_REVIEW,
        WeeklyContentPlan.Status.FAILED,
        WeeklyContentPlan.Status.CANCELLED,
    )
    return JsonResponse({
        "plan_id": str(plan.pk),
        "status": plan.status,
        "status_label": plan.get_status_display(),
        "week_start": plan.week_start.isoformat(),
        "planning_log": plan.planning_log or [],
        "theme": strategy.get("theme", ""),
        "reasoning": plan.strategy_reasoning or strategy.get("reasoning", ""),
        "content_mix": strategy.get("content_mix", {}),
        "topics": topics,
        "topics_count": len(topics),
        "error_message": plan.error_message,
        "terminal": terminal,
        "detail_url": reverse("content:autopilot_detail", kwargs={"plan_id": plan.pk}),
        "approve_url": reverse("content:autopilot_approve", kwargs={"plan_id": plan.pk}),
    })


@login_required
def autopilot_plan_detail(request, plan_id):
    """View a weekly plan — full strategy preview or generated posts."""
    from apps.content.autopilot import get_plan_live_stats, get_plan_posts
    from apps.content.models import WeeklyContentPlan

    plan = get_object_or_404(WeeklyContentPlan, pk=plan_id, user=request.user)
    profile = request.user.profile
    posts = get_plan_posts(plan)
    live_stats = get_plan_live_stats(plan)

    return render(request, "content/autopilot_detail.html", {
        "plan": plan,
        "posts": posts,
        "live_stats": live_stats,
        "auto_approve_posts": profile.auto_approve_posts,
        "is_preview": plan.status == WeeklyContentPlan.Status.PENDING_REVIEW,
    })


@login_required
@require_POST
def autopilot_approve(request, plan_id):
    """User approved the strategy preview — queue post generation."""
    from apps.content.autopilot import execute_autopilot_plan
    from apps.content.models import WeeklyContentPlan

    plan = get_object_or_404(WeeklyContentPlan, pk=plan_id, user=request.user)
    if plan.status != WeeklyContentPlan.Status.PENDING_REVIEW:
        messages.error(request, "This plan is not waiting for approval.")
        return redirect("content:autopilot_detail", plan_id=plan.pk)

    fire_task(execute_autopilot_plan, str(plan.pk))
    if request.user.profile.auto_approve_posts:
        messages.success(
            request,
            "Strategy approved. Kova is generating and scheduling your posts now.",
        )
    else:
        messages.success(
            request,
            "Strategy approved. Kova is generating your posts — you'll review them in Studio before publishing.",
        )
    return redirect("content:autopilot_detail", plan_id=plan.pk)


@login_required
@require_POST
def autopilot_cancel(request, plan_id):
    """Cancel a pending or active autopilot plan."""
    from apps.content.models import WeeklyContentPlan

    plan = get_object_or_404(WeeklyContentPlan, pk=plan_id, user=request.user)
    cancellable = (
        WeeklyContentPlan.Status.PENDING_REVIEW,
        WeeklyContentPlan.Status.PLANNING,
        WeeklyContentPlan.Status.GENERATING,
        WeeklyContentPlan.Status.SCHEDULING,
        WeeklyContentPlan.Status.ACTIVE,
    )
    if plan.status in cancellable:
        plan.status = WeeklyContentPlan.Status.CANCELLED
        plan.save(update_fields=["status"])
        messages.info(request, "Autopilot plan cancelled.")
    return redirect("content:autopilot")
