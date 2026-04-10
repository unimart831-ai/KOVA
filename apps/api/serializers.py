from rest_framework import serializers

from apps.agents.models import AgentAction, AgentConfig
from apps.analytics.models import Conversion, PostMetric
from apps.content.models import ContentSeed, Post
from apps.platforms.models import SocialAccount


class SocialAccountSerializer(serializers.ModelSerializer):
    platform_display = serializers.CharField(source="get_platform_display", read_only=True)

    class Meta:
        model = SocialAccount
        fields = [
            "id", "platform", "platform_display", "username",
            "display_name", "avatar_url", "is_active",
            "last_synced_at", "connected_at",
        ]
        read_only_fields = fields


class ContentSeedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentSeed
        fields = [
            "id", "idea", "notes", "target_platforms",
            "status", "batch_strategy", "brand",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]


class PostSerializer(serializers.ModelSerializer):
    social_account_name = serializers.CharField(
        source="social_account.username", read_only=True
    )
    platform = serializers.CharField(
        source="social_account.platform", read_only=True
    )

    class Meta:
        model = Post
        fields = [
            "id", "content_text", "content_type", "status",
            "platform", "social_account", "social_account_name",
            "media_urls", "scheduled_at", "published_at",
            "platform_post_id", "platform_post_url",
            "predicted_engagement_score", "brand",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "platform", "social_account_name",
            "published_at", "platform_post_id", "platform_post_url",
            "predicted_engagement_score", "created_at", "updated_at",
        ]


class PostMetricSerializer(serializers.ModelSerializer):
    post_id = serializers.UUIDField(source="post.id", read_only=True)

    class Meta:
        model = PostMetric
        fields = [
            "id", "post_id", "likes", "comments", "shares",
            "impressions", "reach", "clicks", "saves",
            "engagement_rate", "fetched_at",
        ]
        read_only_fields = fields


class AgentConfigSerializer(serializers.ModelSerializer):
    agent_type_display = serializers.CharField(
        source="get_agent_type_display", read_only=True
    )

    class Meta:
        model = AgentConfig
        fields = [
            "id", "agent_type", "agent_type_display",
            "is_active", "custom_instructions", "config",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "agent_type", "agent_type_display", "created_at", "updated_at"]


class AgentActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentAction
        fields = [
            "id", "agent_type", "action_type", "description",
            "status", "tokens_used", "model_used", "duration_ms",
            "created_at", "completed_at",
        ]
        read_only_fields = fields


class ConversionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversion
        fields = [
            "id", "conversion_type", "revenue", "event_name",
            "post", "social_account", "product",
            "utm_source", "utm_medium", "utm_campaign", "utm_content",
            "metadata", "created_at",
        ]
        read_only_fields = ["id", "created_at"]
