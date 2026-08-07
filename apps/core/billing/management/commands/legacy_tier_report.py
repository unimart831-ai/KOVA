"""Admin report: subscribers by legacy tier."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.core.accounts.models import UserProfile


class Command(BaseCommand):
    help = "Print subscriber counts by plan tier (legacy + kova)."

    def handle(self, *args, **options):
        User = get_user_model()
        rows = (
            UserProfile.objects.values("plan")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        self.stdout.write("Subscribers by plan tier:")
        total = 0
        legacy = 0
        for row in rows:
            plan = row["plan"] or "unknown"
            count = row["count"]
            total += count
            if plan in ("starter", "growth", "pro"):
                legacy += count
            self.stdout.write(f"  {plan}: {count}")
        self.stdout.write(f"Total profiles: {total}")
        self.stdout.write(f"Legacy (starter/growth/pro): {legacy}")
        kova_count = UserProfile.objects.filter(plan=UserProfile.PlanTier.KOVA).count()
        self.stdout.write(f"Kova: {kova_count}")
