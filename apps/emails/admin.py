from django.contrib import admin

from apps.emails.models import EmailLog


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("to_email", "email_type", "subject", "status", "created_at", "sent_at")
    list_filter = ("email_type", "status", "created_at")
    search_fields = ("to_email", "subject", "user__email")
    readonly_fields = (
        "id", "user", "to_email", "from_email", "email_type", "subject",
        "status", "provider_message_id", "metadata",
        "created_at", "sent_at", "delivered_at", "opened_at", "clicked_at",
        "failed_at", "error_message",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
