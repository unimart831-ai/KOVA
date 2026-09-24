import os
from datetime import timedelta
from itertools import chain

from django.conf import settings
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Count, Q
from django.db.models.functions import TruncHour
from django.shortcuts import render
from django.utils import timezone

from apps.core.admin_dashboard.decorators import staff_required, superuser_required
from apps.create.agents.models import AgentAction
from apps.create.content.models import ContentSeed, Post
from apps.core.platforms.models import SocialAccount


def _check_database():
    """Check database connectivity and basic stats."""
    try:
        connection.ensure_connection()
        return {"status": "online", "engine": connection.vendor}
    except Exception as e:
        return {"status": "down", "error": str(e)}


def _check_redis():
    """Check Redis connectivity via Django cache."""
    from django.core.cache import cache
    try:
        cache.set("_health_check", "ok", 10)
        val = cache.get("_health_check")
        if val == "ok":
            return {"status": "online"}
        return {"status": "degraded", "error": "Cache read mismatch"}
    except Exception as e:
        return {"status": "down", "error": str(e)}


def _check_celery():
    """Check Celery worker availability."""
    try:
        from config.celery import app
        inspector = app.control.inspect(timeout=3.0)
        active = inspector.active()
        if active is None:
            return {"status": "down", "workers": 0, "error": "No workers responding"}
        worker_count = len(active)
        active_tasks = sum(len(tasks) for tasks in active.values())
        return {
            "status": "online",
            "workers": worker_count,
            "active_tasks": active_tasks,
        }
    except Exception as e:
        return {"status": "down", "workers": 0, "error": str(e)}


def _check_celery_beat():
    """Check Celery Beat by looking at django_celery_beat schedule."""
    try:
        from django_celery_beat.models import PeriodicTask
        total = PeriodicTask.objects.filter(enabled=True).count()
        last_run = PeriodicTask.objects.filter(enabled=True, last_run_at__isnull=False).order_by("-last_run_at").first()
        if last_run and last_run.last_run_at:
            since = timezone.now() - last_run.last_run_at
            stale = since > timedelta(minutes=10)
            return {
                "status": "stale" if stale else "online",
                "enabled_tasks": total,
                "last_tick": last_run.last_run_at,
                "last_task": last_run.name,
            }
        return {"status": "unknown", "enabled_tasks": total, "last_tick": None}
    except Exception:
        return {"status": "unknown", "enabled_tasks": 0, "last_tick": None}


