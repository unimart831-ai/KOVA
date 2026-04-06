import uuid
from django.conf import settings
from django.db import models


class AgentConfig(models.Model):
    """Per-user configuration for each AI agent."""

    class AgentType(models.TextChoices):
        RESEARCH = "research", "Research Agent"
        CREATE = "create", "Content Creator Agent"
        ADAPT = "adapt", "Platform Adapter Agent"
        ENGAGE = "engage", "Engagement Agent"
        ANALYST = "analyst", "Analytics Agent"
        STRATEGIST = "strategist", "Chief Strategist"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_configs")
    agent_type = models.CharField(max_length=20, choices=AgentType.choices)
    is_active = models.BooleanField(default=True)
    custom_instructions = models.TextField(blank=True, help_text="Additional instructions for this agent.")
    config = models.JSONField(default=dict, blank=True, help_text="Agent-specific configuration.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "agent_type"]
        ordering = ["agent_type"]

    def __str__(self):
        return f"{self.get_agent_type_display()} for {self.user}"

    @property
    def name(self):
        return self.get_agent_type_display()

    @property
    def slug(self):
        return self.agent_type

    @property
    def icon(self):
        icons = {
            "research": "🔍",
            "create": "✍️",
            "adapt": "🔄",
            "engage": "💬",
            "analyst": "📊",
            "strategist": "🧠",
        }
        return icons.get(self.agent_type, "🤖")

    @property
    def role(self):
        roles = {
            "research": "Finds trends, competitors, and content angles.",
            "create": "Drafts posts in your brand voice.",
            "adapt": "Tailors copy for each platform.",
            "engage": "Suggests replies and flags conversations.",
            "analyst": "Tracks performance and patterns.",
            "strategist": "Orchestrates agents and your daily brief.",
        }
        return roles.get(self.agent_type, "Runs automated tasks for you.")


class AgentAction(models.Model):
    """Log of every action taken by an AI agent."""

    class ActionStatus(models.TextChoices):
        STARTED = "started", "Started"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        NEEDS_APPROVAL = "needs_approval", "Needs Approval"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_actions")
    agent_type = models.CharField(max_length=20, choices=AgentConfig.AgentType.choices, db_index=True)
    action_type = models.CharField(max_length=100)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=ActionStatus.choices, default=ActionStatus.STARTED, db_index=True)
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    tokens_used = models.PositiveIntegerField(default=0)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    model_used = models.CharField(max_length=100, blank=True, help_text="LLM model identifier used for this action")
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Intelligence: outcome tracking — did this action actually work?
    outcome_score = models.FloatField(
        null=True, blank=True,
        help_text="Measured outcome (0-100). E.g. engagement rate of generated posts, accuracy of prediction.",
    )
    outcome_data = models.JSONField(
        default=dict, blank=True,
        help_text="Structured outcome: {posts_created, avg_engagement, user_edits, prediction_accuracy, etc.}",
    )
    outcome_measured_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "agent_type", "-created_at"]),
            models.Index(fields=["user", "status", "-created_at"]),
            models.Index(fields=["agent_type", "status", "-created_at"]),
        ]
