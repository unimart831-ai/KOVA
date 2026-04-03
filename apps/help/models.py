import uuid

from django.conf import settings
from django.db import models


class HelpPageView(models.Model):
    """Tracks each help article view for usage analytics."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="help_views",
    )
    page_type = models.CharField(
        max_length=20,
        choices=[("center", "Help Center"), ("article", "Article")],
    )
    article_slug = models.CharField(max_length=120, blank=True, default="")
    article_title = models.CharField(max_length=255, blank=True, default="")
    category = models.CharField(max_length=60, blank=True, default="")
    viewed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-viewed_at"]
        indexes = [
            models.Index(fields=["article_slug", "viewed_at"]),
            models.Index(fields=["user", "viewed_at"]),
        ]

    def __str__(self):
        if self.article_slug:
            return f"{self.user} → {self.article_slug} @ {self.viewed_at:%Y-%m-%d %H:%M}"
        return f"{self.user} → Help Center @ {self.viewed_at:%Y-%m-%d %H:%M}"
