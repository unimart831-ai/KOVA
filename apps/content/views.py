import json
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.content.forms import ContentSeedForm, PostEditForm
from apps.content.models import ContentSeed, Post
from apps.content.tasks import generate_from_seed
from apps.teams.permissions import can_approve_post, can_edit_post, get_teammate_ids


@login_required
def content_studio(request):
    """Content creation studio — compose seeds and review AI-generated posts."""
    seed_groups, ungrouped, total_pending = _get_studio_posts(request.user)

    # Recent seeds for processing status
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

    return render(request, "content/studio.html", {
        "seed_groups": seed_groups,
        "ungrouped_posts": ungrouped,
        "active_seeds": active_seeds,
        "failed_seeds": failed_seeds,
        "seed_form": seed_form,
        "connected_platforms": json.dumps(connected_platforms),
        "total_pending": total_pending,
        "seed_suggestions": seed_suggestions,
        "page_title": "Content Studio",
    })


def _get_studio_posts(user):
    """Return (seed_groups, ungrouped, total_pending) for the studio."""
    visible_user_ids = get_teammate_ids(user)
    posts = Post.objects.filter(
        user_id__in=visible_user_ids,
        status__in=["draft", "pending_approval", "rejected"]
    ).select_related("social_account", "seed", "user").order_by("-created_at")

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
    seed_groups, ungrouped, total_pending = _get_studio_posts(request.user)
    return render(request, "content/_studio_posts.html", {
        "seed_groups": seed_groups,
        "ungrouped_posts": ungrouped,
        "total_pending": total_pending,
    })


@login_required
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

        # Fire the Create Agent async (runs sync in dev via CELERY_TASK_ALWAYS_EAGER)
        generate_from_seed.delay(str(seed.id))

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
def dismiss_failed_seeds(request):
    """Clear all failed seeds so they don't clutter the studio."""
    deleted, _ = request.user.content_seeds.filter(status="failed").delete()
    if request.headers.get("HX-Request") == "true":
        return HttpResponse("")
    messages.success(request, f"Cleared {deleted} failed generation(s).")
    return redirect("content:studio")


@login_required
def seed_status(request, seed_id):
    """HTMX endpoint: poll seed processing status."""
    seed = get_object_or_404(ContentSeed, id=seed_id, user=request.user)
    posts = seed.posts.select_related("social_account").all()
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
    scheduled_posts = request.user.posts.filter(
        status__in=["approved", "scheduled", "published"],
        scheduled_at__isnull=False,
    ).select_related("social_account", "seed").order_by("scheduled_at")

    unscheduled_posts = request.user.posts.filter(
        status__in=["approved", "scheduled"],
        scheduled_at__isnull=True,
    ).select_related("social_account", "seed").order_by("-updated_at")

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
    if post.status not in (Post.Status.DRAFT, Post.Status.PENDING_APPROVAL):
        return render(request, "components/post_card.html", {"post": post})

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
        publish_post.delay(str(post.id))

    return render(request, "components/post_card.html", {"post": post})


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
            publish_post.delay(str(post.id))

    post_count = posts.count()
    messages.success(request, f"All {post_count} posts approved and scheduled!")
    return redirect("content:studio")


@login_required
def reject_post(request, post_id):
    """Reject a pending post (HTMX)."""
    post = get_object_or_404(Post.objects.select_related("social_account", "user"), id=post_id)
    if not can_approve_post(request.user, post):
        raise Http404
    if post.status in (Post.Status.DRAFT, Post.Status.PENDING_APPROVAL):
        post.status = Post.Status.REJECTED
        post.save(update_fields=["status", "updated_at"])
    return render(request, "components/post_card.html", {"post": post})


@login_required
def regenerate_post(request, post_id):
    """Regenerate content for a single post via HTMX."""
    from apps.agents.create_agent import regenerate_single_post

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

    try:
        post = regenerate_single_post(post)
    except Exception:
        pass  # Post returned as-is; agent logged the error

    return render(request, "components/post_card.html", {"post": post})


@login_required
def edit_post(request, post_id):
    """Edit a post's content."""
    post = get_object_or_404(Post.objects.select_related("social_account", "seed", "user"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404
    if request.method == "POST":
        form = PostEditForm(request.POST, instance=post)
        if form.is_valid():
            post = form.save(commit=False)
            post.status = Post.Status.DRAFT
            post.save(update_fields=["content_text", "status", "updated_at"])

            # Intelligence: track edit feedback for agent learning
            from apps.agents.memory import record_edit_feedback
            record_edit_feedback(post)

            messages.success(request, "Post updated.")
            return redirect("content:studio")
    else:
        form = PostEditForm(instance=post)

    return render(request, "content/edit.html", {
        "post": post,
        "form": form,
        "page_title": "Edit Post",
    })


@login_required
def upload_media(request, post_id):
    """Upload an image to a post."""
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
        return render(request, "content/_media_item.html", {"attachment": attachment})

    return HttpResponse(status=405)


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
        ).order_by("-created_at")[:10]
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
        generate_ab_test_variants.delay(str(ab_test.id))

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
        ab_test.variants.select_related("social_account")
        .prefetch_related("metrics")
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
