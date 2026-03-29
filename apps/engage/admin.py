from django.contrib import admin

from apps.engage.models import Interaction


@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = ["author_name", "interaction_type", "status", "sentiment", "social_account", "created_at"]
    list_filter = ["interaction_type", "status", "sentiment"]
    search_fields = ["author_name", "content"]
