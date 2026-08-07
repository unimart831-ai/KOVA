from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0024_userprofile_seed_quota_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="catalog_showcase_weekly",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "If True, Kova builds a carousel + reel of your in-stock catalog "
                    "(name + price per item) at most once per week."
                ),
                verbose_name="Weekly catalog showcase",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="catalog_showcase_last_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Last time a catalog showcase carousel/reel was generated.",
                null=True,
            ),
        ),
    ]
