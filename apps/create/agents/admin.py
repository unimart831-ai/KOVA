from django.contrib import admin

from apps.create.agents.models import AgentConfig, AgentAction, LLMConfig, UserTokenBucket


@admin.register(AgentConfig)
class AgentConfigAdmin(admin.ModelAdmin):
    list_display = ["user", "agent_type", "is_active", "updated_at"]
    list_filter = ["agent_type", "is_active"]
    search_fields = ["user__email"]


@admin.register(AgentAction)
class AgentActionAdmin(admin.ModelAdmin):
    list_display = [
        "user", "agent_type", "action_type", "status",
        "tokens_used", "model_used", "created_at",
    ]
    list_filter = ["agent_type", "status", "model_used"]
    search_fields = ["user__email", "action_type", "description"]
    readonly_fields = ["created_at", "completed_at", "outcome_measured_at"]
    date_hierarchy = "created_at"


@admin.register(LLMConfig)
class LLMConfigAdmin(admin.ModelAdmin):
    """Singleton — global LLM provider/model/fallback control.
    There's only ever one row; admins edit it to change provider, model
    tiers, or fallback chain across the entire platform."""

    list_display = ["__str__", "default_provider", "default_model", "image_default_model", "updated_at"]
    readonly_fields = ["updated_at"]
    fieldsets = (
        ("Provider defaults", {
            "fields": ("default_provider", "default_model", "max_retries"),
        }),
        ("Model tiers", {
            "fields": ("model_premium", "model_workhorse", "model_fast"),
            "description": "Used by get_model_for_task when no override exists.",
        }),
        ("Fallback chain", {
            "fields": (
                "free_fallback_models",
                "paid_fallback_enabled",
                "paid_fallback_model",
                "paid_fallback_provider",
            ),
        }),
        ("Per-task / per-plan overrides", {
            "fields": ("task_model_overrides", "plan_model_overrides", "plan_rate_limits"),
            "classes": ("collapse",),
        }),
        ("Image generation", {
            "fields": (
                "image_enabled",
                "image_default_provider",
                "image_default_model",
                "image_plan_models",
                "image_fallback_chain",
            ),
            "classes": ("collapse",),
        }),
        ("Audit", {
            "fields": ("updated_by", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def has_add_permission(self, request):
        # Singleton — never allow more than one row
        if LLMConfig.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UserTokenBucket)
class UserTokenBucketAdmin(admin.ModelAdmin):
    """Per-user daily LLM budget tracking. Read-mostly; admins inspect
    heavy users or zero out a bucket if needed."""

    list_display = [
        "user", "period_date", "call_count",
        "input_tokens", "output_tokens", "cost_usd_display",
    ]
    list_filter = ["period_date"]
    search_fields = ["user__email"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "period_date"

    def cost_usd_display(self, obj):
        return f"${obj.cost_usd_micros / 1_000_000:.4f}"
    cost_usd_display.short_description = "Cost (USD)"
    cost_usd_display.admin_order_field = "cost_usd_micros"
