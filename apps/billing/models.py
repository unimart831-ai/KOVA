import uuid

from django.conf import settings
from django.db import models


class BillingEvent(models.Model):
    """Audit trail for Stripe webhook events — never lose a payment event."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stripe_event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100)  # e.g. checkout.session.completed
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="billing_events",
    )
    data = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["stripe_event_id"]),
            models.Index(fields=["event_type", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} ({self.stripe_event_id})"


# ─── Plan Limits ─────────────────────────────────────────────────────────────
# Defines what each plan tier can do. Used by middleware and views.
PLAN_LIMITS = {
    "starter": {
        "label": "Jipange / Starter",
        "max_social_accounts": 1,
        "max_posts_per_month": 15,
        "max_seeds_per_month": 10,
        "agents_enabled": ["create", "analyst"],
        "daily_brief": True,
        "email_brief": False,
        "engagement_agent": False,
        "auto_approve": False,
        "price_kes": 250,
        "price_usd": 5,
    },
    "growth": {
        "label": "Kazi / Growth",
        "max_social_accounts": 3,
        "max_posts_per_month": 50,
        "max_seeds_per_month": 30,
        "agents_enabled": ["create", "analyst", "research", "adapt"],
        "daily_brief": True,
        "email_brief": True,
        "engagement_agent": True,
        "auto_approve": False,
        "price_kes": 1000,
        "price_usd": 19,
    },
    "pro": {
        "label": "Biashara / Pro",
        "max_social_accounts": 10,
        "max_posts_per_month": 999999,  # Unlimited
        "max_seeds_per_month": 999999,
        "agents_enabled": ["create", "analyst", "research", "adapt", "engage", "strategist"],
        "daily_brief": True,
        "email_brief": True,
        "engagement_agent": True,
        "auto_approve": True,
        "price_kes": 2500,
        "price_usd": 49,
    },
    "agency": {
        "label": "Wakala / Agency",
        "max_social_accounts": 25,
        "max_posts_per_month": 999999,
        "max_seeds_per_month": 999999,
        "agents_enabled": ["create", "analyst", "research", "adapt", "engage", "strategist"],
        "daily_brief": True,
        "email_brief": True,
        "engagement_agent": True,
        "auto_approve": True,
        "price_kes": 5000,
        "price_usd": 99,
    },
}


def get_plan_limits(plan_tier):
    """Get the limits for a plan tier. Defaults to starter if unknown."""
    return PLAN_LIMITS.get(plan_tier, PLAN_LIMITS["starter"])
