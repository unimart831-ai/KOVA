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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["user", "date"]
        ordering = ["-date"]

    def __str__(self):
        return f"Brief: {self.user} - {self.date}"
