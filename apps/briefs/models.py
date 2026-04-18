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
