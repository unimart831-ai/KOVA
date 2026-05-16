from django.contrib import admin

from .models import Booking, BookingLink


@admin.register(BookingLink)
class BookingLinkAdmin(admin.ModelAdmin):
    list_display = ("label", "user", "slug", "industry_template", "is_active", "created_at")
    list_filter = ("industry_template", "is_active", "created_at")
    search_fields = ("label", "slug", "user__email", "user__username")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("user",)
    date_hierarchy = "created_at"


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "scheduled_at", "customer_name", "service_name",
        "price_kes", "status", "booking_link",
    )
    list_filter = ("status", "source_channel", "scheduled_at")
    search_fields = (
        "customer_name", "customer_phone", "customer_email",
        "service_name", "booking_link__label", "booking_link__slug",
    )
    readonly_fields = ("id", "created_at", "confirmed_at", "completed_at")
    raw_id_fields = ("booking_link", "source_post", "source_campaign", "source_qr")
    date_hierarchy = "scheduled_at"
