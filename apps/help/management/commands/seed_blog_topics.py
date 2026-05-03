"""
Seed the ArticleTopic backlog with high-value prospect-facing topics.

Run once to bootstrap the blog pipeline:
    python manage.py seed_blog_topics

Idempotent — uses get_or_create so safe to run multiple times.
"""

from django.core.management.base import BaseCommand

from apps.help.models import Article, ArticleTopic


SEED_TOPICS = [
    # Social media strategy for African SMBs
    {
        "title": "Why African SMBs Lose Customers on Social Media (And How to Stop)",
        "audience": Article.Audience.PROSPECT,
        "category": Article.Category.TIPS,
        "priority": 90,
        "rationale": "High-intent prospect content addressing the core pain point that drives signups.",
    },
    {
        "title": "The 3-Post-a-Week Formula That Works for Small Businesses in Africa",
        "audience": Article.Audience.PROSPECT,
        "category": Article.Category.TIPS,
        "priority": 88,
        "rationale": "Actionable cadence advice for time-strapped SMB owners — directly positions Kova as the solution.",
    },
    {
        "title": "Instagram vs Facebook vs WhatsApp: Which Platform Drives the Most Sales for African SMBs?",
        "audience": Article.Audience.PROSPECT,
        "category": Article.Category.TIPS,
        "priority": 87,
        "rationale": "Comparison content that prospects search for, naturally routes to Kova's multi-platform positioning.",
    },
    {
        "title": "How a Nairobi Fashion Brand Got 3,000 Followers in 30 Days With AI-Assisted Content",
        "audience": Article.Audience.PROSPECT,
        "category": Article.Category.TIPS,
        "priority": 85,
        "rationale": "Story-driven case study format — high shareability and SEO value for target market.",
    },
    {
        "title": "What to Post When You Have Nothing to Post: 15 Content Ideas for African Small Businesses",
        "audience": Article.Audience.PROSPECT,
        "category": Article.Category.CONTENT,
        "priority": 84,
        "rationale": "One of the most searched queries by SMB owners — evergreen listicle with strong SEO.",
    },
    {
        "title": "How to Write Captions That Sell (Without Sounding Salesy)",
        "audience": Article.Audience.PROSPECT,
        "category": Article.Category.CONTENT,
        "priority": 83,
        "rationale": "Core copywriting skill that directly showcases what Kova's AI does better than manual effort.",
    },
    {
        "title": "The Best Times to Post on Instagram, Facebook, and X for East and West Africa",
        "audience": Article.Audience.PROSPECT,
        "category": Article.Category.ANALYTICS,
        "priority": 82,
        "rationale": "Data-driven content that positions Kova as the source of African market intelligence.",
    },
    {
        "title": "Why Your Competitor's Posts Get 10x More Engagement (And What to Do About It)",
        "audience": Article.Audience.PROSPECT,
        "category": Article.Category.ANALYTICS,
        "priority": 80,
        "rationale": "Competitor-focused framing triggers urgency; directly links to Kova's competitor intelligence features.",
    },
    {
        "title": "Social Media for Food Businesses in Africa: A Complete 2026 Playbook",
        "audience": Article.Audience.PROSPECT,
        "category": Article.Category.TIPS,
        "priority": 79,
        "rationale": "Vertical-specific guide for the largest SMB segment in Africa. Strong SEO long-tail target.",
    },
    {
        "title": "How to Use WhatsApp Business to Turn Followers Into Paying Customers",
        "audience": Article.Audience.PROSPECT,
        "category": Article.Category.TIPS,
        "priority": 78,
        "rationale": "WhatsApp is the primary commerce channel in many African markets — high relevance, high intent.",
    },
    {
        "title": "AI Content Tools for Small Business Owners: What Actually Works in 2026",
        "audience": Article.Audience.PROSPECT,
        "category": Article.Category.TIPS,
        "priority": 77,
        "rationale": "Category comparison content that captures prospects evaluating AI tools — Kova's primary acquisition moment.",
    },
    {
        "title": "The Real Reason Your Social Media Isn't Converting to Sales",
        "audience": Article.Audience.PROSPECT,
        "category": Article.Category.TIPS,
        "priority": 76,
        "rationale": "Pain-point headline format performs strongly in organic search and social sharing.",
    },
    {
        "title": "How to Build a Content Calendar as a Solo Business Owner (Free Template Inside)",
        "audience": Article.Audience.PROSPECT,
        "category": Article.Category.CONTENT,
        "priority": 75,
        "rationale": "Practical tool-based content — high engagement, positions Kova's scheduling features.",
    },
    {
        "title": "Social Media Marketing on a Tight Budget: How African MSMEs Can Compete",
        "audience": Article.Audience.PROSPECT,
        "category": Article.Category.TIPS,
        "priority": 74,
        "rationale": "Budget framing speaks directly to the core Kova prospect — bootstrapped African SMB owner.",
    },
    {
        "title": "How to Grow From 0 to 1,000 Followers on Instagram Without Paid Ads",
        "audience": Article.Audience.PROSPECT,
        "category": Article.Category.TIPS,
        "priority": 72,
        "rationale": "One of the most searched social media growth queries globally — strong SEO acquisition potential.",
    },
]


class Command(BaseCommand):
    help = "Seed the ArticleTopic backlog with prospect-facing blog topics."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be created without actually inserting.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        created_count = 0
        skipped_count = 0

        for item in SEED_TOPICS:
            title = item["title"]
            if dry_run:
                exists = ArticleTopic.objects.filter(title=title).exists()
                self.stdout.write(
                    f"  {'EXISTS ' if exists else 'CREATE '} [{item['priority']:>3}] {title}"
                )
                continue

            _, was_created = ArticleTopic.objects.get_or_create(
                title=title,
                defaults={
                    "rationale": item["rationale"],
                    "suggested_category": item["category"],
                    "audience": item["audience"],
                    "priority": item["priority"],
                    "source": ArticleTopic.Source.MANUAL,
                },
            )
            if was_created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"  Created: {title}"))
            else:
                skipped_count += 1
                self.stdout.write(f"  Exists:  {title}")

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nDone — {created_count} topics created, {skipped_count} already existed."
                )
            )
