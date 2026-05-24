import uuid
from django.conf import settings
from django.db import models


class DailyBrief(models.Model):
    """Daily briefing compiled by the strategist agent."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="briefs")
    date = models.DateField()
    summary = models.TextField(help_text="Plain-language summary of the day's plan.")
    trending_topics = models.JSONField(default=list, blank=True)
    suggested_posts = models.JSONField(default=list, blank=True, help_text="List of post suggestions with reasoning.")
    performance_summary = models.JSONField(default=dict, blank=True, help_text="Yesterday's performance data.")
    agent_activity = models.JSONField(default=list, blank=True, help_text="What agents did/plan to do.")
    posts_pending = models.PositiveIntegerField(default=0)
    is_read = models.BooleanField(default=False)

    # Kova Score — 0-100 social media health score
    kova_score = models.PositiveSmallIntegerField(default=0, help_text="Social health score 0-100")
    kova_score_delta = models.SmallIntegerField(default=0, help_text="Change from previous brief")

    # While You Slept — agent work summary
    overnight_work = models.JSONField(
        default=dict, blank=True,
        help_text="What agents did overnight: {posts_created, trends_found, competitors_analyzed, engagements_handled}",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["user", "date"]
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["user", "-date"]),
            models.Index(fields=["user", "is_read", "-date"]),
        ]

    def __str__(self):
        return f"Brief: {self.user} - {self.date}"


class BriefWhatsAppLog(models.Model):
    """Audit trail for owner reply-to-act commands on the daily brief."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="brief_whatsapp_logs",
    )
    brief = models.ForeignKey(
        DailyBrief,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_logs",
    )
    wa_id = models.CharField(max_length=20, db_index=True)
    inbound_text = models.CharField(max_length=500, blank=True)
    command = models.CharField(max_length=64, db_index=True)
    response_text = models.TextField(blank=True)
    success = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["command", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user_id} · {self.command} · {self.created_at:%Y-%m-%d %H:%M}"
