from django.contrib import admin
from django.utils.html import format_html

from apps.insight.help.models import (
    Article,
    ArticleTopic,
    ChangelogEntry,
    HelpPageView,
    NewsletterSubscriber,
    WeeklyDigest,
)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "audience",
        "status",
        "author_agent",
        "view_count",
        "published_at",
        "updated_at",
    )
    list_filter = ("status", "audience", "category", "author_agent")
    search_fields = ("title", "slug", "excerpt", "body_md", "tags")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("view_count", "created_at", "updated_at")
    autocomplete_fields = ("reviewed_by",)
    fieldsets = (
        (None, {
            "fields": ("title", "slug", "excerpt", "category", "order", "tags"),
        }),
        ("Audience & status", {
            "fields": ("audience", "status", "published_at", "reviewed_by", "author_agent"),
        }),
        ("Body", {
            "fields": ("body_md", "body_html", "legacy_template"),
            "description": (
                "Markdown-authored articles: fill body_md, leave legacy_template blank. "
                "Migrated articles: legacy_template points to help/articles/&lt;slug&gt;.html."
            ),
        }),
        ("SEO & presentation", {
            "fields": ("hero_image", "meta_title", "meta_description", "reading_minutes"),
        }),
        ("Metrics", {
            "fields": ("view_count", "created_at", "updated_at"),
        }),
    )
    actions = ("mark_published", "mark_archived")

    @admin.action(description="Mark selected articles as published")
    def mark_published(self, request, queryset):
        for article in queryset:
            article.mark_published(reviewer=request.user)
        self.message_user(request, f"Published {queryset.count()} article(s).")

    @admin.action(description="Archive selected articles")
    def mark_archived(self, request, queryset):
        updated = queryset.update(status=Article.Status.ARCHIVED)
        self.message_user(request, f"Archived {updated} article(s).")


@admin.register(ArticleTopic)
class ArticleTopicAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "priority", "audience", "suggested_category", "source", "created_at")
    list_filter = ("status", "audience", "suggested_category", "source")
    search_fields = ("title", "rationale")
    autocomplete_fields = ("drafted_article",)
    readonly_fields = ("created_at", "drafted_at")


@admin.register(ChangelogEntry)
class ChangelogEntryAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "shipped_at", "is_public", "linked_article")
    list_filter = ("category", "is_public")
    search_fields = ("title", "body_md")
    autocomplete_fields = ("linked_article",)
    date_hierarchy = "shipped_at"
    readonly_fields = ("created_at",)


@admin.register(WeeklyDigest)
class WeeklyDigestAdmin(admin.ModelAdmin):
    list_display = ("week_end", "status", "approved_by", "approved_at", "sent_at", "updated_at")
    list_filter = ("status",)
    date_hierarchy = "week_end"
    readonly_fields = ("approved_at", "sent_at", "created_at", "updated_at")
    autocomplete_fields = ("approved_by",)
    fieldsets = (
        (None, {"fields": ("week_end", "status", "approved_by", "approved_at", "sent_at")}),
        ("Rendered sections", {
            "fields": ("intro_html", "changelog_html", "articles_html", "stats_html"),
            "description": "These HTML blocks are inlined into the weekly email.",
        }),
        ("Agent output", {"fields": ("raw_content",), "classes": ("collapse",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
    actions = ("mark_approved",)

    @admin.action(description="Approve selected digests")
    def mark_approved(self, request, queryset):
        for digest in queryset:
            digest.approve(request.user)
        self.message_user(request, f"Approved {queryset.count()} digest(s).")


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "status", "source", "source_slug", "subscribed_at", "unsubscribed_at")
    list_filter = ("status", "source")
    search_fields = ("email", "source_slug")
    readonly_fields = ("unsubscribe_token", "subscribed_at", "unsubscribed_at")
    date_hierarchy = "subscribed_at"


@admin.register(HelpPageView)
class HelpPageViewAdmin(admin.ModelAdmin):
    list_display = ("user", "page_type", "article_slug", "category", "viewed_at")
    list_filter = ("page_type", "category")
    search_fields = ("article_slug", "article_title", "user__email")
    readonly_fields = ("user", "page_type", "article_slug", "article_title", "category", "viewed_at")
    date_hierarchy = "viewed_at"