@superuser_required
def system_health(request):
    """System health dashboard — infrastructure status, tasks, errors, DB stats."""
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_48h = now - timedelta(hours=48)

    # ── Component health checks ──────────────────────────────────────
    db_status = _check_database()
    redis_status = _check_redis()
    celery_status = _check_celery()
    beat_status = _check_celery_beat()

    # ── Celery beat schedule ─────────────────────────────────────────
    beat_tasks = []
    try:
        from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule
        for task in PeriodicTask.objects.filter(enabled=True).select_related("interval", "crontab").order_by("name"):
            if task.interval:
                every = task.interval.every
                period = task.interval.period
                schedule_str = f"every {every} {period}"
            elif task.crontab:
                schedule_str = f"{task.crontab.minute} {task.crontab.hour} {task.crontab.day_of_week}"
            else:
                schedule_str = "—"

            beat_tasks.append({
                "name": task.name,
                "task": task.task,
                "schedule": schedule_str,
                "last_run": task.last_run_at,
                "enabled": task.enabled,
                "total_run_count": task.total_run_count,
            })
    except Exception:
        pass

    # Fallback: show configured beat schedule from settings if no DB tasks
    if not beat_tasks:
        for key, conf in getattr(settings, "CELERY_BEAT_SCHEDULE", {}).items():
            sched = conf.get("schedule")
            if hasattr(sched, "total_seconds"):
                schedule_str = f"every {int(sched.total_seconds())}s"
            else:
                schedule_str = str(sched)
            beat_tasks.append({
                "name": key,
                "task": conf.get("task", ""),
                "schedule": schedule_str,
                "last_run": None,
                "enabled": True,
                "total_run_count": 0,
            })

    # ── Error tracking (24h) ─────────────────────────────────────────
    agent_errors_24h = AgentAction.objects.filter(
        status="failed", created_at__gte=last_24h,
    ).count()

    post_errors_24h = Post.objects.filter(
        status="failed", updated_at__gte=last_24h,
    ).count()

    seed_errors_24h = ContentSeed.objects.filter(
        status="failed", updated_at__gte=last_24h,
    ).count()

    platform_errors = SocialAccount.objects.exclude(
        last_error=""
    ).exclude(last_error__isnull=True).count()

    total_errors_24h = agent_errors_24h + post_errors_24h + seed_errors_24h

    # Recent failed agent actions (last 24h)
    recent_errors = list(
        AgentAction.objects.filter(status="failed", created_at__gte=last_24h)
        .select_related("user")
        .order_by("-created_at")[:20]
    )

    # Error trend — hourly buckets for last 48h (single query)
    error_by_hour = {
        row["hour"]: row["count"]
        for row in AgentAction.objects.filter(
            status="failed", created_at__gte=last_48h,
        ).annotate(hour=TruncHour("created_at"))
        .values("hour").annotate(count=Count("id"))
    }
    error_trend = []
    for i in range(47, -1, -1):
        hour_end = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=i)
        error_trend.append({
            "hour": hour_end.strftime("%b %d %H:00"),
            "count": error_by_hour.get(hour_end, 0),
        })

    # Error breakdown by category (from error_message patterns)
    error_categories = list(
        AgentAction.objects.filter(status="failed", created_at__gte=last_24h)
        .values("agent_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # ── Database stats ───────────────────────────────────────────────
    from apps.core.accounts.models import User
    from apps.insight.analytics.models import Conversion
    from apps.core.billing.models import BillingEvent, MpesaPayment
    from apps.create.briefs.models import DailyBrief
    from apps.messaging.notifications.models import Notification
    from rest_framework.authtoken.models import Token

    total_api_tokens = Token.objects.count()

    db_stats = [
        {"table": "Users", "count": User.objects.count()},
        {"table": "Posts", "count": Post.objects.count()},
        {"table": "Content Seeds", "count": ContentSeed.objects.count()},
        {"table": "Agent Actions", "count": AgentAction.objects.count()},
        {"table": "Social Accounts", "count": SocialAccount.objects.count()},
        {"table": "Notifications", "count": Notification.objects.count()},
        {"table": "Daily Briefs", "count": DailyBrief.objects.count()},
        {"table": "M-Pesa Payments", "count": MpesaPayment.objects.count()},
        {"table": "Billing Events", "count": BillingEvent.objects.count()},
        {"table": "Conversions", "count": Conversion.objects.count()},
        {"table": "API Tokens", "count": total_api_tokens},
    ]
    total_records = sum(s["count"] for s in db_stats)
    db_stats.sort(key=lambda x: x["count"], reverse=True)

    # ── LLM provider status ──────────────────────────────────────────
    agent_models = getattr(settings, "AGENT_MODELS", {})
    # Get unique models in use
    active_models = set(agent_models.values())

    # Per-model success/failure rates (24h)
    llm_providers = []
    for model in sorted(active_models):
        model_qs = AgentAction.objects.filter(
            model_used=model, created_at__gte=last_24h,
        )
        total = model_qs.count()
        failed = model_qs.filter(status="failed").count()
        succeeded = total - failed
        avg_duration = 0
        if total:
            from django.db.models import Avg
            avg_d = model_qs.aggregate(avg=Avg("duration_ms"))["avg"]
            avg_duration = round(avg_d / 1000, 1) if avg_d else 0

        if total == 0:
            status = "idle"
        elif failed / total > 0.2:
            status = "degraded"
        else:
            status = "online"

        llm_providers.append({
            "model": model,
            "status": status,
            "total_24h": total,
            "failed_24h": failed,
            "success_rate": round((succeeded / total) * 100, 1) if total else 0,
            "avg_latency": avg_duration,
        })

    # ── Expiring tokens ──────────────────────────────────────────────
    expiring_soon = SocialAccount.objects.filter(
        is_active=True,
        token_expires_at__isnull=False,
        token_expires_at__lte=now + timedelta(hours=24),
    ).select_related("user").count()

    context = {
        "page_title": "System Health",
        # Component status
        "db_status": db_status,
        "redis_status": redis_status,
        "celery_status": celery_status,
        "beat_status": beat_status,
        # Tasks
        "beat_tasks": beat_tasks,
        # Errors
        "agent_errors_24h": agent_errors_24h,
        "post_errors_24h": post_errors_24h,
        "seed_errors_24h": seed_errors_24h,
        "platform_errors": platform_errors,
        "total_errors_24h": total_errors_24h,
        "recent_errors": recent_errors,
        "error_trend_json": error_trend,
        "error_categories": error_categories,
        # Database
        "db_stats": db_stats,
        "total_records": total_records,
        # LLM
        "llm_providers": llm_providers,
        # Tokens
        "expiring_soon": expiring_soon,
        # API
        "total_api_tokens": total_api_tokens,
    }
    return render(request, "admin_dashboard/system/health.html", context)


@superuser_required
def error_log(request):
    """Searchable error log — failed agent actions, posts, seeds."""
    qs = AgentAction.objects.filter(status="failed").select_related("user")

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(error_message__icontains=search)
            | Q(user__email__icontains=search)
            | Q(agent_type__icontains=search)
            | Q(action_type__icontains=search)
        )

    agent = request.GET.get("agent", "")
    if agent:
        qs = qs.filter(agent_type=agent)

    days = request.GET.get("days", "7")
    try:
        days_int = int(days)
    except ValueError:
        days_int = 7
    if days_int > 0:
        qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=days_int))

    qs = qs.order_by("-created_at")
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page", 1))

    agent_choices = AgentAction.AgentType.choices if hasattr(AgentAction, "AgentType") else []

    context = {
        "page_title": "Error Log",
        "page_obj": page,
        "search": search,
        "current_agent": agent,
        "current_days": days,
        "total_count": paginator.count,
        "agent_choices": agent_choices,
    }
    return render(request, "admin_dashboard/system/errors.html", context)
