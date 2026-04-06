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

app.conf.task_routes = {
    # Critical — user-facing, time-sensitive
    "content.publish_post": {"queue": "critical"},
    "content.check_and_publish_due_posts": {"queue": "critical"},
    "platforms.refresh_expiring_tokens": {"queue": "critical"},
    # Default — content generation, AI agents
    "content.generate_from_seed": {"queue": "default"},
    "content.generate_ab_test_variants": {"queue": "default"},
    "agents.run_daily_research": {"queue": "default"},
    "agents.run_engage_cycle": {"queue": "default"},
    "agents.run_strategy_cycle": {"queue": "default"},
    "briefs.generate_all_daily_briefs": {"queue": "default"},
    # Low — analytics, metrics, background intelligence
    "content.fetch_post_metrics": {"queue": "low"},
    "content.fetch_all_recent_metrics": {"queue": "low"},
    "content.evaluate_ab_tests": {"queue": "low"},
    "agents.measure_agent_outcomes": {"queue": "low"},
    "analyze-all-competitors": {"queue": "low"},
    "billing.check_mpesa_subscriptions": {"queue": "low"},
    # Media Queue — publish user photos on schedule
    "media_queue.process_queues": {"queue": "critical"},
}

# ── Periodic beat schedule ───────────────────────────────────────────────────
app.conf.beat_schedule = {
    "process-media-queues-every-5-min": {
        "task": "media_queue.process_queues",
        "schedule": 300.0,  # every 5 minutes
    },
}

# Auto-discover tasks in all installed apps (looks for tasks.py in each app)
app.autodiscover_tasks()
