from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0022_autopilot_preview_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="weeklycontentplan",
            name="planning_log",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Live strategist steps shown during plan preview generation.",
            ),
        ),
    ]
