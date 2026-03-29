import uuid
from django.db import models


class PostMetric(models.Model):
    """Engagement metrics for a published post."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.OneToOneField("content.Post", on_delete=models.CASCADE, related_name="metrics")
    impressions = models.PositiveIntegerField(default=0)
    reach = models.PositiveIntegerField(default=0)
    likes = models.PositiveIntegerField(default=0)
    comments = models.PositiveIntegerField(default=0)
    shares = models.PositiveIntegerField(default=0)
    saves = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    engagement_rate = models.FloatField(null=True, blank=True)
    fetched_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Metrics for {self.post_id}"
