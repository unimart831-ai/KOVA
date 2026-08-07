"""Remove deprecated PeriodicTask rows left from removed apps."""

from django.core.management.base import BaseCommand

STALE_TASK_NAMES = (
    "media_queue.process_queues",
    "process-media-queues-every-5-min",
)


class Command(BaseCommand):
    help = "Disable or delete stale django-celery-beat tasks from removed features."

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Delete matching PeriodicTask rows instead of disabling them.",
        )

    def handle(self, *args, **options):
        try:
            from django_celery_beat.models import PeriodicTask
        except ImportError:
            self.stderr.write("django-celery-beat is not installed.")
            return

        qs = PeriodicTask.objects.filter(task__in=STALE_TASK_NAMES)
        count = qs.count()
        if not count:
            self.stdout.write("No stale beat tasks found.")
            return

        if options["delete"]:
            qs.delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {count} stale beat task(s)."))
        else:
            qs.update(enabled=False)
            self.stdout.write(self.style.SUCCESS(f"Disabled {count} stale beat task(s)."))
