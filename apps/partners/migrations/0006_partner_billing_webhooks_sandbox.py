# Generated manually — fernet_fields blocked makemigrations in this environment.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("partners", "0005_marketplacepartner_enrich_descriptions_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="marketplacepartner",
            name="is_sandbox",
            field=models.BooleanField(
                default=False,
                help_text="Sandbox mode — sellers provisioned but posts dry-run instead of publishing live",
            ),
        ),
        migrations.AddField(
            model_name="referral",
            name="last_payment_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Timestamp of last counted subscription payment (dedupes webhook retries)",
                null=True,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="commission",
            unique_together={("partner", "referral", "period_start")},
        ),
        migrations.CreateModel(
            name="WebhookDeliveryLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event", models.CharField(db_index=True, max_length=50)),
                ("payload_hash", models.CharField(blank=True, max_length=64)),
                ("status", models.CharField(choices=[("success", "Success"), ("failed", "Failed"), ("skipped", "Skipped")], db_index=True, max_length=10)),
                ("response_code", models.PositiveIntegerField(blank=True, null=True)),
                ("attempts", models.PositiveIntegerField(default=1)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("marketplace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="webhook_logs", to="partners.marketplacepartner")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["marketplace", "-created_at"], name="partners_we_marketp_8a1f2d_idx")],
            },
        ),
    ]
