import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("content", "0020_add_post_format_carousel_slides"),
    ]

    operations = [
        migrations.CreateModel(
            name="WeeklyContentPlan",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="weekly_content_plans", to=settings.AUTH_USER_MODEL)),
                ("week_start", models.DateField(help_text="Monday of the plan week")),
                ("week_end", models.DateField(help_text="Sunday of the plan week")),
                ("status", models.CharField(choices=[("planning", "Planning"), ("generating", "Generating Content"), ("scheduling", "Optimizing Schedule"), ("active", "Active — Publishing"), ("completed", "Week Completed"), ("failed", "Failed"), ("cancelled", "Cancelled")], db_index=True, default="planning", max_length=15)),
                ("strategy", models.JSONField(blank=True, default=dict, help_text="Strategist's weekly plan: {theme, goals, daily_topics: [{day, topic, intent, platforms, notes}], content_mix}")),
                ("strategy_reasoning", models.TextField(blank=True, help_text="Why the Strategist chose this strategy")),
                ("seeds_created", models.PositiveIntegerField(default=0)),
                ("posts_generated", models.PositiveIntegerField(default=0)),
                ("posts_published", models.PositiveIntegerField(default=0)),
                ("posts_failed", models.PositiveIntegerField(default=0)),
                ("performance_summary", models.JSONField(blank=True, default=dict, help_text="Post-week performance: {total_impressions, total_engagement, avg_engagement_rate, top_post_id}")),
                ("review_email_sent", models.BooleanField(default=False)),
                ("review_email_sent_at", models.DateTimeField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["-week_start"],
            },
        ),
        migrations.AddConstraint(
            model_name="weeklycontentplan",
            constraint=models.UniqueConstraint(fields=("user", "week_start"), name="unique_user_week_start"),
        ),
        migrations.AddIndex(
            model_name="weeklycontentplan",
            index=models.Index(fields=["user", "status", "-week_start"], name="content_wcp_user_status_idx"),
        ),
    ]
