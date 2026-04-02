from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required


@staff_required
def content_overview(request):
    """Content pipeline overview — seed to publish funnel."""
    from apps.content.models import ContentSeed, Post

    now = timezone.now()
    today = now.date()

    # Pipeline counts
    seed_counts = dict(
        ContentSeed.objects.values_list("status")
        .annotate(c=Count("id"))
        .values_list("status", "c")
    )
    post_counts = dict(
        Post.objects.values_list("status")
        .annotate(c=Count("id"))
        .values_list("status", "c")
    )

    # 7-day throughput
    pipeline_7d = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        pipeline_7d.append({
            "date": d.isoformat(),
            "seeds": ContentSeed.objects.filter(created_at__date=d).count(),
            "generated": Post.objects.filter(created_at__date=d).count(),
            "published": Post.objects.filter(status="published", published_at__date=d).count(),
            "failed": Post.objects.filter(status="failed", updated_at__date=d).count(),
        })

    # Platform breakdown (published posts)
    platform_breakdown = list(
        Post.objects.filter(status="published")
        .values("social_account__platform")
        .annotate(c=Count("id"))
        .order_by("-c")
    )

    # Agent breakdown (who generated posts)
    agent_breakdown = list(
        Post.objects.exclude(generated_by_agent="")
        .values("generated_by_agent")
        .annotate(c=Count("id"))
        .order_by("-c")
    )

    # Content type breakdown
    type_breakdown = list(
        Post.objects.values("content_type")
        .annotate(c=Count("id"))
        .order_by("-c")
    )

    context = {
        "page_title": "Content Pipeline",
        "seed_counts": seed_counts,
        "post_counts": post_counts,
        "total_seeds": sum(seed_counts.values()),
        "total_posts": sum(post_counts.values()),
        "pipeline_7d_json": pipeline_7d,
        "platform_breakdown": platform_breakdown,
        "agent_breakdown": agent_breakdown,
        "type_breakdown": type_breakdown,
    }
    return render(request, "admin_dashboard/content/overview.html", context)


@staff_required
def post_list(request):
    """All posts with search, filter, sort, pagination."""
    from apps.content.models import Post

    qs = Post.objects.select_related("user", "social_account", "seed").all()

    # ── Search ───────────────────────────────────────────────────────────
    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(content_text__icontains=search) |
            Q(user__email__icontains=search) |
            Q(user__full_name__icontains=search)
        )

    # ── Filters ──────────────────────────────────────────────────────────
    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)

    platform = request.GET.get("platform", "")
    if platform:
        qs = qs.filter(social_account__platform=platform)

    agent = request.GET.get("agent", "")
    if agent:
        qs = qs.filter(generated_by_agent__icontains=agent)

    content_type = request.GET.get("type", "")
    if content_type:
        qs = qs.filter(content_type=content_type)

    # ── Sort ─────────────────────────────────────────────────────────────
    sort = request.GET.get("sort", "-created_at")
    valid_sorts = {
        "created_at", "-created_at", "scheduled_at", "-scheduled_at",
        "published_at", "-published_at",
        "predicted_engagement_score", "-predicted_engagement_score",
    }
    if sort not in valid_sorts:
        sort = "-created_at"
    qs = qs.order_by(sort)

    # ── Pagination ───────────────────────────────────────────────────────
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "All Posts",
        "page_obj": page,
        "search": search,
        "current_status": status,
        "current_platform": platform,
        "current_agent": agent,
        "current_type": content_type,
        "current_sort": sort,
        "total_count": paginator.count,
        "status_choices": Post.Status.choices,
        "type_choices": Post.ContentType.choices,
    }
    return render(request, "admin_dashboard/content/posts.html", context)


@staff_required
def seed_list(request):
    """All content seeds with filtering."""
    from apps.content.models import ContentSeed

    qs = ContentSeed.objects.select_related("user").annotate(
        post_count=Count("posts", distinct=True),
    )

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(idea__icontains=search) |
            Q(user__email__icontains=search)
        )

    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)

    qs = qs.order_by("-created_at")

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "Content Seeds",
        "page_obj": page,
        "search": search,
        "current_status": status,
        "total_count": paginator.count,
        "status_choices": ContentSeed.SeedStatus.choices,
    }
    return render(request, "admin_dashboard/content/seeds.html", context)


@staff_required
def failed_content(request):
    """Failed seeds and posts for diagnosis."""
    from apps.content.models import ContentSeed, Post

    failed_posts = (
        Post.objects.filter(status="failed")
        .select_related("user", "social_account")
        .order_by("-updated_at")[:50]
    )
    failed_seeds = (
        ContentSeed.objects.filter(status="failed")
        .select_related("user")
        .order_by("-updated_at")[:50]
    )

    context = {
        "page_title": "Failed Content",
        "failed_posts": failed_posts,
        "failed_seeds": failed_seeds,
        "total_failed_posts": Post.objects.filter(status="failed").count(),
        "total_failed_seeds": ContentSeed.objects.filter(status="failed").count(),
    }
    return render(request, "admin_dashboard/content/failed.html", context)


@staff_required
def post_detail(request, pk):
    """Single post detail view."""
    from apps.analytics.models import PostMetric
    from apps.content.models import Post

    post = get_object_or_404(
        Post.objects.select_related("user", "social_account", "seed"),
        pk=pk,
    )
    metric = PostMetric.objects.filter(post=post).first()
    attachments = post.attachments.all()

    context = {
        "page_title": f"Post Detail",
        "post": post,
        "metric": metric,
        "attachments": attachments,
    }
    return render(request, "admin_dashboard/content/post_detail.html", context)
