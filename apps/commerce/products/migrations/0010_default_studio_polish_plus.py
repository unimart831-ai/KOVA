"""Default to Studio polish (Plus); migrate legacy quick_polish rows."""

from django.db import migrations, models


def map_quick_polish_to_studio(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    Product.objects.filter(visual_mode="quick_polish").update(visual_mode="pro_scene")


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0009_alter_product_visual_mode_label"),
    ]

    operations = [
        migrations.RunPython(map_quick_polish_to_studio, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="product",
            name="visual_mode",
            field=models.CharField(
                choices=[
                    ("as_is", "Use as-is"),
                    ("quick_polish", "Quick polish"),
                    ("pro_scene", "Studio polish"),
                ],
                default="pro_scene",
                help_text="How Kova treats product photos before content generation.",
                max_length=20,
            ),
        ),
    ]
