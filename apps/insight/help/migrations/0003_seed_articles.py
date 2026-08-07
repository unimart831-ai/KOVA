"""
Seed Articles from the static ARTICLES registry in apps.insight.help.views.

All 20 entries are migrated as audience=user, status=published, with
legacy_template pointing at their existing help/articles/{slug}.html so
the cutover PR can render them without porting bodies to markdown.
"""

from django.db import migrations
from django.utils import timezone


SEED = [
    # Getting Started
    ("welcome-to-kova", "Welcome to Kova Agent",
     "An overview of Kova Agent and what it can do for your social media.",
     "getting-started", 1),
    ("connecting-platforms", "Connecting Your Social Platforms",
     "How to connect Facebook, Instagram, Twitter, LinkedIn, TikTok, and more.",
     "getting-started", 2),
    ("setting-up-brand-voice", "Setting Up Your Brand Voice",
     "Configure your brand's tone, audience, and content pillars.",
     "getting-started", 3),

    # Content & Publishing
    ("content-studio", "Using the Content Studio",
     "Create posts from ideas — the AI takes your seed and generates platform-native content.",
     "content", 1),
    ("content-queue", "The Approval Queue",
     "Review, approve, or reject AI-generated posts before they go live.",
     "content", 2),
    ("content-calendar", "Content Calendar & Scheduling",
     "View your publishing timeline and manage scheduled posts.",
     "content", 3),
    ("media-queue", "Media Queue",
     "Upload, organize, and reorder images and videos for your posts.",
     "content", 4),

    # AI Agents
    ("understanding-agents", "Understanding Your AI Agents",
     "Meet the 6 AI agents that power Kova — what each one does and how they work together.",
     "agents", 1),
    ("configuring-agents", "Configuring Agent Behavior",
     "Give custom instructions to your agents and toggle them on or off.",
     "agents", 2),
    ("daily-brief", "Your Daily Brief",
     "The Strategist agent delivers a daily summary of performance, trends, and recommendations.",
     "agents", 3),

    # Analytics & Insights
    ("analytics-insights", "Analytics & Performance Insights",
     "Understand your content performance with AI-powered analytics.",
     "analytics", 1),
    ("competitor-tracking", "Competitor Tracking",
     "Monitor competitor strategies and find content gaps. Available on Pro plan.",
     "analytics", 2),
    ("engagement-inbox", "Engagement Inbox",
     "Manage comments and replies across all platforms from one inbox.",
     "analytics", 3),
    ("kova-pixel", "Kova Pixel — Website Tracking",
     "Track website visitors and attribute conversions back to your social posts.",
     "analytics", 4),
    ("leads", "Lead Capture & Management",
     "Turn social engagement into business opportunities with lead tracking.",
     "analytics", 5),
    ("kova-links", "Kova Links — Bio Link Pages",
     "Create a customizable bio link page with click analytics.",
     "analytics", 6),

    # Account & Billing
    ("plans-and-pricing", "Plans & Pricing",
     "Compare Starter, Growth, Pro, and Agency plans — what's included in each.",
     "account", 1),
    ("managing-your-account", "Managing Your Account",
     "Update your profile, brand settings, timezone, and preferences.",
     "account", 2),
    ("teams-and-brands", "Teams & Multi-Brand Management",
     "Collaborate with team members and manage multiple brands from one account.",
     "account", 3),
    ("faq", "Frequently Asked Questions",
     "Quick answers to common questions about Kova Agent.",
     "account", 4),
]


def seed_articles(apps, schema_editor):
    Article = apps.get_model("help", "Article")
    now = timezone.now()
    for slug, title, excerpt, category, order in SEED:
        Article.objects.update_or_create(
            slug=slug,
            defaults={
                "title": title,
                "excerpt": excerpt,
                "category": category,
                "order": order,
                "audience": "user",
                "status": "published",
                "author_agent": "",
                "legacy_template": f"help/articles/{slug}.html",
                "published_at": now,
            },
        )


def unseed_articles(apps, schema_editor):
    Article = apps.get_model("help", "Article")
    slugs = [row[0] for row in SEED]
    Article.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("help", "0002_article"),
    ]

    operations = [
        migrations.RunPython(seed_articles, unseed_articles),
    ]
