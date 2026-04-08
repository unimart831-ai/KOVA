from django.contrib import admin

from apps.links.models import (
    FormSubmission,
    KovaForm,
    KovaLink,
    KovaPage,
    LinkClick,
    PageView,
)


class KovaLinkInline(admin.TabularInline):
    model = KovaLink
    extra = 0
    fields = ("title", "link_type", "url", "order", "is_active", "total_clicks")
    readonly_fields = ("total_clicks",)


class KovaFormInline(admin.TabularInline):
    model = KovaForm
    extra = 0
    fields = ("title", "form_type", "is_active", "total_submissions")
    readonly_fields = ("total_submissions",)


@admin.register(KovaPage)
class KovaPageAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "user", "is_published", "total_views", "created_at")
    list_filter = ("is_published", "theme")
    search_fields = ("title", "slug", "user__email")
    readonly_fields = ("total_views", "created_at", "updated_at")
    inlines = [KovaLinkInline, KovaFormInline]


@admin.register(KovaLink)
class KovaLinkAdmin(admin.ModelAdmin):
    list_display = ("title", "page", "link_type", "url", "total_clicks", "is_active")
    list_filter = ("link_type", "is_active")
    search_fields = ("title", "url")
    readonly_fields = ("total_clicks",)


@admin.register(KovaForm)
class KovaFormAdmin(admin.ModelAdmin):
    list_display = ("title", "page", "form_type", "is_active", "total_submissions")
    list_filter = ("form_type", "is_active")
    readonly_fields = ("total_submissions",)


@admin.register(FormSubmission)
class FormSubmissionAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "form", "is_read", "submitted_at")
    list_filter = ("is_read", "form__form_type")
    search_fields = ("email", "name")
    readonly_fields = ("submitted_at",)


@admin.register(LinkClick)
class LinkClickAdmin(admin.ModelAdmin):
    list_display = ("link", "country", "device_type", "clicked_at")
    list_filter = ("device_type",)
    readonly_fields = ("clicked_at",)


@admin.register(PageView)
class PageViewAdmin(admin.ModelAdmin):
    list_display = ("page", "date", "views", "unique_visitors")
    list_filter = ("date",)
