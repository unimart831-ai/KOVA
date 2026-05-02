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
        STRATEGIST = "strategist", "Chief Strategist & Growth Advisor"

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
            "strategist": "Orchestrates agents, tracks audience growth, and drives your strategy.",
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


class LLMConfig(models.Model):
    """
    Singleton model — stores LLM configuration that admins can change at runtime.

    Overrides settings from base.py. The LLM layer reads from DB first,
    falls back to settings/env vars if no DB row exists.
    """

    class Provider(models.TextChoices):
        OPENAI = "openai", "OpenAI"
        OPENROUTER = "openrouter", "OpenRouter"
        ANTHROPIC = "anthropic", "Anthropic"

    # ── Global defaults ──────────────────────────────────────────────
    default_provider = models.CharField(
        max_length=20, choices=Provider.choices, default=Provider.OPENROUTER,
        help_text="Primary LLM provider.",
    )
    default_model = models.CharField(
        max_length=120, default="deepseek/deepseek-v3.2",
        help_text="Default model when no task-specific model is set.",
    )
    paid_fallback_model = models.CharField(
        max_length=120, blank=True, default="google/gemini-2.0-flash-001",
        help_text="Paid model to auto-escalate to when free models fail. Leave blank to disable.",
    )
    paid_fallback_provider = models.CharField(
        max_length=20, choices=Provider.choices, default=Provider.OPENROUTER,
        help_text="Provider for the paid fallback model.",
    )

    # ── Tier defaults ────────────────────────────────────────────────
    model_premium = models.CharField(
        max_length=120, default="deepseek/deepseek-v3.2",
        help_text="Premium tier — creative generation and user-facing text.",
    )
    model_workhorse = models.CharField(
        max_length=120, default="deepseek/deepseek-v3.2",
        help_text="Workhorse tier — reasoning, research, strategy.",
    )
    model_fast = models.CharField(
        max_length=120, default="deepseek/deepseek-v3.2",
        help_text="Fast tier — classification, DNA extraction, scoring.",
    )

    # ── Per-task overrides (JSON: {"task.key": "model-name"}) ────────
    task_model_overrides = models.JSONField(
        default=dict, blank=True,
        help_text='Per-task model overrides. Keys like "create.generate", "engage.reply", etc.',
    )

    # ── Per-plan model routing ───────────────────────────────────────
    # JSON: {"starter": {"premium": "...", "workhorse": "...", "fast": "..."}, ...}
    plan_model_overrides = models.JSONField(
        default=dict, blank=True,
        help_text='Per-plan tier overrides. {"starter": {"premium": "model", "workhorse": "model", "fast": "model"}, ...}',
    )

    # ── Per-plan rate limits ─────────────────────────────────────────
    # JSON: {"starter": {"max_calls_per_hour": 30, "max_tokens_per_day": 100000}, ...}
    plan_rate_limits = models.JSONField(
        default=dict, blank=True,
        help_text='Per-plan rate limits. {"starter": {"max_calls_per_hour": 30, "max_tokens_per_day": 100000}, ...}',
    )

    # ── Free fallback chain ──────────────────────────────────────────
    free_fallback_models = models.JSONField(
        default=list, blank=True,
        help_text="Ordered list of free model identifiers to try when the primary fails.",
    )

    # ── Controls ─────────────────────────────────────────────────────
    max_retries = models.PositiveSmallIntegerField(
        default=3,
        help_text="Max model attempts before giving up (including fallbacks).",
    )
    paid_fallback_enabled = models.BooleanField(
        default=True,
        help_text="Whether to auto-escalate to paid model when free models fail.",
    )

    # ── Image Generation Config ──────────────────────────────────────
    image_default_provider = models.CharField(
        max_length=30, default="together",
        help_text="Primary image provider: together, huggingface, pollinations.",
    )
    image_default_model = models.CharField(
        max_length=120, default="black-forest-labs/FLUX.1-schnell",
        help_text="Default image model when no plan-specific model is configured.",
    )
    image_plan_models = models.JSONField(
        default=dict, blank=True,
        help_text='Per-plan image model routing. {"starter": {"model": "...", "provider": "together"}, ...}',
    )
    image_fallback_chain = models.JSONField(
        default=list, blank=True,
        help_text='Ordered fallback providers: ["together", "huggingface", "pollinations"]',
    )
    image_enabled = models.BooleanField(
        default=True,
        help_text="Global kill-switch for AI image generation.",
    )

    # ── Meta ─────────────────────────────────────────────────────────
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )

    class Meta:
        verbose_name = "LLM Configuration"
        verbose_name_plural = "LLM Configuration"

    def __str__(self):
        return f"LLM Config (updated {self.updated_at})"

    def save(self, *args, **kwargs):
        # Enforce singleton: always use pk=1
        self.pk = 1
        super().save(*args, **kwargs)
        # Clear cached config
        LLMConfig._cached = None

    @classmethod
    def load(cls):
        """Load the singleton config, with in-memory caching."""
        if getattr(cls, "_cached", None) is not None:
            return cls._cached
        try:
            obj = cls.objects.get(pk=1)
        except cls.DoesNotExist:
            obj = cls()  # Unsaved — returns defaults
        cls._cached = obj
        return obj

    _cached = None

    def get_task_models(self, plan=None):
        """
        Build the full AGENT_MODELS dict: tier defaults + per-task overrides.
        Same structure as settings.AGENT_MODELS.

        If *plan* is provided (e.g. "starter", "agency"), use plan-specific
        tier models first, then fall back to global tiers.
        """
        # Resolve tier models: plan-specific overrides → global defaults
        plan_overrides = (self.plan_model_overrides or {}).get(plan, {}) if plan else {}
        premium = plan_overrides.get("premium") or self.model_premium
        workhorse = plan_overrides.get("workhorse") or self.model_workhorse
        fast = plan_overrides.get("fast") or self.model_fast

        tier_mapping = {
            "create.generate": premium,
            "create.regenerate": premium,
            "create.repurpose": premium,
            "engage.analyze": fast,
            "engage.reply": premium,
            "analyst.performance": fast,
            "analyst.content_dna": fast,
            "analyst.predict": fast,
            "research.trends": workhorse,
            "research.angles": workhorse,
            "adapt.schedule": fast,
            "strategist.brief": workhorse,
            "strategist.decide": workhorse,
        }
        # Apply per-task overrides (these override everything)
        tier_mapping.update(self.task_model_overrides or {})
        return tier_mapping

    def get_image_model(self, plan=None):
        """Return (model_id, provider) for the given plan.

        Resolution: plan-specific override → global default → hardcoded fallback.
        """
        plan_cfg = (self.image_plan_models or {}).get(plan, {}) if plan else {}
        model = plan_cfg.get("model") or self.image_default_model or "black-forest-labs/FLUX.1-schnell"
        provider = plan_cfg.get("provider") or self.image_default_provider or "together"
        return model, provider

    def get_image_fallback_chain(self):
        """Return ordered list of fallback providers."""
        return self.image_fallback_chain or ["together", "huggingface", "pollinations"]


class UserTokenBucket(models.Model):
    """Per-user, per-day record of LLM token consumption and estimated cost.

    Used by the budget enforcer in apps.agents.budget to prevent a single
    user from burning the platform's LLM spend before being upgraded to a
    higher plan. Cost is stored in micro-USD (1e-6) so atomic F() updates
    stay integer-safe across many concurrent calls.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="token_buckets",
    )
    period_date = models.DateField(db_index=True)
    input_tokens = models.PositiveBigIntegerField(default=0)
    output_tokens = models.PositiveBigIntegerField(default=0)
    cost_usd_micros = models.PositiveBigIntegerField(default=0)
    call_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "period_date")]
        ordering = ["-period_date"]
        indexes = [
            models.Index(fields=["user", "-period_date"]),
        ]

    def __str__(self):
        return (
            f"{self.user_id} {self.period_date}: "
            f"{self.input_tokens + self.output_tokens} tokens "
            f"(${self.cost_usd_micros / 1_000_000:.4f})"
        )

    @property
    def total_tokens(self):
        return self.input_tokens + self.output_tokens

    @property
    def cost_usd(self):
        return self.cost_usd_micros / 1_000_000
