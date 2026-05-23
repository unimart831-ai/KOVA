from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0019_userprofile_auto_email_marketing"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="commerce_autopilot",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "If True, Snap to Sell needs only a photo — AI names, prices, "
                    "creates posts, and auto-publishes your catalog."
                ),
            ),
        ),
    ]
