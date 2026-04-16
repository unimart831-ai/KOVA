import os

from django.core.management.base import BaseCommand

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create a superuser from environment variables if one doesn't exist."

    def _ensure_verified_email(self, user):
        """Ensure superuser has a verified EmailAddress in allauth."""
        from allauth.account.models import EmailAddress

        email_address, created = EmailAddress.objects.get_or_create(
            user=user,
            email=user.email,
            defaults={"verified": True, "primary": True},
        )
        if not email_address.verified:
            email_address.verified = True
            email_address.primary = True
            email_address.save(update_fields=["verified", "primary"])
            self.stdout.write(self.style.SUCCESS(f"  Marked '{user.email}' as verified."))

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
            user = User.objects.get(email=email)
            self.stdout.write(self.style.SUCCESS(f"Superuser '{email}' already exists. Skipping."))
            self._ensure_verified_email(user)
            return

        username = email.split("@")[0]
        user = User.objects.create_superuser(
            email=email,
            username=username,
            password=password,
        )
        self._ensure_verified_email(user)
        self.stdout.write(self.style.SUCCESS(f"Superuser '{email}' created successfully."))
