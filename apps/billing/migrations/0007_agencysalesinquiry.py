import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0006_contentseedquotalog"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AgencySalesInquiry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=200)),
                ("email", models.EmailField(db_index=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("company_name", models.CharField(blank=True, max_length=255)),
                ("message", models.TextField()),
                ("client_count", models.PositiveIntegerField(blank=True, null=True)),
                ("plan_interest", models.CharField(blank=True, max_length=30)),
                (
                    "status",
                    models.CharField(
                        choices=[("new", "New"), ("contacted", "Contacted"), ("closed", "Closed")],
                        db_index=True,
                        default="new",
                        max_length=20,
                    ),
                ),
                ("staff_notes", models.TextField(blank=True)),
                ("contacted_at", models.DateTimeField(blank=True, null=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="agency_sales_inquiries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "agency sales inquiry",
                "verbose_name_plural": "agency sales inquiries",
                "ordering": ["-created_at"],
            },
        ),
    ]
