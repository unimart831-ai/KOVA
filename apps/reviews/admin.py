from django.contrib import admin

from .models import ReviewRequest


@admin.register(ReviewRequest)
class ReviewRequestAdmin(admin.ModelAdmin):
    list_display = (
        "created_at", "user", "customer_name", "channel", "status",
        "sentiment", "sentiment_score",
    )
    list_filter = ("status", "channel", "sentiment", "created_at")
    search_fields = (
        "user__email", "user__username",
        "customer_name", "customer_phone", "customer_email",
        "response_text",
    )
    readonly_fields = (
        "id", "created_at", "updated_at",
        "sent_at", "responded_at",
    )
    raw_id_fields = ("user", "lead", "booking", "content_seed")
    date_hierarchy = "created_at"
