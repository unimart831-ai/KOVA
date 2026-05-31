"""Import UNIMART (or any marketplace) sellers and products from CSV files."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.partners.models import MarketplacePartner
from apps.partners.marketplace_csv_import import (
    SELLER_CSV_COLUMNS,
    PRODUCT_CSV_COLUMNS,
    get_marketplace_partner,
    import_products_csv,
    import_sellers_csv,
)


class Command(BaseCommand):
    help = (
        "Import marketplace sellers from CSV (no Partner API). "
        "Optionally import a products CSV keyed by external_seller_id."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "sellers_csv",
            help="Path to sellers CSV file",
        )
        parser.add_argument(
            "--partner-slug",
            default="unimart",
            help="MarketplacePartner slug (default: unimart)",
        )
        parser.add_argument(
            "--products-csv",
            dest="products_csv",
            default="",
            help="Optional products CSV (requires external_seller_id column)",
        )
        parser.add_argument(
            "--create-partner",
            action="store_true",
            help="Create marketplace partner if missing (uses first Partner record)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse CSV and report counts without writing to the database",
        )

    def handle(self, *args, **options):
        slug = options["partner_slug"]
        dry_run = options["dry_run"]

        try:
            mp = get_marketplace_partner(slug, create_if_missing=options["create_partner"])
        except MarketplacePartner.DoesNotExist:
            raise CommandError(
                f"Marketplace '{slug}' not found. Create it in admin or pass --create-partner."
            ) from None
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        if options["create_partner"] and not dry_run:
            self.stdout.write(self.style.WARNING(
                f"Using marketplace partner: {mp.name} (slug={mp.slug})"
            ))

        seller_summary = import_sellers_csv(
            mp, options["sellers_csv"], dry_run=dry_run,
        )
        s = seller_summary.to_dict()["summary"]
        self.stdout.write(
            f"Sellers — provisioned: {s['provisioned']}, "
            f"already_exists: {s['already_exists']}, failed: {s['failed']}, "
            f"pending_queued: {s['pending_added']}"
        )
        for err in seller_summary.errors:
            self.stderr.write(self.style.ERROR(err))
        for row in seller_summary.results:
            if row.get("error"):
                self.stderr.write(
                    self.style.ERROR(
                        f"  row {row.get('index', '?')} {row.get('external_seller_id', '')}: "
                        f"{row['error']}"
                    )
                )

        products_path = options.get("products_csv") or ""
        if products_path:
            product_summary = import_products_csv(mp, products_path, dry_run=dry_run)
            p = product_summary.to_dict()["summary"]
            self.stdout.write(
                f"Products — created: {p['products_created']}, updated: {p['products_updated']}, "
                f"failed: {p['failed']}"
            )
            for err in product_summary.errors:
                self.stderr.write(self.style.ERROR(err))

        if dry_run:
            self.stdout.write(self.style.NOTICE("Dry run — no changes saved."))

        self.stdout.write("")
        self.stdout.write("Expected seller columns: " + ", ".join(SELLER_CSV_COLUMNS))
        if products_path:
            self.stdout.write("Expected product columns: " + ", ".join(PRODUCT_CSV_COLUMNS))
