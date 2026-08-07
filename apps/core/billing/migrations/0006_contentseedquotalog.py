import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0005_discountcode_discountredemption_planprice_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ContentSeedQuotaLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("reset_usage", "Reset usage counter"),
                            ("set_limit_override", "Set monthly limit override"),
                            ("clear_limit_override", "Clear limit override"),
                            ("set_bonus", "Set bonus seeds"),
                            ("clear_all", "Clear all overrides"),
                        ],
                        max_length=32,
                    ),
                ),
                ("reason", models.TextField()),
                ("used_before", models.PositiveIntegerField(default=0)),
                ("max_before", models.PositiveIntegerField(default=0)),
                ("remaining_before", models.PositiveIntegerField(default=0)),
                ("plan_label", models.CharField(blank=True, max_length=40)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "admin",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="seed_quota_admin_actions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="seed_quota_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["user", "-created_at"], name="billing_csq_user_created_idx"),
                    models.Index(fields=["action", "-created_at"], name="billing_csq_action_created_idx"),
                ],
            },
        ),
    ]
