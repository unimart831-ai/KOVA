from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0025_userprofile_catalog_showcase"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="is_agency_approved",
            field=models.BooleanField(
                default=False,
                help_text="When True, user may subscribe to the Agency plan via sales onboarding.",
            ),
        ),
    ]
