"""
Celery configuration for Kova Agent.
All agent operations run as Celery tasks.

Queue priority:
  critical  — Publishing, webhooks, token refresh (user-facing, time-sensitive)
  default   — Content generation, AI agents, engagement cycles
  low       — Analytics, competitor analysis, metrics fetching, outcome measurement
"""

import os

from celery import Celery
from kombu import Exchange, Queue

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

app = Celery("kova_agent")
app.config_from_object("django.conf:settings", namespace="CELERY")

# ── Priority queues ──────────────────────────────────────────────────────────
default_exchange = Exchange("default", type="direct")

app.conf.task_queues = (
    Queue("critical", default_exchange, routing_key="critical"),
    Queue("default", default_exchange, routing_key="default"),
    Queue("low", default_exchange, routing_key="low"),
)
app.conf.task_default_queue = "default"
app.conf.task_default_routing_key = "default"

# Worker tuning — prevent a single worker from prefetching too many tasks
app.conf.worker_prefetch_multiplier = 1  # fetch one task at a time per worker process
app.conf.task_acks_late = True  # ack after execution, not before (safer with retries)

app.conf.task_routes = {
    # Critical — user-facing, time-sensitive
    "content.publish_post": {"queue": "critical"},
    "content.check_and_publish_due_posts": {"queue": "critical"},
    "platforms.refresh_expiring_tokens": {"queue": "critical"},
    # Default — content generation, AI agents
    "content.generate_from_seed": {"queue": "default"},
    "content.generate_ab_test_variants": {"queue": "default"},
    "agents.run_daily_research": {"queue": "default"},
    "agents.refresh_seed_suggestions": {"queue": "low"},
    "agents.run_engage_cycle": {"queue": "default"},
    "agents.run_engage_for_user": {"queue": "default"},
    "agents.run_research_for_user": {"queue": "default"},
    "agents.run_strategy_cycle": {"queue": "default"},
    "agents.run_strategy_for_user": {"queue": "default"},
    "briefs.generate_all_daily_briefs": {"queue": "default"},
    "briefs.send_money_board_digests": {"queue": "default"},
    # Low — analytics, metrics, background intelligence
    "content.fetch_post_metrics": {"queue": "low"},
    "content.fetch_all_recent_metrics": {"queue": "low"},
    "content.evaluate_ab_tests": {"queue": "low"},
    "agents.measure_agent_outcomes": {"queue": "low"},
    "analyze-all-competitors": {"queue": "low"},
    "billing.check_mpesa_subscriptions": {"queue": "low"},
    # Media Queue — publish user photos on schedule
    "media_queue.process_queues": {"queue": "critical"},
    # WhatsApp — AI auto-reply must be fast
    "whatsapp.handle_incoming_message": {"queue": "critical"},
    "whatsapp.execute_broadcast": {"queue": "critical"},
    "whatsapp.process_sequence_steps": {"queue": "critical"},
    "whatsapp.send_followup_nudges": {"queue": "default"},
    "whatsapp.generate_status_content": {"queue": "default"},
    "whatsapp.repurpose_post_to_status": {"queue": "default"},
    "whatsapp.cross_post_to_channel": {"queue": "default"},
    "whatsapp.aggregate_daily_analytics": {"queue": "low"},
    "whatsapp.generate_weekly_digest": {"queue": "low"},
    "whatsapp.curate_channel_content": {"queue": "low"},
    # Products
    "products.expire_stale_commerce_payments": {"queue": "low"},
    "products.auto_promote_products": {"queue": "default"},
    "content.recycle_top_content": {"queue": "low"},
    "content.plan_weekly_autopilot": {"queue": "default"},
    "content.plan_user_week": {"queue": "default"},
    "content.send_autopilot_review_emails": {"queue": "low"},
    "campaigns.ai_build_campaign": {"queue": "default"},
    # Lead nurture + scoring + monthly reports
    "leads.process_nurture_steps": {"queue": "default"},
    "leads.score_all_leads": {"queue": "low"},
    "leads.reengage_stale_leads": {"queue": "low"},
    "emails.send_monthly_reports_all": {"queue": "low"},
    # Calendar Intelligence — holiday awareness
    "calendar_intel.run_holiday_watcher": {"queue": "low"},
    "calendar_intel.generate_drafts_for_moment": {"queue": "default"},
    # Profile Audit
    "profile_audit.run_profile_audits": {"queue": "low"},
    "profile_audit.audit_one_account": {"queue": "low"},
    "profile_audit.apply_one_suggestion": {"queue": "default"},
    "accounts.snapshot_pilot_metrics": {"queue": "low"},
}

# NOTE: Beat schedule is defined in CELERY_BEAT_SCHEDULE in config/settings/base.py
# Do NOT set app.conf.beat_schedule here — it would overwrite the settings dict.

# Auto-discover tasks in all installed apps (looks for tasks.py in each app)
app.autodiscover_tasks()

# Tasks defined outside tasks.py must be imported on worker boot.
import apps.content.autopilot  # noqa: F401, E402


# ── Startup diagnostics ─────────────────────────────────────────────────────
# Logs the active settings module + storage backend when the worker starts.
# This is critical for debugging R2/S3 issues on Railway.
from celery.signals import worker_ready  # noqa: E402


@worker_ready.connect
def _log_storage_backend(sender, **kwargs):
    import logging

    from django.conf import settings
    from django.core.files.storage import default_storage

    logger = logging.getLogger("celery.worker")
    logger.info(
        "DJANGO_SETTINGS_MODULE=%s | DEFAULT_STORAGE=%s",
        os.environ.get("DJANGO_SETTINGS_MODULE", "<NOT SET>"),
        default_storage.__class__.__name__,
    )

    # Log Fernet key diagnostics to detect web/worker key mismatch
    from apps.platforms.encryption import _build_fernets
    _build_fernets()

    bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
    if bucket:
        logger.info(
            "R2 active: bucket=%s endpoint=%s",
            bucket,
            getattr(settings, "AWS_S3_ENDPOINT_URL", "<NOT SET>"),
        )
    else:
        logger.warning(
            "R2 NOT active — media files use local FileSystemStorage "
            "(lost on every deploy)."
        )
