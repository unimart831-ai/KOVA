# Generated manually for visual enhancement spec

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0007_commerce_links"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="visual_mode",
            field=models.CharField(
                choices=[
                    ("as_is", "Use as-is"),
                    ("quick_polish", "Quick polish"),
                    ("pro_scene", "Pro scene"),
                ],
                default="quick_polish",
                help_text="How Kova treats product photos before content generation.",
                max_length=20,
            ),
        ),
    ]
