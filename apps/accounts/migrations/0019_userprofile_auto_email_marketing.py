# Generated migration for auto_email_marketing preference

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0018_autopilot_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="auto_email_marketing",
            field=models.BooleanField(
                default=True,
                help_text="If True, Kova auto-sends AI email campaigns and recycles top posts to your list.",
            ),
        ),
    ]
