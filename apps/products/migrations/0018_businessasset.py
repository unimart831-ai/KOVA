# Generated manually for BusinessAsset foundation

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0017_product_gallery_preferences"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BusinessAsset",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "asset_type",
                    models.CharField(
                        choices=[
                            ("product", "Product"),
                            ("service", "Service"),
                            ("digital", "Digital Product"),
                            ("portfolio", "Portfolio Project"),
                            ("case_study", "Case Study"),
                            ("testimonial", "Testimonial"),
                            ("offer", "Offer"),
                            ("event", "Event"),
                            ("promotion", "Promotion"),
                        ],
                        default="product",
                        max_length=20,
                    ),
                ),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                (
                    "metadata",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Type-specific fields (portfolio client, offer expiry, etc.).",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("pending_approval", "Pending Approval"),
                            ("published", "Published"),
                            ("archived", "Archived"),
                        ],
                        default="draft",
                        max_length=20,
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("manual", "Manual"),
                            ("snap", "Snap to Sell"),
                            ("whatsapp", "WhatsApp"),
                            ("import", "Import"),
                        ],
                        default="manual",
                        max_length=15,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "product",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="business_asset",
                        to="products.product",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="business_assets",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="businessasset",
            index=models.Index(fields=["user", "asset_type", "-created_at"], name="products_ba_user_ty_idx"),
        ),
        migrations.AddIndex(
            model_name="businessasset",
            index=models.Index(fields=["user", "status"], name="products_ba_user_st_idx"),
        ),
    ]
