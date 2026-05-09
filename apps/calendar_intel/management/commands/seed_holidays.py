"""
Seed the Holiday table.

Loads curated_moments.yaml + python-holidays for supported countries.
Idempotent — re-run to apply YAML edits.

Usage:
    python manage.py seed_holidays
    python manage.py seed_holidays --curated-only
    python manage.py seed_holidays --library-only
"""
from django.core.management.base import BaseCommand

from apps.calendar_intel.seed_loader import (
    load_curated,
    load_from_python_holidays,
)


class Command(BaseCommand):
    help = "Seed the Holiday table from curated YAML + python-holidays library."

    def add_arguments(self, parser):
        parser.add_argument(
            "--curated-only",
            action="store_true",
            help="Only load from curated_moments.yaml (skip python-holidays).",
        )
        parser.add_argument(
            "--library-only",
            action="store_true",
            help="Only load from python-holidays (skip curated YAML).",
        )

    def handle(self, *args, **options):
        curated_only = options["curated_only"]
        library_only = options["library_only"]

        if not library_only:
            self.stdout.write("Loading curated moments from YAML...")
            n = load_curated()
            self.stdout.write(self.style.SUCCESS(f"  -> {n} curated entries upserted"))

        if not curated_only:
            self.stdout.write("Loading statutory holidays from python-holidays...")
            n = load_from_python_holidays()
            self.stdout.write(self.style.SUCCESS(f"  -> {n} library entries created"))

        self.stdout.write(self.style.SUCCESS("[OK] Holiday seeding complete."))
        self.stdout.write(
            "Next: run `python manage.py rebuild_occurrences` to compute dates."
        )
