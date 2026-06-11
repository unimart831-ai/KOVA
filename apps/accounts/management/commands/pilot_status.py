"""List TEST_BUSINESSES slugs and pilot readiness.

Usage:
    python manage.py pilot_status
    python manage.py pilot_status --wave1
    python manage.py pilot_status --json
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.accounts.pilot_metrics import compute_pilot_readiness
from apps.accounts.test_businesses import TEST_BUSINESS_REGISTRY, TEST_BUSINESS_EMAILS, WAVE1_SLUGS


class Command(BaseCommand):
    help = "List 14 TEST_BUSINESSES slugs with seed/readiness status (see docs/TEST_BUSINESSES.md)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--wave1", action="store_true",
            help="Only show Wave 1 pilot businesses (kawaida, mara, nyama).",
        )
        parser.add_argument(
            "--json", action="store_true",
            help="Output JSON instead of a table.",
        )

    def handle(self, *args, **options):
        targets = TEST_BUSINESS_REGISTRY
        if options["wave1"]:
            targets = [b for b in targets if b["slug"] in WAVE1_SLUGS]

        users = {
            u.email: u
            for u in User.objects.filter(email__in=TEST_BUSINESS_EMAILS)
        }

        rows = [
            compute_pilot_readiness(meta, users.get(meta["email"]))
            for meta in targets
        ]

        if options["json"]:
            self.stdout.write(json.dumps(rows, indent=2))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"TEST_BUSINESSES pilot status ({len(rows)} accounts)"
        ))
        self.stdout.write("")
        self.stdout.write(
            f"{'Slug':12} {'Wave':5} {'Plan':8} {'Readiness':22} {'Wedge':6} {'Company'}"
        )
        self.stdout.write("-" * 72)

        for row in rows:
            wave = str(row.get("wave") or "-")
            wedge = f"{row['wedge_percent']}%" if row["seeded"] else "-"
            style = self.style.SUCCESS if row["readiness"] == "pilot_ready" else self.style.WARNING
            if row["readiness"] == "not_seeded":
                style = self.style.ERROR
            line = (
                f"{row['slug']:12} {wave:5} {row['plan']:8} "
                f"{row['readiness']:22} {wedge:6} {row['company_name']}"
            )
            self.stdout.write(style(line))

        seeded = sum(1 for r in rows if r["seeded"])
        ready = sum(1 for r in rows if r["readiness"] == "pilot_ready")
        self.stdout.write("")
        self.stdout.write(f"Seeded: {seeded}/{len(rows)}  |  Pilot-ready: {ready}/{len(rows)}")
        self.stdout.write("")
        self.stdout.write("Seed missing accounts: python manage.py seed_test_businesses")
        self.stdout.write("Full pilot dashboard: /dashboard/pilot/")
