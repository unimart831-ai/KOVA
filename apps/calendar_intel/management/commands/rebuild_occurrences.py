"""
Compute HolidayOccurrence rows for every active Holiday across a year window.

Run on first deploy, after seed_holidays, and on a Celery beat schedule each
January 1 to refresh the next year's dates.

Usage:
    python manage.py rebuild_occurrences                  # current + next year
    python manage.py rebuild_occurrences --years 2026 2027 2028
    python manage.py rebuild_occurrences --prune          # also delete past entries > 2 years old
"""
import logging
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.calendar_intel.date_engine import (
    DateComputationError,
    compute_occurrences,
)
from apps.calendar_intel.models import Holiday, HolidayOccurrence

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Compute HolidayOccurrence rows for active holidays."

    def add_arguments(self, parser):
        parser.add_argument(
            "--years",
            nargs="+",
            type=int,
            help="Years to compute (default: current + next).",
        )
        parser.add_argument(
            "--prune",
            action="store_true",
            help="Also delete occurrences older than 2 years.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Compute but don't save.",
        )

    def handle(self, *args, **options):
        years = options.get("years") or self._default_years()
        dry_run = options["dry_run"]
        prune = options["prune"]

        self.stdout.write(f"Computing occurrences for years: {years}")

        created, updated, skipped, errors = 0, 0, 0, 0

        with transaction.atomic():
            for holiday in Holiday.objects.filter(is_active=True):
                for year in years:
                    try:
                        dates = compute_occurrences(
                            holiday.date_type, holiday.date_config, year,
                        )
                    except DateComputationError as exc:
                        self.stderr.write(
                            self.style.ERROR(
                                f"  [ERR] {holiday.slug} ({year}): {exc}"
                            )
                        )
                        errors += 1
                        continue

                    if not dates:
                        skipped += 1
                        continue

                    # Most holidays have one date; lunar may have two in the
                    # same Gregorian year. Use first match for the (holiday, year)
                    # unique constraint, store others as the next year's row if
                    # they fall in the next year, or as separate logical year+1.
                    primary = dates[0]
                    if dry_run:
                        self.stdout.write(f"  - {holiday.slug} {year} -> {primary}")
                        continue

                    obj, was_created = HolidayOccurrence.objects.update_or_create(
                        holiday=holiday,
                        year=year,
                        defaults={"date": primary, "notes": _build_notes(holiday, dates)},
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1

            if prune and not dry_run:
                cutoff = timezone.now().date().replace(year=timezone.now().year - 2)
                deleted, _ = HolidayOccurrence.objects.filter(date__lt=cutoff).delete()
                self.stdout.write(self.style.WARNING(f"Pruned {deleted} old occurrences."))

            if dry_run:
                # Roll back any accidental DB writes
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f"\n[OK] Done. created={created} updated={updated} skipped={skipped} errors={errors}"
        ))

    def _default_years(self) -> list[int]:
        current = timezone.now().year
        return [current, current + 1]


def _build_notes(holiday: Holiday, dates: list[date]) -> str:
    """Add a caveat note for lunar holidays or multi-occurrence years."""
    if holiday.date_type == "lunar_islamic":
        return "Date is approximate (lunar calendar — may shift ±1 day by region)."
    if len(dates) > 1:
        extras = ", ".join(d.isoformat() for d in dates[1:])
        return f"Additional occurrences this year: {extras}"
    return ""
