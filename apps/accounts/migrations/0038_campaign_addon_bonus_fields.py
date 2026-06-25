from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0037_kova_plan_and_marketing_campaign"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="burst_campaign_bonus",
            field=models.PositiveIntegerField(
                default=0,
                help_text="One-time burst pack credits for the current calendar month.",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="burst_campaign_expires_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When burst credits expire (end of purchase month).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="recurring_campaign_bonus",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Active recurring campaign add-ons (Boost/Scale) — stacks on base quota.",
            ),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="seed_monthly_bonus",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Extra campaigns on top of plan limit (recurring add-ons + burst).",
            ),
        ),
    ]
