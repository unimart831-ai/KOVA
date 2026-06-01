# Generated manually — content safety models and blocked post status

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0028_post_publish_error"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="post",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("pending_approval", "Pending Approval"),
                    ("approved", "Approved"),
                    ("scheduled", "Scheduled"),
                    ("publishing", "Publishing..."),
                    ("published", "Published"),
                    ("failed", "Failed"),
                    ("blocked", "Blocked (Policy)"),
                    ("rejected", "Rejected"),
                ],
                db_index=True,
                default="draft",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="SystemSafetyConfig",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "auto_publish_paused",
                    models.BooleanField(
                        default=False,
                        help_text="When True, no posts are auto-published platform-wide.",
                    ),
                ),
                ("paused_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "paused_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "System Safety Configuration",
                "verbose_name_plural": "System Safety Configuration",
            },
        ),
        migrations.CreateModel(
            name="ContentSafetyIncident",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("snap", "Snap to Sell"),
                            ("batch_snap", "Batch Snap"),
                            ("publish", "Publish gate"),
                            ("approve", "Approval gate"),
                            ("upload", "Upload"),
                            ("vision", "Vision analyze"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("image_url", models.URLField(blank=True, max_length=2000)),
                ("reasons", models.JSONField(blank=True, default=list)),
                ("categories", models.JSONField(blank=True, default=list)),
                ("severity", models.PositiveSmallIntegerField(db_index=True, default=0)),
                (
                    "review_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending review"),
                            ("dismissed", "Dismissed (false positive)"),
                            ("confirmed", "Confirmed violation"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("action_taken", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "post",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="safety_incidents",
                        to="content.post",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_safety_incidents",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="content_safety_incidents",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["review_status", "-created_at"],
                        name="content_con_review__a1b2c3_idx",
                    ),
                    models.Index(
                        fields=["user", "-created_at"],
                        name="content_con_user_id_d4e5f6_idx",
                    ),
                ],
            },
        ),
    ]
