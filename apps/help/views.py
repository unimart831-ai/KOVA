import json

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.utils.safestring import mark_safe

from apps.help.models import HelpPageView

# Article registry — metadata for all help articles
# Each article renders a template at help/articles/{slug}.html
CATEGORIES = [
    {
        "id": "getting-started",
        "name": "Getting Started",
        "icon": '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>',
        "color": "kova",
    },
    {
        "id": "content",
        "name": "Content & Publishing",
        "icon": '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>',
        "color": "blue",
    },
    {
        "id": "agents",
        "name": "AI Agents",
        "icon": '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>',
        "color": "purple",
    },
    {
        "id": "analytics",
        "name": "Analytics & Insights",
        "icon": '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>',
        "color": "emerald",
    },
    {
        "id": "account",
        "name": "Account & Billing",
        "icon": '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>',
        "color": "amber",
    },
]

ARTICLES = [
    # Getting Started
    {
        "slug": "welcome-to-kova",
        "title": "Welcome to Kova Agent",
        "description": "An overview of Kova Agent and what it can do for your social media.",
        "category": "getting-started",
        "order": 1,
    },
    {
        "slug": "connecting-platforms",
        "title": "Connecting Your Social Platforms",
        "description": "How to connect Facebook, Instagram, Twitter, LinkedIn, TikTok, and more.",
        "category": "getting-started",
        "order": 2,
    },
    {
        "slug": "setting-up-brand-voice",
        "title": "Setting Up Your Brand Voice",
        "description": "Configure your brand's tone, audience, and content pillars.",
        "category": "getting-started",
        "order": 3,
    },
    # Content & Publishing
    {
        "slug": "content-studio",
        "title": "Using the Content Studio",
        "description": "Create posts from ideas — the AI takes your seed and generates platform-native content.",
        "category": "content",
        "order": 1,
    },
    {
        "slug": "content-queue",
        "title": "The Approval Queue",
        "description": "Review, approve, or reject AI-generated posts before they go live.",
        "category": "content",
        "order": 2,
    },
    {
        "slug": "content-calendar",
        "title": "Content Calendar & Scheduling",
        "description": "View your publishing timeline and manage scheduled posts.",
        "category": "content",
        "order": 3,
    },
    # AI Agents
    {
        "slug": "understanding-agents",
        "title": "Understanding Your AI Agents",
        "description": "Meet the 6 AI agents that power Kova — what each one does and how they work together.",
        "category": "agents",
        "order": 1,
    },
    {
        "slug": "configuring-agents",
        "title": "Configuring Agent Behavior",
        "description": "Give custom instructions to your agents and toggle them on or off.",
        "category": "agents",
        "order": 2,
    },
    {
        "slug": "daily-brief",
        "title": "Your Daily Brief",
        "description": "The Strategist agent delivers a daily summary of performance, trends, and recommendations.",
        "category": "agents",
        "order": 3,
    },
    # Analytics & Insights
    {
        "slug": "analytics-insights",
        "title": "Analytics & Performance Insights",
        "description": "Understand your content performance with AI-powered analytics.",
        "category": "analytics",
        "order": 1,
    },
    {
        "slug": "competitor-tracking",
        "title": "Competitor Tracking",
        "description": "Monitor competitor strategies and find content gaps. Available on Pro plan.",
        "category": "analytics",
        "order": 2,
    },
    {
        "slug": "engagement-inbox",
        "title": "Engagement Inbox",
        "description": "Manage comments and replies across all platforms from one inbox.",
        "category": "analytics",
        "order": 3,
    },
    # Account & Billing
    {
        "slug": "plans-and-pricing",
        "title": "Plans & Pricing",
        "description": "Compare Starter, Growth, Pro, and Agency plans — what's included in each.",
        "category": "account",
        "order": 1,
    },
    {
        "slug": "managing-your-account",
        "title": "Managing Your Account",
        "description": "Update your profile, brand settings, timezone, and preferences.",
        "category": "account",
        "order": 2,
    },
    {
        "slug": "faq",
        "title": "Frequently Asked Questions",
        "description": "Quick answers to common questions about Kova Agent.",
        "category": "account",
        "order": 3,
    },
]

# Build lookup dicts
_ARTICLE_MAP = {a["slug"]: a for a in ARTICLES}
_CATEGORY_MAP = {c["id"]: c for c in CATEGORIES}


def _get_articles_by_category():
    """Group articles by category for the index page."""
    grouped = []
    for cat in CATEGORIES:
        cat_articles = sorted(
            [a for a in ARTICLES if a["category"] == cat["id"]],
            key=lambda a: a["order"],
        )
        if cat_articles:
            grouped.append({"category": cat, "articles": cat_articles})
    return grouped


@login_required
def help_center(request):
    # Track page view
    HelpPageView.objects.create(user=request.user, page_type="center")

    search_data = [
        {"slug": a["slug"], "title": a["title"], "description": a["description"], "category": a["category"]}
        for a in ARTICLES
    ]
    return render(request, "help/index.html", {
        "grouped_articles": _get_articles_by_category(),
        "articles_json": mark_safe(json.dumps(search_data)),
    })


@login_required
def help_article(request, slug):
    article = _ARTICLE_MAP.get(slug)
    if not article:
        raise Http404("Article not found")

    category = _CATEGORY_MAP.get(article["category"])

    # Find prev/next in same category
    siblings = sorted(
        [a for a in ARTICLES if a["category"] == article["category"]],
        key=lambda a: a["order"],
    )
    idx = next(i for i, a in enumerate(siblings) if a["slug"] == slug)
    prev_article = siblings[idx - 1] if idx > 0 else None
    next_article = siblings[idx + 1] if idx < len(siblings) - 1 else None

    # Track article view
    HelpPageView.objects.create(
        user=request.user,
        page_type="article",
        article_slug=slug,
        article_title=article["title"],
        category=article["category"],
    )

    return render(request, "help/article.html", {
        "article": article,
        "category": category,
        "prev_article": prev_article,
        "next_article": next_article,
        "template_name": f"help/articles/{slug}.html",
    })


# ── Public (unauthenticated) help views ──────────────────────────────────────


def public_help_center(request):
    """Public-facing help center — no login required."""
    search_data = [
        {"slug": a["slug"], "title": a["title"], "description": a["description"], "category": a["category"]}
        for a in ARTICLES
    ]

    # Track view for authenticated users only
    if request.user.is_authenticated:
        HelpPageView.objects.create(user=request.user, page_type="center")

    return render(request, "help/public_index.html", {
        "grouped_articles": _get_articles_by_category(),
        "articles_json": mark_safe(json.dumps(search_data)),
    })


def public_help_article(request, slug):
    """Public-facing article view — no login required."""
    article = _ARTICLE_MAP.get(slug)
    if not article:
        raise Http404("Article not found")

    category = _CATEGORY_MAP.get(article["category"])

    siblings = sorted(
        [a for a in ARTICLES if a["category"] == article["category"]],
        key=lambda a: a["order"],
    )
    idx = next(i for i, a in enumerate(siblings) if a["slug"] == slug)
    prev_article = siblings[idx - 1] if idx > 0 else None
    next_article = siblings[idx + 1] if idx < len(siblings) - 1 else None

    # Track view for authenticated users only
    if request.user.is_authenticated:
        HelpPageView.objects.create(
            user=request.user,
            page_type="article",
            article_slug=slug,
            article_title=article["title"],
            category=article["category"],
        )

    return render(request, "help/public_article.html", {
        "article": article,
        "category": category,
        "prev_article": prev_article,
        "next_article": next_article,
        "template_name": f"help/articles/{slug}.html",
    })
