# Generated manually for Market Day Mode (Batch Snap)

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0026_post_published_at_index"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("products", "0011_product_exclude_primary_image"),
    ]

    operations = [
        migrations.CreateModel(
            name="BatchSnapSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("stall_title", models.CharField(blank=True, max_length=120)),
                ("voice_transcript", models.TextField(blank=True)),
                ("stall_notes", models.TextField(blank=True)),
                ("stall_context", models.JSONField(blank=True, default=dict)),
                ("offering_type", models.CharField(default="product", max_length=10)),
                ("default_price", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("default_currency", models.CharField(default="KES", max_length=5)),
                (
                    "launch_bundle",
                    models.BooleanField(
                        default=True,
                        help_text="When true, create stall showcase reel + collection post + seller ping",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("processing", "Processing items"),
                            ("finalizing", "Building stall launch"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="processing",
                        max_length=20,
                    ),
                ),
                ("product_count", models.PositiveSmallIntegerField(default=0)),
                ("items_processed", models.PositiveSmallIntegerField(default=0)),
                ("shop_url", models.URLField(blank=True, max_length=500)),
                ("bundle_post_ids", models.JSONField(blank=True, default=list)),
                ("whatsapp_message", models.TextField(blank=True)),
                ("whatsapp_sent", models.BooleanField(default=False)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("finalized_at", models.DateTimeField(blank=True, null=True)),
                (
                    "bundle_seed",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="batch_snap_sessions",
                        to="content.contentseed",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="batch_snap_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddField(
            model_name="product",
            name="batch_index",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="Order within a Batch Snap session (0-based)",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="batch_snap_session",
            field=models.ForeignKey(
                blank=True,
                help_text="Market Day batch this product was created in (Batch Snap)",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="products",
                to="products.batchsnapsession",
            ),
        ),
        migrations.AddIndex(
            model_name="batchsnapsession",
            index=models.Index(fields=["user", "-created_at"], name="products_ba_user_id_6a8f2d_idx"),
        ),
        migrations.AddIndex(
            model_name="batchsnapsession",
            index=models.Index(fields=["user", "status"], name="products_ba_user_id_9c4e1a_idx"),
        ),
    ]
