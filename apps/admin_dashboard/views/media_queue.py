"""Admin dashboard views for the Media Queue system."""

from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.admin_dashboard.decorators import staff_required, superuser_required


@staff_required
def media_queue_overview(request):
    """Media Queue admin overview — stats, queue health, recent activity."""
    from apps.media_queue.models import MediaQueue, QueueItem

    now = timezone.now()
    today = now.date()
    seven_days_ago = now - timedelta(days=7)

    # ── Overall stats ────────────────────────────────────────────
    total_queues = MediaQueue.objects.count()
    active_queues = MediaQueue.objects.filter(is_active=True).count()
    paused_queues = total_queues - active_queues

    total_items = QueueItem.objects.count()
    queued_items = QueueItem.objects.filter(status=QueueItem.Status.QUEUED).count()
    published_items = QueueItem.objects.filter(status=QueueItem.Status.PUBLISHED).count()
    failed_items = QueueItem.objects.filter(status=QueueItem.Status.FAILED).count()
    publishing_items = QueueItem.objects.filter(status=QueueItem.Status.PUBLISHING).count()

    # Published in last 7 days
    published_7d = QueueItem.objects.filter(
        status=QueueItem.Status.PUBLISHED,
        published_at__gte=seven_days_ago,
    ).count()

    # Failed in last 7 days
    failed_7d = QueueItem.objects.filter(
        status=QueueItem.Status.FAILED,
        updated_at__gte=seven_days_ago,
    ).count()

    # ── 7-day publish chart ──────────────────────────────────────
    pub_by_day = dict(
        QueueItem.objects
        .filter(status=QueueItem.Status.PUBLISHED, published_at__date__gte=today - timedelta(days=6))
        .annotate(day=TruncDate("published_at"))
        .values("day").annotate(count=Count("id"))
        .values_list("day", "count")
    )
    fail_by_day = dict(
        QueueItem.objects
        .filter(status=QueueItem.Status.FAILED, updated_at__date__gte=today - timedelta(days=6))
        .annotate(day=TruncDate("updated_at"))
        .values("day").annotate(count=Count("id"))
        .values_list("day", "count")
    )
    chart_7d = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        chart_7d.append({
            "date": d.strftime("%b %d"),
            "published": pub_by_day.get(d, 0),
            "failed": fail_by_day.get(d, 0),
        })

    # ── Per-platform breakdown ───────────────────────────────────
    platform_stats = list(
        MediaQueue.objects
        .values(platform=F("social_account__platform"))
        .annotate(
            queue_count=Count("id"),
            total_items=Count("items"),
            queued=Count("items", filter=Q(items__status=QueueItem.Status.QUEUED)),
            published=Count("items", filter=Q(items__status=QueueItem.Status.PUBLISHED)),
            failed=Count("items", filter=Q(items__status=QueueItem.Status.FAILED)),
        )
        .order_by("-queue_count")
    )

    # ── All queues list ──────────────────────────────────────────
    queues = (
        MediaQueue.objects
        .select_related("user", "social_account")
        .annotate(
            total_items=Count("items"),
            items_queued=Count("items", filter=Q(items__status=QueueItem.Status.QUEUED)),
            items_published=Count("items", filter=Q(items__status=QueueItem.Status.PUBLISHED)),
            items_failed=Count("items", filter=Q(items__status=QueueItem.Status.FAILED)),
        )
        .order_by("-created_at")
    )

    # Filter by status
    status_filter = request.GET.get("status", "")
    if status_filter == "active":
        queues = queues.filter(is_active=True)
    elif status_filter == "paused":
        queues = queues.filter(is_active=False)
    elif status_filter == "low":
        # Filter in Python since is_low is a property
        queues = [q for q in queues if q.items_queued <= q.notify_when_low and q.items_queued > 0]

    # Filter by platform
    platform_filter = request.GET.get("platform", "")
    if platform_filter:
        if isinstance(queues, list):
            queues = [q for q in queues if q.social_account.platform == platform_filter]
        else:
            queues = queues.filter(social_account__platform=platform_filter)

    # Search
    search = request.GET.get("q", "")
    if search:
        if isinstance(queues, list):
            s = search.lower()
            queues = [q for q in queues if s in q.user.email.lower() or s in (q.name or "").lower()]
        else:
            queues = queues.filter(
                Q(user__email__icontains=search) | Q(name__icontains=search)
            )

    # Paginate (only if queryset, not filtered list)
    if isinstance(queues, list):
        paginator = Paginator(queues, 25)
    else:
        paginator = Paginator(queues, 25)
    page = paginator.get_page(request.GET.get("page", 1))

    # ── Low queue alerts ─────────────────────────────────────────
    low_queues = (
        MediaQueue.objects
        .filter(is_active=True)
        .select_related("user", "social_account")
        .annotate(items_queued=Count("items", filter=Q(items__status=QueueItem.Status.QUEUED)))
    )
    low_queues = [q for q in low_queues if q.items_queued <= q.notify_when_low and q.is_active]

    # ── Recent failures ──────────────────────────────────────────
    recent_failures = (
        QueueItem.objects
        .filter(status=QueueItem.Status.FAILED)
        .select_related("queue", "queue__user", "queue__social_account")
        .order_by("-updated_at")[:10]
    )

    return render(request, "admin_dashboard/media_queue/overview.html", {
        "total_queues": total_queues,
        "active_queues": active_queues,
        "paused_queues": paused_queues,
        "total_items": total_items,
        "queued_items": queued_items,
        "published_items": published_items,
        "failed_items": failed_items,
        "publishing_items": publishing_items,
        "published_7d": published_7d,
        "failed_7d": failed_7d,
        "chart_7d": chart_7d,
        "platform_stats": platform_stats,
        "page": page,
        "status_filter": status_filter,
        "platform_filter": platform_filter,
        "search": search,
        "low_queues": low_queues,
        "recent_failures": recent_failures,
    })


