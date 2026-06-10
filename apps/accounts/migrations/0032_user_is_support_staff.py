from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0031_money_board_digest_engage_trial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_support_staff",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Limited staff role: read-only admin dashboard access. "
                    "Requires is_staff=True. Superusers bypass restrictions."
                ),
            ),
        ),
    ]
