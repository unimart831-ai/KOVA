import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("briefs", "0003_add_kova_score_overnight_work"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BriefWhatsAppLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("wa_id", models.CharField(db_index=True, max_length=20)),
                ("inbound_text", models.CharField(blank=True, max_length=500)),
                ("command", models.CharField(db_index=True, max_length=64)),
                ("response_text", models.TextField(blank=True)),
                ("success", models.BooleanField(default=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "brief",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="whatsapp_logs",
                        to="briefs.dailybrief",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="brief_whatsapp_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["-created_at"], name="briefs_brie_created_6a1b0d_idx"),
                    models.Index(fields=["user", "-created_at"], name="briefs_brie_user_id_8c4f2a_idx"),
                    models.Index(fields=["command", "-created_at"], name="briefs_brie_command_91e3bc_idx"),
                ],
            },
        ),
    ]
