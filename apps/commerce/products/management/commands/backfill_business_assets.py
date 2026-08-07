"""
Backfill BusinessAsset rows from existing Product catalog.

Usage:
    python manage.py backfill_business_assets
    python manage.py backfill_business_assets --dry-run
    python manage.py backfill_business_assets --user-id 42
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update BusinessAsset records for all active products"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report counts without writing to the database",
        )
        parser.add_argument(
            "--user-id",
            type=int,
            default=None,
            help="Limit backfill to a single user ID",
        )

    def handle(self, *args, **options):
        from apps.commerce.products.business_assets import sync_asset_from_product
        from apps.commerce.products.models import Product

        dry_run = options["dry_run"]
        user_id = options["user_id"]

        qs = Product.objects.filter(is_active=True).select_related("user")
        if user_id:
            qs = qs.filter(user_id=user_id)

        created = 0
        updated = 0
        skipped = 0

        for product in qs.iterator(chunk_size=200):
            if hasattr(product, "business_asset") and product.business_asset_id:
                if dry_run:
                    skipped += 1
                    continue
                sync_asset_from_product(product)
                updated += 1
            else:
                if dry_run:
                    created += 1
                    continue
                sync_asset_from_product(product)
                created += 1

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}BusinessAsset backfill complete: "
                f"{created} created, {updated} updated, {skipped} already linked"
            )
        )
