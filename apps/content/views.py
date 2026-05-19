import json
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
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
    from apps.billing.models import get_plan_limits
    user_plan = getattr(getattr(request.user, "profile", None), "plan", "starter")
    plan_limits = get_plan_limits(user_plan)
    can_generate_images = plan_limits.get("ai_image_generation", False)

    all_posts = [p for g in seed_groups for p in g["posts"]] + list(ungrouped)
    pending_images = sum(1 for p in all_posts if p.media_status == "pending")

    return render(request, "content/studio.html", {
        "seed_groups": seed_groups,
        "ungrouped_posts": ungrouped,
        "active_seeds": active_seeds,
        "failed_seeds": failed_seeds,
        "seed_form": seed_form,
        "connected_platforms": json.dumps(connected_platforms),
        "total_pending": total_pending,
        "pending_images": pending_images,
        "seed_suggestions": seed_suggestions,
        "can_generate_images": can_generate_images,
        "current_status": request.GET.get("status", ""),
        "current_platform": request.GET.get("platform", ""),
        "current_format": request.GET.get("post_format", ""),
        "current_search": request.GET.get("q", ""),
        "current_source": request.GET.get("source", ""),
        "page_title": "Content Studio",
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
        posts = posts.filter(content_text__icontains=search_query)
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
            seed_groups.append({
                "seed": seed_obj,
                "posts": seed_posts,
                "platform_count": len(seed_posts),
                "all_pending": all(p.status in ("pending_approval", "draft") for p in seed_posts),
            })

    seed_groups.sort(key=lambda g: g["seed"].created_at, reverse=True)
    return seed_groups, ungrouped, posts.count()


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

    is_htmx = request.headers.get("HX-Request") == "true"

    form = ContentSeedForm(request.POST)
    if form.is_valid():
        seed = form.save(commit=False)
        seed.user = request.user
        seed.save()

        fire_task(generate_from_seed, str(seed.id))

        if is_htmx:
            # Return the processing spinner card that polls for status
            return render(request, "content/_seed_processing.html", {"seed": seed})

        messages.success(request, "Your idea is being processed! Posts will appear below shortly.")
        return redirect("content:studio")

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
    response = render(request, "content/_seed_status.html", {
        "seed": seed,
        "posts": posts,
    })
    # When generation is done, tell the posts section to refresh
    if seed.status in ("completed", "failed"):
        response["HX-Trigger"] = "postsUpdated"
    return response


@login_required
def content_queue(request):
    """View scheduled and published posts, grouped by seed where possible."""
    visible_user_ids = get_teammate_ids(request.user)
    team_posts = Post.objects.filter(user_id__in=visible_user_ids)

    scheduled = team_posts.filter(
        status__in=["approved", "scheduled"]
    ).select_related("social_account", "seed", "user").order_by("scheduled_at")
    publishing = team_posts.filter(
        status="publishing"
    ).select_related("social_account", "seed", "user").order_by("-updated_at")
    failed = team_posts.filter(
        status="failed"
    ).select_related("social_account", "seed", "user").order_by("-updated_at")
    published = team_posts.filter(
        status="published"
    ).select_related("social_account", "seed", "user").order_by("-published_at")[:30]

    def group_by_seed(posts_qs):
        """Group posts into seed batches + ungrouped."""
        grouped = defaultdict(list)
        ungrouped = []
        for post in posts_qs:
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
                if seed_obj:
                    batches.append({"seed": seed_obj, "posts": seed_posts})
        return batches, ungrouped

    scheduled_batches, scheduled_ungrouped = group_by_seed(scheduled)
    published_batches, published_ungrouped = group_by_seed(published)

    return render(request, "content/queue.html", {
        "scheduled_batches": scheduled_batches,
        "scheduled_ungrouped": scheduled_ungrouped,
        "scheduled_count": scheduled.count(),
        "publishing": publishing,
        "failed": failed,
        "published_batches": published_batches,
        "published_ungrouped": published_ungrouped,
        "published_count": published.count(),
        "page_title": "Content Queue",
    })


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

    for post in posts:
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

        # If "post_now" — fire publish tasks
        if intent == "post_now":
            from apps.content.tasks import publish_post
            fire_task(publish_post, str(post.id))

    post_count = posts.count()
    messages.success(request, f"All {post_count} posts approved and scheduled!")
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
    from apps.billing.models import get_plan_limits
    user_plan = getattr(getattr(post.user, "profile", None), "plan", "starter")
    plan_limits = get_plan_limits(user_plan)
    if not plan_limits.get("ai_image_generation", False):
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<span class="text-[10px] font-medium px-2 py-0.5 rounded-md '
                'bg-red-50 text-red-600 dark:bg-red-950 dark:text-red-400">'
                'Upgrade your plan for AI images</span>',
                status=403,
            )
        messages.error(request, "Your plan doesn't include AI image generation.")
        return redirect("content:edit", post_id=post.id)

    # Check monthly limit
    from django.utils import timezone as tz
    monthly_limit = plan_limits.get("ai_images_per_month", 5)
    month_start = tz.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    images_this_month = Post.objects.filter(
        user=post.user, media_status="generated", created_at__gte=month_start,
    ).count()
    if images_this_month >= monthly_limit:
        if request.headers.get("HX-Request"):
            return HttpResponse(
                f'<span class="text-[10px] font-medium px-2 py-0.5 rounded-md '
                f'bg-amber-50 text-amber-600 dark:bg-amber-950 dark:text-amber-400">'
                f'Monthly limit reached ({images_this_month}/{monthly_limit})</span>'
            )
        messages.warning(request, f"Monthly image limit reached ({images_this_month}/{monthly_limit}).")
        return redirect("content:edit", post_id=post.id)

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
    from apps.content.models import ABTest, ContentSeed
    from apps.content.tasks import generate_ab_test_variants
    from apps.platforms.models import SocialAccount

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
    """Upload a voice memo and turn it into a full campaign."""
    from apps.content.models import VoiceBrief
    from apps.content.tasks import process_voice_brief

    if request.method == "POST":
        audio = request.FILES.get("audio")
        if not audio:
            messages.error(request, "Please upload an audio file.")
            return redirect("content:voice_campaign")

        # Basic validation
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

        if audio.size > 25 * 1024 * 1024:  # 25 MB Whisper limit
            messages.error(request, "Audio file too large. Maximum 25 MB.")
            return redirect("content:voice_campaign")

        vb = VoiceBrief.objects.create(user=request.user, audio_file=audio)
        fire_task(process_voice_brief, str(vb.pk))
        messages.success(
            request,
            "Voice memo uploaded! AI is transcribing and building your campaign — "
            "check back in a minute."
        )
        return redirect("content:voice_campaign")

    briefs = (
        VoiceBrief.objects
        .filter(user=request.user)
        .select_related("campaign")
        .order_by("-created_at")[:30]
    )

    return render(request, "content/voice_campaign.html", {
        "briefs": briefs,
    })
