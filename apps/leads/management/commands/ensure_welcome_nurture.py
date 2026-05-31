"""Ensure default welcome + stale win-back nurture sequences for users."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.leads.defaults import ensure_default_nurture_sequences


class Command(BaseCommand):
    help = "Create default Welcome + Win-back nurture sequences for one or all users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            help="Only ensure sequences for this username (default: all active users)",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        qs = User.objects.filter(is_active=True)
        if options.get("username"):
            qs = qs.filter(username=options["username"])

        count = 0
        for user in qs.iterator():
            ensure_default_nurture_sequences(user)
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Ensured default nurture sequences for {count} user(s)."))
