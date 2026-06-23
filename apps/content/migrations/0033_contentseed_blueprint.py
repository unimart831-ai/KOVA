from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0032_rename_content_con_review__a1b2c3_idx_content_con_review__7adf57_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="contentseed",
            name="blueprint",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="ContentBlueprint spec — platform slots and objective from BusinessAsset.",
            ),
        ),
    ]
