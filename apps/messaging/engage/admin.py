from django.contrib import admin

from apps.messaging.engage.models import Interaction, Superfan


@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = ["author_name", "interaction_type", "status", "sentiment", "social_account", "created_at"]
    list_filter = ["interaction_type", "status", "sentiment"]
    search_fields = ["author_name", "content"]


@admin.register(Superfan)
class SuperfanAdmin(admin.ModelAdmin):
    list_display = ["author_name", "author_username", "tier", "interaction_count", "last_interaction_at"]
    list_filter = ["tier"]
    search_fields = ["author_name", "author_username"]
