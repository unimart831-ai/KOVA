import json
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.content.forms import ContentSeedForm
from apps.content.models import ContentSeed, Post
from apps.content.tasks import generate_from_seed
from apps.teams.permissions import can_approve_post, get_teammate_ids
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
