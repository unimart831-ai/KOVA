from django.contrib import admin

from apps.agents.models import AgentConfig, AgentAction


@admin.register(AgentConfig)
class AgentConfigAdmin(admin.ModelAdmin):
    list_display = ["user", "agent_type", "is_active", "updated_at"]
    list_filter = ["agent_type", "is_active"]
    search_fields = ["user__email"]


@admin.register(AgentAction)
class AgentActionAdmin(admin.ModelAdmin):
    list_display = ["user", "agent_type", "action_type", "status", "tokens_used", "created_at"]
    list_filter = ["agent_type", "status"]
    search_fields = ["user__email", "action_type"]
    readonly_fields = ["created_at", "completed_at"]
