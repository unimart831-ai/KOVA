from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0034_kova_plan_and_marketing_campaign"),
    ]

    operations = [
        migrations.AddField(
            model_name="marketingcampaign",
            name="expires_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="When the offer ends — campaign page auto-archives after this.",
                null=True,
            ),
        ),
    ]
