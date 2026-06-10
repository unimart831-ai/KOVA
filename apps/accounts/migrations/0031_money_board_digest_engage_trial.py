from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0030_userprofile_operations_autopilot"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="money_board_digest_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Daily email/in-app digest when money board counts need attention.",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="engage_trial_replies_this_week",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text="Starter trial: auto-replies sent this ISO week.",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="engage_trial_week_start",
            field=models.DateTimeField(
                blank=True,
                help_text="Week boundary for engage_trial_replies_this_week reset.",
                null=True,
            ),
        ),
    ]
