"""
Management command: backfill selected_page_id for Facebook accounts.

Accounts connected before the selected_page_id fix have pages in metadata
but no selected_page_id set. This command sets it to the first page for all
such accounts so the Active badge displays correctly without requiring a reconnect.

Usage:
    python manage.py backfill_selected_page
    python manage.py backfill_selected_page --dry-run
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Backfill selected_page_id for Facebook accounts missing it"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be changed without saving",
        )

    def handle(self, *args, **options):
        from apps.platforms.models import SocialAccount

        dry_run = options["dry_run"]
        accounts = SocialAccount.objects.filter(
            platform="facebook",
            is_active=True,
        )

        fixed = 0
        skipped = 0
        for account in accounts:
            meta = account.metadata or {}
            pages = meta.get("pages", [])

            if not pages:
                skipped += 1
                continue

            if meta.get("selected_page_id"):
                # Already set — verify it still points to a valid page
                valid_ids = {p["id"] for p in pages}
                if meta["selected_page_id"] in valid_ids:
                    skipped += 1
                    continue
                # selected_page_id points to a page that no longer exists — reset to first
                self.stdout.write(
                    self.style.WARNING(
                        f"  Account {account.id} (@{account.username}): "
                        f"selected_page_id={meta['selected_page_id']} not in pages, resetting"
                    )
                )

            first_page = pages[0]
            self.stdout.write(
                f"  {'[DRY RUN] ' if dry_run else ''}Account {account.id} "
                f"(@{account.username}): set selected_page_id → {first_page['id']} ({first_page['name']})"
            )

            if not dry_run:
                meta["selected_page_id"] = first_page["id"]
                account.metadata = meta
                account.save(update_fields=["metadata", "updated_at"])

            fixed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'[DRY RUN] ' if dry_run else ''}Done: {fixed} accounts updated, {skipped} skipped (already correct)"
            )
        )
