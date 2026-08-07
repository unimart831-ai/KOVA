# Generated manually — per-user content safety controls

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0026_userprofile_is_agency_approved"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="content_safety_strike_count",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text="Count of confirmed or high-severity content policy violations.",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="suspended_for_policy",
            field=models.BooleanField(
                default=False,
                help_text="When True, user cannot publish until staff clears the suspension.",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="auto_publish_paused",
            field=models.BooleanField(
                default=False,
                help_text="When True, this user's posts are not auto-published (manual only).",
            ),
        ),
    ]
