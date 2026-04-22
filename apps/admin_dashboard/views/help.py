from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required
from apps.help.models import Article, HelpPageView
from apps.help.views import CATEGORY_META


def _cat_name_map():
    return {cid: meta["name"] for cid, meta in CATEGORY_META.items()}


def _published_articles():
    return Article.objects.filter(status=Article.Status.PUBLISHED)


@staff_required
def help_overview(request):
    """Help center usage overview — views, popular articles, trends."""
    now = timezone.now()
    today = now.date()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # ── Key Metrics ──────────────────────────────────────────────────────
    total_views = HelpPageView.objects.count()
    views_7d = HelpPageView.objects.filter(viewed_at__gte=seven_days_ago).count()
    views_today = HelpPageView.objects.filter(viewed_at__date=today).count()
    unique_users_7d = (
        HelpPageView.objects.filter(viewed_at__gte=seven_days_ago)
        .values("user").distinct().count()
    )

    # Center vs article views (7 days)
    center_views_7d = HelpPageView.objects.filter(
        viewed_at__gte=seven_days_ago, page_type="center",
    ).count()
    article_views_7d = HelpPageView.objects.filter(
        viewed_at__gte=seven_days_ago, page_type="article",
    ).count()

    # ── Article Popularity (top 10, last 30 days) ────────────────────────
    top_articles = list(
        HelpPageView.objects.filter(
            viewed_at__gte=thirty_days_ago, page_type="article",
        )
        .values("article_slug", "article_title", "category")
        .annotate(views=Count("id"))
        .order_by("-views")[:10]
    )
    cat_name_map = _cat_name_map()
    for art in top_articles:
        art["category_name"] = cat_name_map.get(art["category"], art["category"])

    # ── Category Usage (30 days) ─────────────────────────────────────────
    category_stats = list(
        HelpPageView.objects.filter(
            viewed_at__gte=thirty_days_ago, page_type="article",
        )
        .values("category")
        .annotate(views=Count("id"), unique_users=Count("user", distinct=True))
        .order_by("-views")
    )
    for cs in category_stats:
        cs["category_name"] = cat_name_map.get(cs["category"], cs["category"])

    # ── Daily Views Trend (14 days) ──────────────────────────────────────
    fourteen_days_ago = today - timedelta(days=13)
    daily_views_qs = dict(
        HelpPageView.objects.filter(viewed_at__date__gte=fourteen_days_ago)
        .annotate(day=TruncDate("viewed_at"))
        .values("day")
        .annotate(count=Count("id"))
        .values_list("day", "count")
    )
    daily_views = []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        daily_views.append({"date": d.isoformat(), "views": daily_views_qs.get(d, 0)})

    # ── Articles with zero views ─────────────────────────────────────────
    viewed_slugs = set(
        HelpPageView.objects.filter(page_type="article")
        .values_list("article_slug", flat=True).distinct()
    )
    unviewed_articles = [
        {
            "slug": a.slug,
            "title": a.title,
            "category": a.category,
            "category_name": cat_name_map.get(a.category, a.category),
        }
        for a in _published_articles().exclude(slug__in=viewed_slugs)
    ]

    # ── Top Users (most help views, 30 days) ─────────────────────────────
    top_users = list(
        HelpPageView.objects.filter(viewed_at__gte=thirty_days_ago)
        .values("user__email", "user__full_name")
        .annotate(views=Count("id"))
        .order_by("-views")[:10]
    )

    context = {
        "page_title": "Help Center",
        "total_views": total_views,
        "views_7d": views_7d,
        "views_today": views_today,
        "unique_users_7d": unique_users_7d,
        "center_views_7d": center_views_7d,
        "article_views_7d": article_views_7d,
        "top_articles": top_articles,
        "category_stats": category_stats,
        "daily_views_json": daily_views,
        "unviewed_articles": unviewed_articles,
        "top_users": top_users,
        "total_articles": _published_articles().count(),
        "total_categories": len(CATEGORY_META),
    }
    return render(request, "admin_dashboard/help/overview.html", context)


@staff_required
def help_article_views(request):
    """Per-article view breakdown with search and pagination."""
    thirty_days_ago = timezone.now() - timedelta(days=30)

    view_counts = dict(
        HelpPageView.objects.filter(
            viewed_at__gte=thirty_days_ago, page_type="article",
        )
        .values("article_slug")
        .annotate(views=Count("id"))
        .values_list("article_slug", "views")
    )
    unique_counts = dict(
        HelpPageView.objects.filter(
            viewed_at__gte=thirty_days_ago, page_type="article",
        )
        .values("article_slug")
        .annotate(unique_users=Count("user", distinct=True))
        .values_list("article_slug", "unique_users")
    )

    cat_name_map = _cat_name_map()
    article_list = [
        {
            "slug": a.slug,
            "title": a.title,
            "category": a.category,
            "category_name": cat_name_map.get(a.category, a.category),
            "views_30d": view_counts.get(a.slug, 0),
            "unique_users_30d": unique_counts.get(a.slug, 0),
        }
        for a in _published_articles()
    ]

    # Search filter
    search = request.GET.get("q", "").strip()
    if search:
        article_list = [
            a for a in article_list
            if search.lower() in a["title"].lower()
            or search.lower() in a["category_name"].lower()
        ]

    # Sort
    sort = request.GET.get("sort", "-views_30d")
    reverse = sort.startswith("-")
    sort_key = sort.lstrip("-")
    if sort_key in ("views_30d", "unique_users_30d", "title"):
        article_list.sort(key=lambda a: a.get(sort_key, 0), reverse=reverse)

    paginator = Paginator(article_list, 20)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "Article Views",
        "page_obj": page,
        "search": search,
        "sort": sort,
        "total_articles": _published_articles().count(),
    }
    return render(request, "admin_dashboard/help/article_views.html", context)


@staff_required
def help_view_log(request):
    """Recent help page view log with pagination."""
    qs = HelpPageView.objects.select_related("user").order_by("-viewed_at")

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(user__email__icontains=search) |
            Q(user__full_name__icontains=search) |
            Q(article_slug__icontains=search) |
            Q(article_title__icontains=search)
        )

    page_type_filter = request.GET.get("type", "")
    if page_type_filter in ("center", "article"):
        qs = qs.filter(page_type=page_type_filter)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "Help View Log",
        "page_obj": page,
        "search": search,
        "type_filter": page_type_filter,
    }
    return render(request, "admin_dashboard/help/view_log.html", context)
