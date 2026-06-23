from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0035_userprofile_storefront_vibe_shop_footer"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="business_model",
            field=models.CharField(
                blank=True,
                choices=[
                    ("product", "Product business"),
                    ("service", "Service business"),
                    ("professional", "Professional / agency"),
                ],
                default="",
                help_text="Primary business type — drives onboarding and default workflows.",
                max_length=20,
            ),
        ),
    ]
