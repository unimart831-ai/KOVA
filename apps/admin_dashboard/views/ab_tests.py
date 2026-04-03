from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required


@staff_required
def ab_tests_overview(request):
    """A/B testing overview — test counts, win rates, insights."""
    from apps.content.models import ABTest

    now = timezone.now()
    today = now.date()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    total_tests = ABTest.objects.count()
    tests_by_status = dict(
        ABTest.objects.values_list("status")
        .annotate(c=Count("id"))
        .values_list("status", "c")
    )

    # Recent activity
    tests_7d = ABTest.objects.filter(created_at__gte=seven_days_ago).count()
    concluded_7d = ABTest.objects.filter(
        status="concluded", concluded_at__gte=seven_days_ago,
    ).count()

    # Platform breakdown
    platform_breakdown = list(
        ABTest.objects.values("social_account__platform")
        .annotate(c=Count("id"))
        .order_by("-c")
    )

    # Tests per day (30d chart)
    tests_by_day = dict(
        ABTest.objects.filter(created_at__date__gte=today - timedelta(days=29))
        .annotate(day=TruncDate("created_at"))
        .values("day").annotate(count=Count("id"))
        .values_list("day", "count")
    )
    concluded_by_day = dict(
        ABTest.objects.filter(
            status="concluded",
            concluded_at__date__gte=today - timedelta(days=29),
        ).annotate(day=TruncDate("concluded_at"))
        .values("day").annotate(count=Count("id"))
        .values_list("day", "count")
    )
    chart_data = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        chart_data.append({
            "date": d.isoformat(),
            "created": tests_by_day.get(d, 0),
            "concluded": concluded_by_day.get(d, 0),
        })

    # Average variant count and test duration
    avg_stats = ABTest.objects.aggregate(
        avg_variants=Avg("variant_count"),
        avg_duration=Avg("test_duration_hours"),
    )

    # Top testers (users who create the most tests)
    top_testers = list(
        ABTest.objects.values("user__email", "user__full_name")
        .annotate(test_count=Count("id"))
        .order_by("-test_count")[:10]
    )

    # Currently running tests that are overdue
    overdue_tests = []
    running = ABTest.objects.filter(
        status="running", started_at__isnull=False,
    ).select_related("user", "social_account")
    for test in running:
        if test.is_overdue:
            overdue_tests.append(test)

    context = {
        "page_title": "A/B Tests",
        "total_tests": total_tests,
        "tests_by_status": tests_by_status,
        "tests_7d": tests_7d,
        "concluded_7d": concluded_7d,
        "platform_breakdown": platform_breakdown,
        "chart_data_json": chart_data,
        "avg_variants": round(avg_stats["avg_variants"] or 0, 1),
        "avg_duration": round(avg_stats["avg_duration"] or 0, 0),
        "top_testers": top_testers,
        "overdue_tests": overdue_tests,
    }
    return render(request, "admin_dashboard/ab_tests/overview.html", context)


@staff_required
def ab_test_list_admin(request):
    """All A/B tests with search, filter, sort, pagination."""
    from apps.content.models import ABTest

    qs = ABTest.objects.select_related(
        "user", "social_account", "seed", "winner",
    ).annotate(
        variant_count_actual=Count("variants", distinct=True),
    )

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(user__full_name__icontains=search)
        )

    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)

    platform = request.GET.get("platform", "")
    if platform:
        qs = qs.filter(social_account__platform=platform)

    sort = request.GET.get("sort", "-created_at")
    valid_sorts = {"created_at", "-created_at", "status", "-status"}
    if sort not in valid_sorts:
        sort = "-created_at"
    qs = qs.order_by(sort)

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "All A/B Tests",
        "page_obj": page,
        "search": search,
        "current_status": status,
        "current_platform": platform,
        "current_sort": sort,
        "total_count": paginator.count,
        "status_choices": ABTest.Status.choices,
    }
    return render(request, "admin_dashboard/ab_tests/list.html", context)


@staff_required
def ab_test_detail_admin(request, pk):
    """Single A/B test detail — variants, metrics comparison."""
    from apps.content.models import ABTest

    ab_test = get_object_or_404(
        ABTest.objects.select_related("user", "social_account", "seed", "winner"),
        pk=pk,
    )

    variants = (
        ab_test.variants.select_related("social_account")
        .prefetch_related("metrics")
        .order_by("variant_label")
    )

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

    context = {
        "page_title": f"A/B Test: {ab_test.name[:50]}",
        "ab_test": ab_test,
        "variant_data": variant_data,
    }
    return render(request, "admin_dashboard/ab_tests/detail.html", context)
