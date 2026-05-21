from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0017_add_kova_link_page_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="autopilot_enabled",
            field=models.BooleanField(
                default=False,
                help_text="If True, the Strategist plans a full week of content autonomously and posts are auto-generated and scheduled every week.",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="autopilot_posts_per_week",
            field=models.PositiveSmallIntegerField(
                default=5,
                help_text="Target number of posts per week when autopilot is active (1-14).",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="autopilot_platforms",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Platforms for autopilot to target. Empty = all connected. ["instagram", "linkedin"]',
            ),
        ),
    ]
