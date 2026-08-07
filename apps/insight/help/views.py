import json

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from apps.insight.help.models import Article, HelpPageView, NewsletterSubscriber


# ── Category UI metadata ─────────────────────────────────────────────────────
# Icon SVG path + colour keyed by Article.Category value. Kept in Python
# (not in the DB) because it's presentational, not content.

CATEGORY_META = {
    "getting-started": {
        "name": "Getting Started",
        "icon": '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>',
        "color": "kova",
    },
    "content": {
        "name": "Content & Publishing",
        "icon": '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>',
        "color": "blue",
    },
    "agents": {
        "name": "AI Agents",
        "icon": '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>',
        "color": "purple",
    },
    "analytics": {
        "name": "Analytics & Insights",
        "icon": '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>',
        "color": "emerald",
    },
    "account": {
        "name": "Account & Billing",
        "icon": '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>',
        "color": "amber",
    },
    "tips": {
        "name": "Tips & Best Practices",
        "icon": '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>',
        "color": "yellow",
    },
    "product-updates": {
        "name": "Product Updates",
        "icon": '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>',
        "color": "pink",
    },
}


# ── Internal helpers ─────────────────────────────────────────────────────────


def _user_visible_articles():
    """Articles that should appear in /help/ and /learn/ (user + prospect blog
    is a separate surface — see Epic 2)."""
    return Article.objects.filter(
        status=Article.Status.PUBLISHED,
        audience__in=[Article.Audience.USER, Article.Audience.BOTH],
    )


def _group_by_category(articles):
    """Group a queryset/list of Articles by category in CATEGORY_META order."""
    buckets: dict[str, list[Article]] = {}
    for article in articles:
        buckets.setdefault(article.category, []).append(article)

    grouped = []
    for cat_id, meta in CATEGORY_META.items():
        cat_articles = buckets.get(cat_id)
        if not cat_articles:
            continue
        cat_articles.sort(key=lambda a: (a.order, a.title))
        grouped.append({
            "category": {"id": cat_id, **meta},
            "articles": cat_articles,
        })
    return grouped


def _search_payload(articles):
    """JSON payload consumed by the Alpine search widget."""
    return [
        {
            "slug": a.slug,
            "title": a.title,
            "description": a.excerpt,
            "category": a.category,
        }
        for a in articles
    ]


def _sibling_nav(article):
    """Return (prev_article, next_article) within the same category."""
    siblings = list(
        _user_visible_articles()
        .filter(category=article.category)
        .order_by("order", "title")
    )
    try:
        idx = next(i for i, a in enumerate(siblings) if a.slug == article.slug)
    except StopIteration:
        return None, None
    prev_article = siblings[idx - 1] if idx > 0 else None
    next_article = siblings[idx + 1] if idx < len(siblings) - 1 else None
    return prev_article, next_article


def _get_visible_article_or_404(slug):
    article = get_object_or_404(_user_visible_articles(), slug=slug)
    return article


# ── Authenticated (in-product) help views ────────────────────────────────────


@login_required
def help_center(request):
    HelpPageView.objects.create(user=request.user, page_type="center")

    articles = list(_user_visible_articles())
    return render(request, "help/index.html", {
        "grouped_articles": _group_by_category(articles),
        "articles_json": mark_safe(json.dumps(_search_payload(articles))),
    })


@login_required
def help_article(request, slug):
    article = _get_visible_article_or_404(slug)
    category_meta = CATEGORY_META.get(article.category, {"name": article.category})
    category = {"id": article.category, **category_meta}
    prev_article, next_article = _sibling_nav(article)

    HelpPageView.objects.create(
        user=request.user,
        page_type="article",
        article_slug=slug,
        article_title=article.title,
        category=article.category,
    )

    return render(request, "help/article.html", {
        "article": article,
        "category": category,
        "prev_article": prev_article,
        "next_article": next_article,
    })


@login_required
def system_maps_index(request):
    """Redirect legacy URL — staff use admin dashboard."""
    if request.user.is_staff:
        return redirect("admin_dashboard:system_maps")
    return redirect("help:center")


@login_required
def system_map_detail(request, slug):
    if request.user.is_staff:
        return redirect("admin_dashboard:system_map", slug=slug)
    return redirect("help:center")


@login_required
def system_maps_print(request):
    if request.user.is_staff:
        return redirect("admin_dashboard:system_maps_print")
    return redirect("help:center")


# ── Public (unauthenticated) /learn/ views ───────────────────────────────────


def public_help_center(request):
    articles = list(_user_visible_articles())
    if request.user.is_authenticated:
        HelpPageView.objects.create(user=request.user, page_type="center")

    return render(request, "help/public_index.html", {
        "grouped_articles": _group_by_category(articles),
        "articles_json": mark_safe(json.dumps(_search_payload(articles))),
    })


# ── Public /blog/ views (prospect + both audience) ───────────────────────────


def _prospect_visible_articles():
    return Article.objects.filter(
        status=Article.Status.PUBLISHED,
        audience__in=[Article.Audience.PROSPECT, Article.Audience.BOTH],
    )


