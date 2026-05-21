from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0023_weeklycontentplan_planning_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="contentseed",
            name="generation_log",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Live Create Agent steps shown during post generation.",
            ),
        ),
    ]
