from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.core.accounts.models import User, UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile"
    fk_name = "user"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = ["email", "full_name", "onboarding_completed", "date_joined", "is_active"]
    list_filter = ["is_active", "onboarding_completed", "date_joined"]
    search_fields = ["email", "full_name"]
    ordering = ["-date_joined"]

    def delete_queryset(self, request, queryset):
        """Use per-instance soft_delete so emails are properly mangled."""
        for user in queryset:
            user.soft_delete()

    def delete_model(self, request, obj):
        """Explicit soft_delete for single-object admin deletes."""
        obj.soft_delete()

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("full_name", "username", "avatar", "timezone", "daily_brief_time")}),
        ("Status", {"fields": ("onboarding_completed",)}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "password1", "password2"),
        }),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "company_name", "industry", "plan", "created_at"]
    list_filter = ["plan", "industry"]
    search_fields = ["user__email", "company_name"]
    readonly_fields = ["created_at", "updated_at"]
