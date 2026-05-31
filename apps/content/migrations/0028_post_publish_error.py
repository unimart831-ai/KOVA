from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0027_remove_weeklycontentplan_unique_user_week_start_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="publish_error",
            field=models.TextField(
                blank=True,
                help_text="Last publish failure message from the platform API (shown in Queue).",
            ),
        ),
    ]