@staff_required
def media_queue_detail(request, pk):
    """Admin view of a single user's media queue."""
    from apps.media_queue.models import MediaQueue, QueueItem

    queue = get_object_or_404(
        MediaQueue.objects.select_related("user", "social_account"),
        pk=pk,
    )
    queued = queue.items.filter(status=QueueItem.Status.QUEUED).order_by("order")
    published = queue.items.filter(status=QueueItem.Status.PUBLISHED).order_by("-published_at")[:30]
    failed = queue.items.filter(status=QueueItem.Status.FAILED).order_by("-updated_at")

    return render(request, "admin_dashboard/media_queue/detail.html", {
        "queue": queue,
        "queued_items": queued,
        "published_items": published,
        "failed_items": failed,
    })


@superuser_required
@require_POST
def media_queue_toggle(request, pk):
    """Admin toggle queue active/paused."""
    from apps.media_queue.models import MediaQueue

    queue = get_object_or_404(MediaQueue, pk=pk)
    queue.is_active = not queue.is_active
    queue.save(update_fields=["is_active", "updated_at"])

    if request.headers.get("HX-Request"):
        status = "Active" if queue.is_active else "Paused"
        color = "green" if queue.is_active else "amber"
        return HttpResponse(
            f'<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium '
            f'bg-{color}-100 text-{color}-800 dark:bg-{color}-900/30 dark:text-{color}-400">'
            f'{status}</span>'
        )
    from django.shortcuts import redirect
    return redirect("admin_dashboard:media_queue_overview")


@superuser_required
@require_POST
def media_queue_process_now(request):
    """Manually trigger queue processing (for testing/debugging)."""
    from apps.media_queue.tasks import process_media_queues
    result = process_media_queues.delay()
    return JsonResponse({"status": "triggered", "task_id": str(result.id)})
