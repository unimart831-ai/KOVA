import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0021_weeklycontentplan"),
    ]

    operations = [
        migrations.AddField(
            model_name="contentseed",
            name="weekly_plan",
            field=models.ForeignKey(
                blank=True,
                help_text="Set when this seed was created by Content Autopilot.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="seeds",
                to="content.weeklycontentplan",
            ),
        ),
        migrations.AlterField(
            model_name="weeklycontentplan",
            name="status",
            field=models.CharField(
                choices=[
                    ("planning", "Planning"),
                    ("pending_review", "Awaiting Your Approval"),
                    ("generating", "Generating Content"),
                    ("scheduling", "Optimizing Schedule"),
                    ("active", "Active — Publishing"),
                    ("completed", "Week Completed"),
                    ("failed", "Failed"),
                    ("cancelled", "Cancelled"),
                ],
                db_index=True,
                default="planning",
                max_length=15,
            ),
        ),
    ]
