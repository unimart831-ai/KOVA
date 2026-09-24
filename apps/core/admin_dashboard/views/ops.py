"""Ops views — Celery beat health for critical scheduled tasks."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.shortcuts import render
from django.utils import timezone

from apps.core.admin_dashboard.decorators import staff_required

# Critical beat tasks monitored on /dashboard/ops/celery/
CRITICAL_BEAT_TASKS = (
    {
        "task": "briefs.generate_all_daily_briefs",
        "label": "Daily briefs",
        "schedule_key": "generate-daily-briefs",
        "stale_minutes": 20,
    },
    {
        "task": "content.check_and_publish_due_posts",
        "label": "Publish due posts",
        "schedule_key": "check-and-publish-due-posts",
        "stale_minutes": 10,
    },
    {
        "task": "whatsapp.send_followup_nudges",
        "label": "WhatsApp follow-up",
        "schedule_key": "whatsapp-followup-nudges",
        "stale_minutes": 90,
    },
    {
        "task": "briefs.send_money_board_digests",
        "label": "Money board digest",
        "schedule_key": "send-money-board-digests",
        "stale_minutes": 26 * 60,
    },
)


def _schedule_label(schedule_key: str, task_name: str) -> str:
    conf = getattr(settings, "CELERY_BEAT_SCHEDULE", {}).get(schedule_key, {})
    sched = conf.get("schedule")
    if hasattr(sched, "total_seconds"):
        seconds = int(sched.total_seconds())
        if seconds >= 86400:
            return f"every {seconds // 86400}d"
        if seconds >= 3600:
            return f"every {seconds // 3600}h"
        if seconds >= 60:
            return f"every {seconds // 60}m"
        return f"every {seconds}s"
    return task_name


def _beat_task_rows():
    now = timezone.now()
    rows = []

    db_tasks = {}
    try:
        from django_celery_beat.models import PeriodicTask

        for pt in PeriodicTask.objects.filter(enabled=True):
            db_tasks[pt.task] = pt
    except Exception:
        pass

    for spec in CRITICAL_BEAT_TASKS:
        pt = db_tasks.get(spec["task"])
        last_run = pt.last_run_at if pt else None
        stale_after = timedelta(minutes=spec["stale_minutes"])

        if last_run is None:
            status = "unknown"
        elif now - last_run > stale_after:
            status = "stale"
        else:
            status = "ok"

        rows.append({
            "label": spec["label"],
            "task": spec["task"],
            "schedule": _schedule_label(spec["schedule_key"], spec["task"]),
            "last_run": last_run,
            "stale_minutes": spec["stale_minutes"],
            "status": status,
            "enabled": pt.enabled if pt else True,
            "total_run_count": pt.total_run_count if pt else 0,
        })

    return rows


@staff_required
def celery_health(request):
    """Last success time for critical Celery beat tasks."""
    from apps.core.admin_dashboard.views.system import _check_celery, _check_celery_beat

    rows = _beat_task_rows()
    stale_count = sum(1 for r in rows if r["status"] == "stale")
    unknown_count = sum(1 for r in rows if r["status"] == "unknown")

    return render(request, "admin_dashboard/ops/celery.html", {
        "page_title": "Celery health",
        "tasks": rows,
        "stale_count": stale_count,
        "unknown_count": unknown_count,
        "celery_status": _check_celery(),
        "beat_status": _check_celery_beat(),
    })
