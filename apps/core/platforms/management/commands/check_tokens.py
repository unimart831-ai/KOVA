"""
Diagnose social account token health.

Usage:
    python manage.py check_tokens            # all accounts
    python manage.py check_tokens --facebook # Facebook/Instagram only
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.platforms.models import SocialAccount


class Command(BaseCommand):
    help = "Check token health for connected social accounts"

    def add_arguments(self, parser):
        parser.add_argument(
            "--facebook",
            action="store_true",
            help="Only check Facebook/Instagram accounts",
        )

    def handle(self, *args, **options):
        qs = SocialAccount.objects.filter(is_active=True).select_related("user")
        if options["facebook"]:
            qs = qs.filter(platform__in=("facebook", "instagram"))

        if not qs.exists():
            self.stdout.write(self.style.WARNING("No active accounts found."))
            return

        issues = 0
        for acct in qs:
            problems = []

            if acct.is_token_expired:
                problems.append("TOKEN EXPIRED")

            if not acct.access_token:
                problems.append("NO ACCESS TOKEN")

            if acct.platform in ("facebook", "instagram"):
                pages = (acct.metadata or {}).get("pages", [])
                if not pages:
                    problems.append("NO PAGES in metadata")
                elif not pages[0].get("access_token"):
                    problems.append("NO PAGE ACCESS TOKEN")

            if acct.last_error:
                problems.append(f"LAST ERROR: {acct.last_error[:80]}")

            status = self.style.ERROR("ISSUES") if problems else self.style.SUCCESS("OK")
            self.stdout.write(
                f"  [{status}] {acct.platform:10s} @{acct.username:20s} "
                f"user={acct.user.email:30s} id={acct.id}"
            )
            for p in problems:
                self.stdout.write(self.style.WARNING(f"         -> {p}"))
                issues += 1

        self.stdout.write("")
        if issues:
            self.stdout.write(self.style.ERROR(f"{issues} issue(s) found."))
        else:
            self.stdout.write(self.style.SUCCESS("All accounts healthy."))
