from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required
from apps.platforms.models import SocialAccount


@staff_required
def platform_overview(request):
    """Platform health summary — accounts, tokens, publishing stats."""
    now = timezone.now()
    next_24h = now + timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    from apps.content.models import Post

    # Per-platform summary (bulk queries instead of per-platform loops)
    acct_stats = {
        row["platform"]: row
        for row in SocialAccount.objects.values("platform").annotate(
            total=Count("id"),
            active=Count("id", filter=Q(is_active=True)),
            errors=Count("id", filter=~Q(last_error="")),
            expiring=Count("id", filter=Q(
                token_expires_at__isnull=False,
                token_expires_at__lte=next_24h,
                token_expires_at__gt=now,
            )),
        )
    }
    pub_stats = {
        row["social_account__platform"]: row
        for row in Post.objects.filter(
            published_at__gte=last_7d,
            status="published",
        ).values("social_account__platform").annotate(count=Count("id"))
    }
    fail_stats = {
        row["social_account__platform"]: row
        for row in Post.objects.filter(
            updated_at__gte=last_7d,
            status="failed",
        ).values("social_account__platform").annotate(count=Count("id"))
    }

    platforms = []
    for platform_code, platform_label in SocialAccount.Platform.choices:
        row = acct_stats.get(platform_code, {})
        total = row.get("total", 0)
        if total == 0:
            continue
        active = row.get("active", 0)
        errors = row.get("errors", 0)
        expiring = row.get("expiring", 0)
        pub_week = pub_stats.get(platform_code, {}).get("count", 0)
        failed_week = fail_stats.get(platform_code, {}).get("count", 0)

        platforms.append({
            "code": platform_code,
            "label": platform_label,
            "total": total,
            "active": active,
            "inactive": total - active,
            "errors": errors,
            "expiring": expiring,
            "pub_week": pub_week,
            "failed_week": failed_week,
            "success_rate": round(
                pub_week / (pub_week + failed_week) * 100, 1
            ) if (pub_week + failed_week) else 100,
        })

    # Global totals
    total_accounts = SocialAccount.objects.count()
    active_accounts = SocialAccount.objects.filter(is_active=True).count()
    total_errors = SocialAccount.objects.exclude(last_error="").count()
    total_expiring = SocialAccount.objects.filter(
        token_expires_at__isnull=False,
        token_expires_at__lte=next_24h,
        token_expires_at__gt=now,
    ).count()

    # 7-day publishing success rate chart (2 queries instead of 14)
    pub_by_day = dict(
        Post.objects.filter(
            status="published", published_at__date__gte=(now - timedelta(days=6)).date(),
        ).annotate(day=TruncDate("published_at"))
        .values("day").annotate(count=Count("id"))
        .values_list("day", "count")
    )
    fail_by_day = dict(
        Post.objects.filter(
            status="failed", updated_at__date__gte=(now - timedelta(days=6)).date(),
        ).annotate(day=TruncDate("updated_at"))
        .values("day").annotate(count=Count("id"))
        .values_list("day", "count")
    )
    pub_chart = []
    for i in range(6, -1, -1):
        d = (now - timedelta(days=i)).date()
        pub_chart.append({
            "date": d.isoformat(),
            "published": pub_by_day.get(d, 0),
            "failed": fail_by_day.get(d, 0),
        })

    context = {
        "page_title": "Platform Management",
        "platforms": platforms,
        "total_accounts": total_accounts,
        "active_accounts": active_accounts,
        "total_errors": total_errors,
        "total_expiring": total_expiring,
        "pub_chart_json": pub_chart,
    }
    return render(request, "admin_dashboard/platforms/overview.html", context)


@staff_required
def platform_accounts(request):
    """All social accounts with search, filter, sort."""
    qs = SocialAccount.objects.select_related("user").all()

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(username__icontains=search)
            | Q(display_name__icontains=search)
            | Q(user__email__icontains=search)
        )

    platform = request.GET.get("platform", "")
    if platform:
        qs = qs.filter(platform=platform)

    status_filter = request.GET.get("status", "")
    if status_filter == "active":
        qs = qs.filter(is_active=True)
    elif status_filter == "inactive":
        qs = qs.filter(is_active=False)
    elif status_filter == "error":
        qs = qs.exclude(last_error="")
    elif status_filter == "expiring":
        now = timezone.now()
        qs = qs.filter(
            token_expires_at__isnull=False,
            token_expires_at__lte=now + timedelta(hours=24),
            token_expires_at__gt=now,
        )

    qs = qs.annotate(
        post_count=Count(
            "posts", filter=Q(posts__status="published"), distinct=True,
        ),
    )

    sort = request.GET.get("sort", "platform")
    valid_sorts = {
        "platform", "-platform", "username", "-username",
        "connected_at", "-connected_at",
        "token_expires_at", "-token_expires_at",
        "post_count", "-post_count",
    }
    if sort not in valid_sorts:
        sort = "platform"
    qs = qs.order_by(sort)

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "Platform Accounts",
        "page_obj": page,
        "search": search,
        "current_platform": platform,
        "current_status": status_filter,
        "current_sort": sort,
        "total_count": paginator.count,
        "platform_choices": SocialAccount.Platform.choices,
    }
    return render(request, "admin_dashboard/platforms/accounts.html", context)
