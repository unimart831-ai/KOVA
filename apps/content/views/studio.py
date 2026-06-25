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
    from apps.billing.models import get_effective_plan_tier, get_user_plan_limits

    profile = getattr(request.user, "profile", None)
    plan_tier = get_effective_plan_tier(profile)
    plan_limits = get_user_plan_limits(request.user)
    is_starter_plan = plan_tier == "starter"

    visible_user_ids = get_teammate_ids(request.user)
    pending_approve_count = Post.objects.filter(
        user_id__in=visible_user_ids,
        status__in=["draft", "pending_approval"],
    ).count()

    status_filter = request.GET.get("status")
    if (
        status_filter is None
        and pending_approve_count > 0
        and not request.GET.get("q")
        and request.GET.get("source") != "holiday"
    ):
        status_filter = "pending_approval"

    seed_groups, ungrouped, total_pending = _get_studio_posts(
        request.user,
        status_filter=status_filter,
        platform_filter=request.GET.get("platform"),
        format_filter=request.GET.get("post_format"),
        search_query=request.GET.get("q"),
        source_filter=request.GET.get("source"),
    )
    approve_first = pending_approve_count > 0

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
    ).select_related("marketing_campaign")[:10]
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

    can_generate_images = plan_limits.get("ai_image_generation", False)

    all_posts = [p for g in seed_groups for p in g["posts"]] + list(ungrouped)
    pending_images = sum(1 for p in all_posts if p.media_status == "pending")

    seed_usage = get_seed_usage(request.user)
    at_seed_limit = seed_usage["at_limit"]
    plan_limit_notice = None
    if at_seed_limit:
        plan_limit_notice = (
            f"You've used all {seed_usage['max']} marketing campaigns this month "
            f"({seed_usage['plan_label']})."
        )

    from apps.products.asset_queries import studio_assets_for_user

    studio_assets = studio_assets_for_user(request.user, limit=8)

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
        "approve_first": approve_first,
        "is_starter_plan": is_starter_plan,
        "pending_approve_count": pending_approve_count,
        "current_status": status_filter or "",
        "current_platform": request.GET.get("platform", ""),
        "current_format": request.GET.get("post_format", ""),
        "current_search": request.GET.get("q", ""),
        "current_source": request.GET.get("source", ""),
        "page_title": "Studio",
        "generating_seed_id": request.GET.get("generating", ""),
        "business_model": getattr(profile, "business_model", ""),
        "studio_assets": studio_assets,
    })


def _get_studio_posts(user, status_filter=None, platform_filter=None, format_filter=None, search_query=None, source_filter=None):
    """Return (seed_groups, ungrouped, total_pending) for the studio."""
    visible_user_ids = get_teammate_ids(user)

    default_statuses = ["draft", "pending_approval", "rejected"]
    filter_statuses = [status_filter] if status_filter and status_filter in dict(Post.Status.choices) else default_statuses

    posts = Post.objects.filter(
        user_id__in=visible_user_ids,
        status__in=filter_statuses,
    ).select_related(
        "social_account", "seed", "seed__product",
        "seed__marketing_campaign", "seed__marketing_campaign__business_asset",
        "user",
    ).order_by("-created_at")

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
    platforms_by_user: dict = {}
    if seeds_map:
        from apps.platforms.models import SocialAccount

        user_ids = {s.user_id for s in seeds_map.values()}
        for row in SocialAccount.objects.filter(
            user_id__in=user_ids, is_active=True,
        ).values("user_id", "platform"):
            platforms_by_user.setdefault(row["user_id"], []).append(row["platform"])

    for seed_id, seed_posts in grouped.items():
        seed_obj = seeds_map.get(seed_id)
        if seed_obj:
            seed_groups.append(_enrich_seed_group(
                seed_obj,
                seed_posts,
                connected_platforms=platforms_by_user.get(seed_obj.user_id, []),
            ))

    seed_groups.sort(key=lambda g: g["seed"].created_at, reverse=True)
    return seed_groups, ungrouped, posts.count()


def _enrich_seed_group(seed_obj, seed_posts, *, connected_platforms=None):
    """Attach batch-approve metadata and campaign context to a seed group."""
    from apps.content.campaigns import campaign_display_label
    from apps.content.campaign_pages import campaign_page_path
    from apps.content.campaign_bundle import bundle_display_for_studio
    from apps.content.campaign_approval import campaign_approval_summary
    from apps.content.campaign_qa import audit_campaign_qa, qa_display_for_studio
    from apps.content.campaign_attribution import campaign_revenue_snapshot
    from apps.content.post_labels import summarize_showcase_types

    pending_statuses = ("pending_approval", "draft")
    minutes_saved = len(seed_posts) * 35
    campaign = getattr(seed_obj, "marketing_campaign", None)
    proposal = (campaign.proposal_meta if campaign else None) or seed_obj.blueprint.get("proposal") or {}
    formats = proposal.get("suggested_formats") or seed_obj.blueprint.get("suggested_formats") or []
    if connected_platforms is None:
        connected_platforms = list(
            seed_obj.user.social_accounts.filter(is_active=True).values_list("platform", flat=True)
        )
    bundle = bundle_display_for_studio(seed_posts, connected_platforms)
    approval = campaign_approval_summary(seed_posts, bundle=bundle)
    qa_report = (
        audit_campaign_qa(campaign, seed_posts, seed_obj.user)
        if campaign and seed_posts
        else None
    )
    qa = qa_display_for_studio(qa_report) if qa_report else None
    revenue = campaign_revenue_snapshot(campaign, seed_obj.user) if campaign else None

    return {
        "seed": seed_obj,
        "campaign": campaign,
        "campaign_title": campaign.title if campaign else seed_obj.idea.split("\n")[0][:200],
        "campaign_objective": campaign.get_objective_display() if campaign else "",
        "campaign_quality": qa_report.overall if qa_report else (campaign.quality_score if campaign else None),
        "campaign_url": campaign_page_path(campaign) if campaign else "",
        "campaign_formats": formats,
        "campaign_rationale": (proposal.get("rationale") or "")[:300],
        "posts": seed_posts,
        "platform_count": len(seed_posts),
        "all_pending": all(p.status in pending_statuses for p in seed_posts),
        "can_batch_approve": approval["can_approve_campaign"],
        "approvable_count": approval["approvable_count"],
        "media_blocked_count": approval["media_blocked_count"],
        "minutes_saved_estimate": minutes_saved,
        "showcase_summary": summarize_showcase_types(seed_posts),
        "bundle": bundle,
        "approval": approval,
        "qa": qa,
        "revenue": revenue,
        "display_label": campaign_display_label(campaign) if campaign else seed_obj.idea[:80],
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

        from apps.content.campaigns import ensure_campaign_for_seed

        ensure_campaign_for_seed(seed, title=seed.idea[:200], objective="awareness")

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
        from apps.content.campaigns import ensure_campaign_for_seed

        ensure_campaign_for_seed(seed, title=text[:200], objective="awareness")
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
