"""
Trigger the Educator agent to draft queued blog articles.

Intended to be called by Celery beat or a cron job:
    python manage.py draft_blog_posts --count 1

Options:
    --count N     Number of articles to draft (default: 1)
    --dry-run     Show backlog state without drafting anything
"""

from django.core.management.base import BaseCommand

from apps.help.models import Article, ArticleTopic


class Command(BaseCommand):
    help = "Draft N articles from the ArticleTopic backlog using the Educator agent."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=1,
            help="How many articles to draft in this run (default: 1).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show backlog state without calling the LLM.",
        )

    def handle(self, *args, **options):
        count = max(1, options["count"])
        dry_run = options["dry_run"]

        pending = ArticleTopic.objects.filter(
            status=ArticleTopic.Status.PENDING,
        ).order_by("-priority", "created_at")
        pending_count = pending.count()

        self.stdout.write(f"Backlog: {pending_count} pending topics")
        self.stdout.write(
            f"Target articles to draft: {count}"
            + (" [DRY RUN]" if dry_run else "")
        )

        if dry_run:
            self.stdout.write("\nTop topics in queue:")
            for t in pending[:count]:
                self.stdout.write(
                    f"  [{t.priority:>3}] [{t.audience}] {t.title}"
                )
            return

        if pending_count == 0:
            self.stdout.write(
                self.style.WARNING(
                    "No pending topics. Run: python manage.py seed_blog_topics"
                )
            )

        from apps.agents.educator_agent import draft_next_topic

        drafted = 0
        for i in range(count):
            self.stdout.write(f"\nDrafting article {i + 1}/{count}…")
            try:
                result = draft_next_topic(min_backlog=2, suggest_batch=8)
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"  Error: {exc}"))
                continue

            if result is None:
                self.stdout.write(
                    self.style.WARNING("  Backlog empty and topic generation failed. Stopping.")
                )
                break

            a = result.article
            drafted += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Created draft [{a.pk}]: {a.title} ({a.reading_minutes} min)"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(f"\nDone — {drafted}/{count} article(s) drafted.")
        )
        self.stdout.write(
            "Review and publish at: /dashboard/blog/"
        )
