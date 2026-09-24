from django.contrib import admin

from apps.create.content.models import (
    ABTest,
    ContentSafetyIncident,
    ContentSeed,
    MediaAttachment,
    Post,
    PostVersion,
    SystemSafetyConfig,
    VoiceBrief,
)


class MediaInline(admin.TabularInline):
    model = MediaAttachment
    extra = 0


class PostVersionInline(admin.TabularInline):
    model = PostVersion
    extra = 0
    fields = ("version_number", "source", "edited_by", "content_text", "created_at")
    readonly_fields = ("version_number", "source", "edited_by", "created_at")


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    inlines = [MediaInline, PostVersionInline]
    list_display = [
        "user", "social_account", "status", "content_type",
        "variant_label", "scheduled_at", "created_at",
    ]
    list_filter = ["status", "content_type", "social_account__platform", "generated_by_agent"]
    search_fields = ["content_text", "user__email", "ai_angle"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "created_at"
    raw_id_fields = ["user", "seed", "product", "social_account", "ab_test"]


@admin.register(ABTest)
class ABTestAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "social_account", "status", "variant_count", "created_at"]
    list_filter = ["status"]
    search_fields = ["name", "user__email"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ContentSeed)
class ContentSeedAdmin(admin.ModelAdmin):
    """Where users drop ideas/topics for AI to expand into posts.
    Most-touched model in the studio flow — needs admin visibility."""

    list_display = [
        "id_short", "user", "status", "idea_preview",
        "target_platforms_display", "created_at",
    ]
    list_filter = ["status", "generate_images", "target_platforms"]
    search_fields = ["idea", "notes", "user__email"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "created_at"
    raw_id_fields = ["user", "product"]

    def id_short(self, obj):
        return str(obj.id)[:8]
    id_short.short_description = "ID"

    def idea_preview(self, obj):
        idea = obj.idea or ""
        return (idea[:80] + "...") if len(idea) > 80 else idea
    idea_preview.short_description = "Idea"

    def target_platforms_display(self, obj):
        if not obj.target_platforms:
            return "—"
        return ", ".join(obj.target_platforms[:3]) + ("…" if len(obj.target_platforms) > 3 else "")
    target_platforms_display.short_description = "Platforms"


@admin.register(MediaAttachment)
class MediaAttachmentAdmin(admin.ModelAdmin):
    """Image/video files attached to posts. Useful for debugging media
    pipeline issues (broken uploads, wrong file_type, etc.)."""

    list_display = ["id_short", "post_link", "file_type", "alt_text_short", "order", "created_at"]
    list_filter = ["file_type"]
    search_fields = ["post__user__email", "alt_text"]
    readonly_fields = ["created_at"]
    date_hierarchy = "created_at"
    raw_id_fields = ["post"]

    def id_short(self, obj):
        return str(obj.id)[:8]
    id_short.short_description = "ID"

    def post_link(self, obj):
        if obj.post:
            return f"{obj.post.user} — {obj.post.platform}"
        return "—"
    post_link.short_description = "Post"

    def alt_text_short(self, obj):
        return (obj.alt_text[:50] + "...") if len(obj.alt_text or "") > 50 else (obj.alt_text or "—")
    alt_text_short.short_description = "Alt text"


@admin.register(PostVersion)
class PostVersionAdmin(admin.ModelAdmin):
    """Version history per post — captures edits + AI regenerations.
    Read-only; never edit a version directly."""

    list_display = ["post_link", "version_number", "source", "edited_by", "created_at"]
    list_filter = ["source"]
    search_fields = ["post__user__email", "content_text"]
    readonly_fields = ["created_at", "post", "version_number", "source", "edited_by", "content_text"]
    date_hierarchy = "created_at"

    def post_link(self, obj):
        if obj.post:
            return f"{obj.post.user} — {obj.post.platform}"
        return "—"
    post_link.short_description = "Post"

    def has_add_permission(self, request):
        return False  # versions only created programmatically


@admin.register(VoiceBrief)
class VoiceBriefAdmin(admin.ModelAdmin):
    """Voice-to-content: user records an audio brief, AI transcribes + extracts seeds.
    Admin used to debug transcription failures or low-quality extraction."""

    list_display = [
        "id_short", "user", "status", "duration_display",
        "language_detected", "seeds_created", "created_at",
    ]
    list_filter = ["status", "language_detected"]
    search_fields = ["user__email", "transcript"]
    readonly_fields = ["created_at", "completed_at", "processing_time_ms"]
    date_hierarchy = "created_at"
    raw_id_fields = ["user", "campaign"]
    fieldsets = (
        ("Audio", {"fields": ("user", "audio_file", "duration_seconds", "status")}),
        ("AI processing", {
            "fields": ("transcript", "language_detected", "ai_extraction", "error_message"),
        }),
        ("Outputs", {
            "fields": ("seeds_created", "campaign"),
        }),
        ("Timestamps", {"fields": ("created_at", "completed_at", "processing_time_ms"), "classes": ("collapse",)}),
    )

    def id_short(self, obj):
        return str(obj.id)[:8]
    id_short.short_description = "ID"

    def duration_display(self, obj):
        s = obj.duration_seconds or 0
        return f"{s // 60}:{s % 60:02d}"
    duration_display.short_description = "Duration"


@admin.register(ContentSafetyIncident)
class ContentSafetyIncidentAdmin(admin.ModelAdmin):
    list_display = [
        "user", "source", "severity", "review_status", "created_at",
    ]
    list_filter = ["source", "review_status", "severity"]
    search_fields = ["user__email", "reasons", "categories"]
    readonly_fields = ["created_at", "reviewed_at"]
    raw_id_fields = ["user", "post", "reviewed_by"]


@admin.register(SystemSafetyConfig)
class SystemSafetyConfigAdmin(admin.ModelAdmin):
    list_display = [
        "auto_publish_paused",
        "content_safety_checks_enabled",
        "paused_by",
        "content_safety_paused_by",
        "updated_at",
    ]
    readonly_fields = ["updated_at"]
