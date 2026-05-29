from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0023_alter_userprofile_autopilot_enabled_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="seed_quota_reset_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Seeds before this time are not counted toward the monthly limit.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="seed_monthly_limit_override",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="When set, replaces plan max_seeds_per_month for this user.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="seed_monthly_bonus",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Extra seeds added on top of plan limit (promotions).",
            ),
        ),
    ]
