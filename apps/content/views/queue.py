import calendar as cal_module
from collections import defaultdict
from datetime import date, datetime as dt

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.content.models import ContentSeed, Post
from apps.teams.permissions import can_approve_post, get_teammate_ids
from apps.utils import fire_task


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

    raw_by_date = defaultdict(list)
    for post in scheduled_posts:
        raw_by_date[post.scheduled_at.date()].append(post)

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
def content_calendar_grid(request):
    """Visual monthly calendar grid showing posts by day."""
    today = date.today()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    if month < 1:
        month, year = 12, year - 1
    elif month > 12:
        month, year = 1, year + 1

    cal = cal_module.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(year, month)

    month_start = date(year, month, 1)
    month_end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    visible_user_ids = get_teammate_ids(request.user)
    posts = (
        Post.objects.filter(
            user_id__in=visible_user_ids,
            scheduled_at__date__gte=month_start,
            scheduled_at__date__lt=month_end,
            status__in=["approved", "scheduled", "published", "pending_approval"],
        )
        .select_related("social_account")
        .order_by("scheduled_at")
    )

    posts_by_date = defaultdict(list)
    for post in posts:
        posts_by_date[post.scheduled_at.date()].append(post)

    for week in weeks:
        for i, day in enumerate(week):
            week[i] = {
                "date": day,
                "in_month": day.month == month,
                "is_today": day == today,
                "posts": posts_by_date.get(day, []),
            }

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    ctx = {
        "page_title": "Content Calendar",
        "weeks": weeks,
        "year": year,
        "month": month,
        "month_name": cal_module.month_name[month],
        "today": today,
        "prev_month": prev_month,
        "prev_year": prev_year,
        "next_month": next_month,
        "next_year": next_year,
        "total_scheduled": posts.count(),
    }

    if request.headers.get("HX-Request"):
        return render(request, "content/_calendar_grid.html", ctx)
    return render(request, "content/calendar_grid.html", ctx)


def _has_team_access(user, post):
    try:
        from apps.teams.models import get_teammate_ids
        return post.user_id in get_teammate_ids(user)
    except Exception:
        return False


@login_required
@login_required
@require_POST
def reschedule_post(request, post_id):
    """Move a scheduled post to a new time. JSON or form POST."""
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


def approve_post(request, post_id):
    """Approve a post with intent-based scheduling."""
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

    if intent == "post_now":
        from apps.content.tasks import publish_post
        fire_task(publish_post, str(post.id))

    if is_htmx:
        return render(request, "components/post_card.html", {"post": post})
    return redirect("content:post_detail", post_id=post.id)


@login_required
def batch_approve(request, seed_id):
    """Approve ALL posts from a seed at once with the same scheduling intent."""
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
