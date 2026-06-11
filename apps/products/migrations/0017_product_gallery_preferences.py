# Generated manually for P0-1 hero picker / gallery preferences

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0016_alter_commercepayment_transaction_ref"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="gallery_preferences",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Merchant gallery choices: hero_image_url override, excluded_urls, "
                    "excluded_variant_ids for carousel/shop visibility."
                ),
            ),
        ),
    ]
