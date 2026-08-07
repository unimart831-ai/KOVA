"""Draft email to legacy tier users before Kova migration (dry-run by default)."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.core.accounts.models import UserProfile


class Command(BaseCommand):
    help = "Preview or send Kova migration email to legacy tier subscribers."

    def add_arguments(self, parser):
        parser.add_argument("--send", action="store_true", help="Actually send emails")
        parser.add_argument("--plan", default="", help="Limit to plan (starter/growth/pro)")

    def handle(self, *args, **options):
        User = get_user_model()
        legacy_plans = ("starter", "growth", "pro")
        plan_filter = options["plan"].strip().lower()
        if plan_filter:
            legacy_plans = (plan_filter,)

        qs = User.objects.filter(
            profile__plan__in=legacy_plans,
            is_active=True,
        ).select_related("profile")

        subject = "Kova is simplifying — one plan, more campaigns"
        body_template = (
            "Hi {name},\n\n"
            "We're moving to one Kova plan (KES 1,300/mo, 30 campaigns) with everything included. "
            "Your current plan continues until renewal, then you'll migrate to Kova automatically "
            "with goodwill campaign credits.\n\n"
            "Questions? Reply to this email or WhatsApp us.\n\n— Team Kova"
        )

        for user in qs[:500]:
            body = body_template.format(name=user.first_name or user.email.split("@")[0])
            if options["send"]:
                from django.core.mail import send_mail
                from django.conf import settings

                send_mail(
                    subject,
                    body,
                    getattr(settings, "DEFAULT_FROM_EMAIL", "hello@kova.ai"),
                    [user.email],
                    fail_silently=False,
                )
                self.stdout.write(f"Sent: {user.email}")
            else:
                self.stdout.write(f"[dry-run] {user.email} ({user.profile.plan})\n{body[:120]}...\n")

        self.stdout.write(self.style.SUCCESS(f"Processed {qs.count()} users (send={options['send']})"))
