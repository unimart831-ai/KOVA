import os

from django.core.management.base import BaseCommand

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create a superuser from environment variables if one doesn't exist."

    def handle(self, *args, **options):
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

        if not email or not password:
            self.stdout.write(
                self.style.WARNING(
                    "DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD must be set. Skipping."
                )
            )
            return

        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.SUCCESS(f"Superuser '{email}' already exists. Skipping."))
            return

        username = email.split("@")[0]
        User.objects.create_superuser(
            email=email,
            username=username,
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(f"Superuser '{email}' created successfully."))
