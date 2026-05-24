# Generated manually for Studio polish label update

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0008_product_visual_mode"),
    ]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="visual_mode",
            field=models.CharField(
                choices=[
                    ("as_is", "Use as-is"),
                    ("quick_polish", "Quick polish"),
                    ("pro_scene", "Studio polish"),
                ],
                default="quick_polish",
                help_text="How Kova treats product photos before content generation.",
                max_length=20,
            ),
        ),
    ]