def _blog_category_pills(active: str = ""):
    """Build the filter pill list with counts for the current blog corpus."""
    counts = dict(
        _prospect_visible_articles()
        .values("category")
        .annotate(c=Count("id"))
        .values_list("category", "c")
    )
    total = sum(counts.values())
    pills = [{
        "id": "",
        "name": "All",
        "count": total,
        "active": not active,
    }]
    for cat_id, meta in CATEGORY_META.items():
        n = counts.get(cat_id, 0)
        if not n:
            continue
        pills.append({
            "id": cat_id,
            "name": meta["name"],
            "count": n,
            "active": active == cat_id,
        })
    return pills


def public_blog_index(request):
    category_filter = request.GET.get("category", "").strip()

    qs = _prospect_visible_articles()
    if category_filter and category_filter in CATEGORY_META:
        qs = qs.filter(category=category_filter)
    articles = list(qs.order_by("-published_at", "title"))

    featured = articles[0] if articles else None
    rest = articles[1:] if articles else []

    return render(request, "blog/index.html", {
        "articles": articles,
        "featured": featured,
        "rest": rest,
        "category_pills": _blog_category_pills(active=category_filter),
        "active_category": category_filter,
        "total_count": _prospect_visible_articles().count(),
    })


def public_blog_article(request, slug):
    article = get_object_or_404(_prospect_visible_articles(), slug=slug)
    category_meta = CATEGORY_META.get(article.category, {"name": article.category})
    category = {"id": article.category, **category_meta}

    # Siblings within the blog surface only
    siblings = list(_prospect_visible_articles().order_by("-published_at", "title"))
    try:
        idx = next(i for i, a in enumerate(siblings) if a.slug == article.slug)
    except StopIteration:
        idx = -1
    prev_article = siblings[idx - 1] if idx > 0 else None
    next_article = siblings[idx + 1] if 0 <= idx < len(siblings) - 1 else None

    # Related — same category, exclude self, newest 3
    related = list(
        _prospect_visible_articles()
        .filter(category=article.category)
        .exclude(pk=article.pk)
        .order_by("-published_at")[:3]
    )

    return render(request, "blog/article.html", {
        "article": article,
        "category": category,
        "prev_article": prev_article,
        "next_article": next_article,
        "related_articles": related,
    })


# ── Newsletter subscribe / unsubscribe ───────────────────────────────────────


@ratelimit(key="ip", rate="5/m", method="POST", block=True)
@require_POST
def blog_subscribe(request):
    """Accept a newsletter signup from the blog. Returns an HTMX-friendly HTML
    fragment on success (swap-in confirmation) or a plain bad-request."""
    email = (request.POST.get("email") or "").strip().lower()
    source_slug = (request.POST.get("source_slug") or "").strip()[:120]
    source = NewsletterSubscriber.Source.BLOG
    if source_slug:
        source = NewsletterSubscriber.Source.ARTICLE

    if not email or "@" not in email or len(email) > 254:
        return HttpResponse(
            '<div class="text-sm text-red-600 dark:text-red-400 mt-2">Please enter a valid email address.</div>',
            status=400,
        )

    sub, created = NewsletterSubscriber.objects.get_or_create(
        email=email,
        defaults={"source": source, "source_slug": source_slug},
    )
    if not created and sub.status == NewsletterSubscriber.Status.UNSUBSCRIBED:
        # Re-subscribe a previously-unsubscribed address
        sub.status = NewsletterSubscriber.Status.ACTIVE
        sub.unsubscribed_at = None
        sub.save(update_fields=["status", "unsubscribed_at"])

    return HttpResponse(
        '<div class="rounded-lg bg-green-50 dark:bg-green-950/40 border border-green-200 dark:border-green-900 '
        'px-4 py-3 text-sm text-green-800 dark:text-green-200">'
        "You're in. We'll send the next edition of <strong>Kova Weekly</strong> to "
        f"<strong>{email}</strong>.</div>"
    )


@require_GET
def blog_unsubscribe(request, token):
    try:
        sub = NewsletterSubscriber.objects.get(unsubscribe_token=token)
    except NewsletterSubscriber.DoesNotExist:
        return HttpResponseBadRequest("Invalid or expired link.")
    if sub.status == NewsletterSubscriber.Status.ACTIVE:
        sub.unsubscribe()
    return render(request, "blog/unsubscribed.html", {"email": sub.email})


def public_help_article(request, slug):
    article = _get_visible_article_or_404(slug)
    category_meta = CATEGORY_META.get(article.category, {"name": article.category})
    category = {"id": article.category, **category_meta}
    prev_article, next_article = _sibling_nav(article)

    if request.user.is_authenticated:
        HelpPageView.objects.create(
            user=request.user,
            page_type="article",
            article_slug=slug,
            article_title=article.title,
            category=article.category,
        )

    return render(request, "help/public_article.html", {
        "article": article,
        "category": category,
        "prev_article": prev_article,
        "next_article": next_article,
    })
